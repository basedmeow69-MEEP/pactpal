"""Claude negotiation guardrails, red-zone void path, and live Sandbox failure handling."""
from __future__ import annotations

import io
import urllib.error
from pathlib import Path

import pytest

from src.backend import negotiation_agents
from src.backend.negotiation_agents import AgentOffer, run_claude_negotiation
from src.backend.pactpal_engine import PactPalClearinghouseEngine
from src.backend.paypal_sandbox_client import PayPalSandboxClient

SCENARIO = PactPalClearinghouseEngine.get_scenarios()["b2b_gpu_inference_cluster"]


def scripted_offers(*offers: AgentOffer):
    queue = list(offers)
    return lambda system, transcript: queue.pop(0)


def offer(price: float, accept: bool = False) -> AgentOffer:
    return AgentOffer(price_usd=price, early_discount_pct=8.0, sla_guarantee_score=92.0,
                      accept_counterparty_offer=accept, rationale="test move")


def test_claude_agents_reach_agreement_on_accepted_price():
    deal = run_claude_negotiation(SCENARIO, scripted_offers(offer(480), offer(360), offer(405), offer(0, accept=True)))
    assert deal["price_usd"] == 405.00
    assert deal["turns"][-1]["role_badge"] == "PACT_LOCKED"


def test_buyer_offer_above_mandate_cap_is_clamped():
    deal = run_claude_negotiation(SCENARIO, scripted_offers(offer(480), offer(9999), offer(0, accept=True)))
    assert deal["price_usd"] == SCENARIO["buyer_max_budget_usd"]


def test_seller_cannot_offer_below_floor():
    floor = round(SCENARIO["negotiated_price_usd"] * 0.95, 2)
    deal = run_claude_negotiation(SCENARIO, scripted_offers(offer(1.0), offer(0, accept=True)))
    assert deal["price_usd"] == floor


