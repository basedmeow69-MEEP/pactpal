import json

import httpx
import pytest

from pactpal.paypal_client import PayPalError, SandboxClient, request_id


class FakePayPal:
    def __init__(self):
        self.token_calls = 0
        self.requests: list[httpx.Request] = []
        self.revoke_next = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/oauth2/token":
            self.token_calls += 1
            return httpx.Response(200, json={"access_token": f"tok{self.token_calls}", "expires_in": 32400})
        self.requests.append(request)
        if self.revoke_next:
            self.revoke_next = False
            return httpx.Response(401, json={"error": "invalid_token"})
        if request.url.path == "/v2/checkout/orders/bad":
            return httpx.Response(422, json={"name": "UNPROCESSABLE_ENTITY"})
        return httpx.Response(201, json={"id": "ORDER1", "status": "CREATED"})


def make_client(fake: FakePayPal, now: list[float]) -> SandboxClient:
    return SandboxClient("id", "secret", transport=httpx.MockTransport(fake.handler), clock=lambda: now[0])


def test_token_is_cached_then_refreshed_before_expiry():
    fake, now = FakePayPal(), [1000.0]
    client = make_client(fake, now)
    client.call("GET", "/v2/checkout/orders/ORDER1")
    client.call("GET", "/v2/checkout/orders/ORDER1")
    assert fake.token_calls == 1
    now[0] += 32400 - 299
    client.call("GET", "/v2/checkout/orders/ORDER1")
    assert fake.token_calls == 2
    assert fake.requests[-1].headers["Authorization"] == "Bearer tok2"


def test_revoked_token_is_refreshed_once():
    fake, now = FakePayPal(), [0.0]
    client = make_client(fake, now)
    client.call("GET", "/x")
    fake.revoke_next = True
    assert client.call("GET", "/x")["id"] == "ORDER1"
    assert fake.token_calls == 2


def test_writes_require_and_send_idempotency_key():
    fake, now = FakePayPal(), [0.0]
    client = make_client(fake, now)
    with pytest.raises(ValueError):
        client.call("POST", "/v2/checkout/orders", json_body={})
    key = request_id("pact-1", "create_order", {"b": 1, "a": 2})
    client.call("POST", "/v2/checkout/orders", json_body={"a": 2}, idempotency_key=key)
    assert fake.requests[-1].headers["PayPal-Request-Id"] == key
    assert json.loads(fake.requests[-1].content) == {"a": 2}


def test_request_id_is_stable_and_stage_specific():
    assert request_id("p", "s", {"a": 1, "b": 2}) == request_id("p", "s", {"b": 2, "a": 1})
    assert request_id("p", "s", {"a": 1}) != request_id("p", "t", {"a": 1})
    assert len(request_id("p", "s", None)) == 32


def test_errors_surface_status_and_body():
    fake, now = FakePayPal(), [0.0]
    with pytest.raises(PayPalError) as err:
        make_client(fake, now).call("GET", "/v2/checkout/orders/bad")
    assert err.value.status == 422
    assert err.value.body["name"] == "UNPROCESSABLE_ENTITY"
