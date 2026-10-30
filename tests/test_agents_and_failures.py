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
    monkeypatch.setattr(negotiation_agents, "_claude_offer_fn", lambda: (lambda s, t: None))
    client = PayPalSandboxClient(client_id="", client_secret="", mode="hybrid", vault_path=tmp_path / "v.json")
    res = PactPalClearinghouseEngine(client=client, use_claude_agents=True).execute_pact_lifecycle(sla_outcome_mode="green_payout")
    assert res["negotiation_engine"].startswith("scripted")
    assert res["financial_summary"]["negotiated_invoice_usd"] == 390.00


def test_claude_price_flows_into_invoice_and_scaled_line_items(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(negotiation_agents, "_claude_offer_fn",
                        lambda: scripted_offers(offer(480), offer(400.10), offer(0, accept=True)))
    client = PayPalSandboxClient(client_id="", client_secret="", mode="hybrid", vault_path=tmp_path / "v.json")
    res = PactPalClearinghouseEngine(client=client, use_claude_agents=True).execute_pact_lifecycle(sla_outcome_mode="green_payout")
    assert res["negotiation_engine"] == negotiation_agents.CLAUDE_MODEL
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
