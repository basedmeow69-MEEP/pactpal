"""PayPal Sandbox REST client with cached OAuth tokens and idempotent writes."""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable

import httpx

from .config import SANDBOX_BASE_URL

REFRESH_MARGIN_SECONDS = 300


def request_id(pact_id: str, stage: str, payload: Any) -> str:
    """Deterministic PayPal-Request-Id so an agent retry cannot duplicate a write."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{pact_id}|{stage}|{canonical}".encode()).hexdigest()[:32]


class PayPalError(Exception):
    def __init__(self, status: int, body: Any):
        super().__init__(f"PayPal returned {status}: {body}")
        self.status = status
        self.body = body


class SandboxClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        base_url: str = SANDBOX_BASE_URL,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self._auth = (client_id, client_secret)
        self._http = httpx.Client(base_url=base_url, transport=transport, timeout=30)
        self._clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    def _access_token(self, force: bool = False) -> str:
        if force or self._token is None or self._clock() >= self._expires_at - REFRESH_MARGIN_SECONDS:
            response = self._http.post(
                "/v1/oauth2/token",
                auth=self._auth,
                data={"grant_type": "client_credentials"},
            )
            if response.status_code != 200:
                raise PayPalError(response.status_code, _body(response))
            data = response.json()
            self._token = data["access_token"]
            self._expires_at = self._clock() + int(data["expires_in"])
        return self._token

    def call(self, method: str, path: str, *, json_body: Any = None, idempotency_key: str | None = None) -> Any:
        if method != "GET" and idempotency_key is None:
            raise ValueError(f"{method} {path} needs an idempotency key")
        for attempt in (0, 1):
            headers = {"Authorization": f"Bearer {self._access_token(force=attempt == 1)}", "Prefer": "return=representation"}
            if idempotency_key:
                headers["PayPal-Request-Id"] = idempotency_key
            response = self._http.request(method, path, json=json_body, headers=headers)
            # A token revoked before its expiry gets one refresh and retry.
            if response.status_code == 401 and attempt == 0:
                continue
            if response.status_code >= 400:
                raise PayPalError(response.status_code, _body(response))
            return _body(response)
        raise AssertionError("unreachable")


def _body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return response.text
