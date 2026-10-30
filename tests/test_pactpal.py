"""Automated Pytest Verification Suite for PactPal PayPal Sandbox Clearinghouse."""
from __future__ import annotations

from pathlib import Path

from src.backend.pactpal_engine import PactPalClearinghouseEngine
from src.backend.paypal_sandbox_client import PayPalSandboxClient


def test_green_sla_full_capture_and_3_way_batch_payout(tmp_path: Path) -> None:
    vault_file = tmp_path / "test_paypal_vault.json"
    client = PayPalSandboxClient(client_id="", client_secret="", mode="hybrid", vault_path=vault_file)
    engine = PactPalClearinghouseEngine(client=client)

    res = engine.execute_pact_lifecycle(
        scenario_key="dermotwin_luxury_bundle",
        sla_outcome_mode="green_payout",
    )

    assert res["status"] == "SETTLED_FULL_SLA_PAYOUT"
    assert res["financial_summary"]["negotiated_invoice_usd"] == 372.00
    assert res["financial_summary"]["final_net_settled_usd"] == 372.00
    assert len(res["payout_splits"]) == 3
    total_split = round(sum(s["amount_usd"] for s in res["payout_splits"]), 2)
    assert total_split == 372.00
    assert len(res["paypal_telemetry"]) == 9  # + invoice send step


def test_amber_sla_autonomous_sandbox_dispute_courtroom_and_vault_replay(tmp_path: Path) -> None:
    vault_file = tmp_path / "test_paypal_vault.json"
    client = PayPalSandboxClient(client_id="", client_secret="", mode="hybrid", vault_path=vault_file)
    engine = PactPalClearinghouseEngine(client=client)

    res1 = engine.execute_pact_lifecycle(
        scenario_key="b2b_gpu_inference_cluster",
        sla_outcome_mode="amber_dispute",
    )

    assert res1["status"] == "RESOLVED_VIA_PARTIAL_CURE_COURTROOM"
    assert res1["sla_verdict"]["overall_sla_score"] == 76.0
    assert res1["dispute_courtroom"] is not None
    # 24% partial-cure refund on $390.00 = $93.60 refund, $296.40 net settlement
    assert res1["financial_summary"]["partial_cure_refund_usd"] == 93.60
    assert res1["financial_summary"]["final_net_settled_usd"] == 296.40
    assert len(res1["paypal_telemetry"]) == 11  # + invoice send step

    # Second identical execution must hit SHA-256 Replay Vault 100% of the time
    res2 = engine.execute_pact_lifecycle(
        scenario_key="b2b_gpu_inference_cluster",
        sla_outcome_mode="amber_dispute",
    )
    assert all(call["cache_hit"] is True for call in res2["paypal_telemetry"])


def test_cryptographic_spend_mandate_blocks_over_budget_execution(tmp_path: Path) -> None:
    vault_file = tmp_path / "test_paypal_vault.json"
    client = PayPalSandboxClient(client_id="", client_secret="", mode="hybrid", vault_path=vault_file)
    engine = PactPalClearinghouseEngine(client=client)

    # Set budget cap ($300) below negotiated contract ($390) -> must block before any PayPal call runs
    blocked = engine.execute_pact_lifecycle(
        scenario_key="b2b_gpu_inference_cluster",
        sla_outcome_mode="green_payout",
        override_budget_cap_usd=300.00,
    )
    assert blocked["status"] == "BLOCKED_BY_SPEND_MANDATE_GUARDRAIL"
    assert blocked["mandate_verification"]["allowed"] is False
    assert len(blocked["paypal_telemetry"]) == 0