def test_refusal_or_error_falls_back_to_scripted_negotiation(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(negotiation_agents, "_claude_offer_fn", lambda: (lambda s, t: None))
    client = PayPalSandboxClient(client_id="", client_secret="", mode="hybrid", vault_path=tmp_path / "v.json")
    res = PactPalClearinghouseEngine(client=client, use_claude_agents=True).execute_pact_lifecycle(sla_outcome_mode="green_payout")
    assert res["negotiation_engine"].startswith("scripted")
    assert res["financial_summary"]["negotiated_invoice_usd"] == 390.00


def test_claude_price_flows_into_invoice_and_scaled_line_items(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(negotiation_agents, "_claude_offer_fn",
                        lambda: scripted_offers(offer(480), offer(400.10), offer(0, accept=True)))
    client = PayPalSandboxClient(client_id="", client_secret="", mode="hybrid", vault_path=tmp_path / "v.json")
    res = PactPalClearinghouseEngine(client=client, use_claude_agents=True).execute_pact_lifecycle(sla_outcome_mode="green_payout")
    assert res["negotiation_engine"] == negotiation_agents.ai_model_label()
    assert res["financial_summary"]["final_net_settled_usd"] == 400.10
    items = res["paypal_telemetry"][0]["raw_Preview"]
    invoice_payload_total = sum(float(i["unit_amount"]["value"]) for i in
                                PactPalClearinghouseEngine.scale_line_items(SCENARIO["line_items"], 400.10))
    assert round(invoice_payload_total, 2) == 400.10
    assert items["amount"]["value"] == "400.10"


def test_red_zone_voids_authorization_and_cancels_invoice(tmp_path: Path):
    client = PayPalSandboxClient(client_id="", client_secret="", mode="hybrid", vault_path=tmp_path / "v.json")
    res = PactPalClearinghouseEngine(client=client, use_claude_agents=False).execute_pact_lifecycle(sla_outcome_mode="red_void")
    assert res["status"] == "VOIDED_SLA_FAILURE_FULL_BUYER_REFUND"
    assert res["financial_summary"]["final_net_settled_usd"] == 0.0
    endpoints = [t["endpoint"] for t in res["paypal_telemetry"]]
    assert endpoints[-2].endswith("/void") and endpoints[-1].endswith("/cancel")


def test_live_sandbox_error_halts_instead_of_faking_success(monkeypatch, tmp_path: Path):
    def fake_urlopen(req, timeout=0):
        if req.full_url.endswith("/v1/oauth2/token"):
            return io.BytesIO(b'{"access_token": "t", "expires_in": 32400}')
        raise urllib.error.HTTPError(req.full_url, 422, "Unprocessable", {}, io.BytesIO(b'{"name": "INVALID_REQUEST"}'))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = PayPalSandboxClient(client_id="id", client_secret="secret", mode="live", vault_path=tmp_path / "v.json")
    res = PactPalClearinghouseEngine(client=client, use_claude_agents=False).execute_pact_lifecycle(sla_outcome_mode="green_payout")
    assert res["status"] == "HALTED_ON_PAYPAL_SANDBOX_ERROR"
    assert res["error"]["http_status"] == 422
    assert res["error"]["paypal_response"] == {"name": "INVALID_REQUEST"}
    assert res["paypal_telemetry"][-1]["summary"].startswith("FAILED")


def test_revoked_token_is_refreshed_and_call_retried(monkeypatch, tmp_path: Path):
    tokens = iter(["old", "new"])
    seen = []

    class Resp(io.BytesIO):
        status = 201

    def fake_urlopen(req, timeout=0):
        if req.full_url.endswith("/v1/oauth2/token"):
            return io.BytesIO(('{"access_token": "%s", "expires_in": 32400}' % next(tokens)).encode())
        seen.append(req.get_header("Authorization"))
        if req.get_header("Authorization") == "Bearer old":
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"{}"))
        return Resp(b'{"id": "ORDER1", "status": "CREATED"}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = PayPalSandboxClient(client_id="id", client_secret="secret", mode="live", vault_path=tmp_path / "v.json")
    body, tel = client.invoke_sandbox_endpoint("P", "Orders v2", "POST", "/v2/checkout/orders", "create_order", {}, "{id}")
    assert body["id"] == "ORDER1" and tel.source == "LIVE SANDBOX"
    assert seen == ["Bearer old", "Bearer new"]


class FakeLiveSandbox:
    """Stands in for a live Sandbox client; dispute state is advanced by the test like a real buyer would."""

    is_live = True

    def __init__(self):
        self.dispute = None  # None -> no dispute yet; then a dict like PayPal's GET dispute response
        self.calls = []

    def invoke_sandbox_endpoint(self, pact_id, api_family, http_method, endpoint, agent_toolkit_tool, payload, summary_template):
        from src.apimatic_sdk.models import PayPalApiCallTelemetry
        self.calls.append((http_method, endpoint, payload))
        if endpoint.startswith("/v1/customer/disputes?"):
            body = {"items": [{"dispute_id": "PP-R-TEST"}] if self.dispute else []}
        elif endpoint == "/v1/customer/disputes/PP-R-TEST":
            body = {"id": "PP-R-TEST", **self.dispute}
        elif endpoint.endswith("/make-offer"):
            self.dispute["offer"] = {"seller_offered_amount": payload["offer_amount"]}
            body = {"id": "PP-R-TEST"}
        elif http_method == "GET" and endpoint.startswith("/v2/checkout/orders/"):
            body = {"id": "ORDER", "status": "APPROVED"}
        elif endpoint.endswith("/capture"):
            body = {"id": "CAPTURE1", "status": "COMPLETED"}
        else:
            body = {"id": "X"}
        tel = PayPalApiCallTelemetry(len(self.calls), api_family, http_method, endpoint, agent_toolkit_tool,
                                     "rid", body.get("id", "X"), 200, False, 0.0, "ok", body, "LIVE SANDBOX")
        return body, tel


def test_live_amber_waits_for_dispute_offers_in_inquiry_then_records_resolution():
    sandbox = FakeLiveSandbox()
    engine = PactPalClearinghouseEngine(client=sandbox, use_claude_agents=False)
    run = lambda: engine.execute_pact_lifecycle(sla_outcome_mode="amber_dispute", run_id="t1")

    assert run()["status"] == "AWAITING_BUYER_DISPUTE"

    sandbox.dispute = {"status": "WAITING_FOR_SELLER_RESPONSE", "dispute_life_cycle_stage": "INQUIRY",
                       "reason": "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED"}
    waiting = run()
    assert waiting["status"] == "AWAITING_BUYER_OFFER_RESPONSE"
    offers = [p for m, e, p in sandbox.calls if e.endswith("/make-offer")]
    assert offers == [{"note": offers[0]["note"], "offer_type": "REFUND",
                       "offer_amount": {"currency_code": "USD", "value": "93.60"}}]

    run()  # an existing offer is never re-sent
    assert len([1 for _, e, _ in sandbox.calls if e.endswith("/make-offer")]) == 1

    sandbox.dispute.update(status="RESOLVED", dispute_outcome={"outcome_code": "RESOLVED_BUYER_FAVOUR"})
    done = run()
    assert done["status"] == "RESOLVED_VIA_PARTIAL_CURE_COURTROOM"
    assert done["dispute_courtroom"]["net_merchant_settlement_usd"] == 296.40
    assert not any("require-evidence" in e or "adjudicate" in e for _, e, _ in sandbox.calls)


def test_nvidia_backend_parses_offer_and_retries_malformed_reply(monkeypatch):
    import httpx
    replies = iter([
        "Sure! Here is my offer: not json",
        '{"price_usd": 405, "early_discount_pct": 6, "sla_guarantee_score": 92, "accept_counterparty_offer": false, "rationale": "fair"}',
    ])
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": next(replies)}}]})

    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert negotiation_agents.ai_provider() == "nvidia"
    offer = negotiation_agents._nvidia_offer_fn()("system", "transcript")
    assert offer.price_usd == 405 and len(sent) == 2
    assert sent[0].headers["Authorization"] == "Bearer nvapi-test"
    assert sent[0].url.path == "/v1/chat/completions"
