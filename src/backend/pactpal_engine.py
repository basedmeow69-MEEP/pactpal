"""PactPal Core Engine: A2A Nash Deal-Desk, Telemetry Escrow & Sandbox Dispute Courtroom."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.apimatic_sdk.models import (
    InvoiceConditionalRuleSpec,
    PayPalApiCallTelemetry,
    PayoutRecipientSplit,
    SpendMandateToken,
)
from src.backend.negotiation_agents import CLAUDE_MODEL, claude_available, run_claude_negotiation
from src.backend.paypal_sandbox_client import PayPalSandboxClient, PayPalSandboxError


@dataclass
class NegotiationTurn:
    round_num: int
    speaker_agent: str
    role_badge: str
    proposed_price_usd: float
    early_discount_pct: float
    sla_guarantee_score: float
    rationale: str


@dataclass
class SlaAuditVerdict:
    overall_sla_score: float
    epistemic_zone: str  # "GREEN_FULL_CAPTURE" | "AMBER_PARTIAL_CURE_DISPUTE" | "RED_AUTO_VOID"
    checks_passed: list[str]
    checks_failed: list[str]
    defect_ratio: float
    recommended_partial_refund_usd: float
    net_merchant_capture_usd: float


class PactPalClearinghouseEngine:
    """Orchestrates A2A Negotiation, PayPal Conditional Invoicing, Escrow, Payouts & Disputes."""

    def __init__(self, client: PayPalSandboxClient | None = None, use_claude_agents: bool | None = None) -> None:
        self.client = client or PayPalSandboxClient()
        self.use_claude_agents = claude_available() if use_claude_agents is None else use_claude_agents

    @staticmethod
    def scale_line_items(items: list[dict[str, Any]], total_usd: float) -> list[dict[str, Any]]:
        """Rescale line items so the invoice total matches the negotiated price to the cent."""
        values = [float(i["unit_amount"]["value"]) * int(i["quantity"]) for i in items]
        base = sum(values)
        if abs(base - total_usd) < 0.005:
            return items
        scaled = [round(v * total_usd / base, 2) for v in values]
        scaled[-1] = round(total_usd - sum(scaled[:-1]), 2)
        return [
            {**item, "unit_amount": {**item["unit_amount"], "value": f"{v / int(item['quantity']):.2f}"}}
            for item, v in zip(items, scaled)
        ]

    @staticmethod
    def get_scenarios() -> dict[str, dict[str, Any]]:
        """Pre-seeded commercial scenarios (including Sprint 2 DermoTwin Cart Bridge)."""
        return {
            "b2b_gpu_inference_cluster": {
                "pact_id": "PACT-2026-GPU-01",
                "title": "Scenario 1: Autonomous B2B Fine-Tuning & GPU Inference SLA Contract",
                "buyer_agent_id": "agent.procurement.finops@enterprise.ai",
                "merchant_email": "treasury@nebius-compute-merchant.sandbox.paypal.com",
                "sub_agent_email": "weights-auditor@verifier-node.sandbox.paypal.com",
                "referrer_email": "guild-royalty@coffeekiller.sandbox.paypal.com",
                "initial_ask_usd": 480.00,
                "buyer_max_budget_usd": 420.00,
                "negotiated_price_usd": 390.00,
                "early_discount_pct": 8.0,
                "line_items": [
                    {"name": "LoRA Checkpoint Distillation (50k Rows)", "quantity": "1", "unit_amount": {"currency_code": "USD", "value": "240.00"}},
                    {"name": "Dedicated Low-Latency Inference Slot (24h SLA <150ms)", "quantity": "1", "unit_amount": {"currency_code": "USD", "value": "150.00"}},
                ],
                "default_sla_mode": "amber_dispute",
            },
            "dermotwin_luxury_bundle": {
                "pact_id": "PACT-2026-DERM-02",
                "title": "Scenario 2: DermoTwin Biometric-Harmonized 5-Category Retail Escrow (Sprint 2 Bridge)",
                "buyer_agent_id": "agent.stylist.concierge@dermotwin.ai",
                "merchant_email": "orders@atelier-vera-luxury.sandbox.paypal.com",
                "sub_agent_email": "formulation@aura-labs-derm.sandbox.paypal.com",
                "referrer_email": "vto-royalty@lumen-jewelry.sandbox.paypal.com",
                "initial_ask_usd": 410.00,
                "buyer_max_budget_usd": 385.00,
                "negotiated_price_usd": 372.00,
                "early_discount_pct": 6.0,
                "line_items": [
                    {"name": "Aura Labs Panthenol + Cica Barrier Duo (Skin AI Verified)", "quantity": "1", "unit_amount": {"currency_code": "USD", "value": "82.00"}},
                    {"name": "Atelier Vera Sage-Emerald Cashmere Drape + Satin Look Duo", "quantity": "1", "unit_amount": {"currency_code": "USD", "value": "204.00"}},
                    {"name": "Lumen 18K Brushed Gold Pearl Drop Earrings", "quantity": "1", "unit_amount": {"currency_code": "USD", "value": "86.00"}},
                ],
                "default_sla_mode": "green_payout",
            },
        }

    @staticmethod
    def run_nash_negotiation(scenario: dict[str, Any]) -> tuple[list[NegotiationTurn], InvoiceConditionalRuleSpec]:
        ask = float(scenario["initial_ask_usd"])
        cap = float(scenario["buyer_max_budget_usd"])
        settled = float(scenario["negotiated_price_usd"])
        disc = float(scenario["early_discount_pct"])

        turns = [
            NegotiationTurn(
                round_num=1,
                speaker_agent="Seller Deal-Desk Agent",
                role_badge="MERCHANT_AI",
                proposed_price_usd=ask,
                early_discount_pct=2.0,
                sla_guarantee_score=85.0,
                rationale=f"Opening list quote at ${ask:.2f} USD with standard 85% delivery SLA.",
            ),
            NegotiationTurn(
                round_num=2,
                speaker_agent="Buyer Procurement Agent",
                role_badge="BUYER_AI",
                proposed_price_usd=round(settled * 0.94, 2),
                early_discount_pct=10.0,
                sla_guarantee_score=92.0,
                rationale=(
                    f"Hard SpendMandateToken cap is ${cap:.2f}. Counter-proposing ${settled * 0.94:.2f} "
                    "conditioned on >=90% automated SLA verification and PayPal Orders v2 Escrow Hold."
                ),
            ),
            NegotiationTurn(
                round_num=3,
                speaker_agent="Nash Clearinghouse Mediator",
                role_badge="PACT_LOCKED",
                proposed_price_usd=settled,
                early_discount_pct=disc,
                sla_guarantee_score=90.0,
                rationale=(
                    f"Nash equilibrium converged at ${settled:.2f} USD. Attaching PayPal Invoices v2 "
                    f"Conditional Rule ({disc:.1f}% early-settlement incentive + automatic partial-cure "
                    "dispute clause if SLA falls between 60% and 89%)."
                ),
            ),
        ]
        rule = InvoiceConditionalRuleSpec(
            rule_type="EARLY_PAYMENT_AND_SLA_ESCROW_RULE",
            trigger_condition="SLA_SCORE_GE_90_WITHIN_24H",
            discount_percent=disc,
            auto_cancel_after_hours=48,
            pay_by_bank_enabled=True,
        )
        return turns, rule

    @staticmethod
    def evaluate_sla_telemetry(total_usd: float, simulation_mode: str) -> SlaAuditVerdict:
        """Evaluate delivery telemetry and route to Green (Payout) or Amber (Dispute Courtroom)."""
        if simulation_mode == "green_payout":
            return SlaAuditVerdict(
                overall_sla_score=96.4,
                epistemic_zone="GREEN_FULL_CAPTURE",
                checks_passed=[
                    "PayPal Shipment Tracking status verified: DELIVERED (Carrier signature matched)",
                    "Artifact SHA-256 checksum & schema contract 100% compliant",
                    "p95 latency / biometric harmony benchmark exceeded 90.0 threshold (96.4%)",
                ],
                checks_failed=[],
                defect_ratio=0.0,
                recommended_partial_refund_usd=0.0,
                net_merchant_capture_usd=round(total_usd, 2),
            )

        if simulation_mode == "red_void":
            return SlaAuditVerdict(
                overall_sla_score=41.0,
                epistemic_zone="RED_AUTO_VOID",
                checks_passed=["Tracking payload received via PayPal Tracker API"],
                checks_failed=[
                    "SLA Breach #1: Deliverable failed 29 of 50 validation items (58% defect ratio)",
                    "SLA Breach #2: Delivery landed 31h after the contracted 24h window",
                ],
                defect_ratio=1.0,
                recommended_partial_refund_usd=round(total_usd, 2),
                net_merchant_capture_usd=0.0,
            )

        # Amber Dispute Mode: Partial SLA breach (76.0% score -> 24% mathematical partial-cure offer)
        defect_ratio = 0.24
        refund_usd = round(total_usd * defect_ratio, 2)
        net_usd = round(total_usd - refund_usd, 2)
        return SlaAuditVerdict(
            overall_sla_score=76.0,
            epistemic_zone="AMBER_PARTIAL_CURE_DISPUTE",
            checks_passed=[
                "Primary deliverable & tracking payload received via PayPal Tracker API",
                "Core functional tests passed (38/50 assertions)",
            ],
            checks_failed=[
                "SLA Breach #1: Tail p95 latency spiked to 218ms (Contract ceiling: <=150ms)",
                "SLA Breach #2: 12 of 50 validation items required fallback remediation (24% defect ratio)",
            ],
            defect_ratio=defect_ratio,
            recommended_partial_refund_usd=refund_usd,
            net_merchant_capture_usd=net_usd,
        )

    def execute_pact_lifecycle(
        self,
        scenario_key: str = "b2b_gpu_inference_cluster",
        sla_outcome_mode: str | None = None,
        override_budget_cap_usd: float | None = None,
    ) -> dict[str, Any]:
        """Run the complete 5-Stage PactPal lifecycle across PayPal Sandbox APIs."""
        scenarios = self.get_scenarios()
        scenario = scenarios.get(scenario_key, scenarios["b2b_gpu_inference_cluster"])
        pact_id = scenario["pact_id"]
        outcome_mode = sla_outcome_mode or scenario["default_sla_mode"]
        settled_usd = float(scenario["negotiated_price_usd"])
        budget_cap = float(override_budget_cap_usd) if override_budget_cap_usd is not None else float(scenario["buyer_max_budget_usd"])

        # Stage 1: A2A Nash Negotiation (Claude buyer/seller agents when an Anthropic key is configured)
        turns, cond_rule = self.run_nash_negotiation(scenario)
        negotiation_engine = "scripted (set ANTHROPIC_API_KEY for Claude agents)"
        ai_deal = run_claude_negotiation({**scenario, "buyer_max_budget_usd": budget_cap}) if self.use_claude_agents else None
        if ai_deal:
            settled_usd = ai_deal["price_usd"]
            turns = [NegotiationTurn(**t) for t in ai_deal["turns"]]
            cond_rule.discount_percent = ai_deal["early_discount_pct"]
            negotiation_engine = CLAUDE_MODEL
        line_items = self.scale_line_items(scenario["line_items"], settled_usd)

        # Stage 2: Mint & Verify Cryptographic SpendMandateToken
        mandate = SpendMandateToken.issue(
            mandate_id=f"MND-{pact_id}",
            buyer_agent_id=scenario["buyer_agent_id"],
            allowed_merchant_email=scenario["merchant_email"],
            max_budget_usd=budget_cap,
            min_sla_score_for_full_capture=90.0,
        )
        mandate_ok, mandate_msg = mandate.verify_for_execution(settled_usd, scenario["merchant_email"])
        if not mandate_ok:
            return {
                "pact_id": pact_id,
                "status": "BLOCKED_BY_SPEND_MANDATE_GUARDRAIL",
                "negotiation_engine": negotiation_engine,
                "mandate_verification": {"allowed": False, "reason": mandate_msg, "mandate": asdict(mandate)},
                "negotiation_turns": [asdict(t) for t in turns],
                "paypal_telemetry": [],
            }

        telemetry_log: list[PayPalApiCallTelemetry] = []
        try:
            return self._run_paypal_stages(
                scenario, pact_id, outcome_mode, settled_usd, line_items, turns, cond_rule,
                mandate, mandate_msg, negotiation_engine, telemetry_log,
            )
        except PayPalSandboxError as exc:
            telemetry_log.append(exc.telemetry)
            return {
                "pact_id": pact_id,
                "scenario_title": scenario["title"],
                "status": "HALTED_ON_PAYPAL_SANDBOX_ERROR",
                "error": {"endpoint": exc.telemetry.endpoint, "http_status": exc.status, "paypal_response": exc.body},
                "negotiation_engine": negotiation_engine,
                "mandate_verification": {"allowed": True, "reason": mandate_msg, "mandate": asdict(mandate)},
                "negotiation_turns": [asdict(t) for t in turns],
                "paypal_telemetry": [t.to_dict() for t in telemetry_log],
            }

    def _run_paypal_stages(
        self,
        scenario: dict[str, Any],
        pact_id: str,
        outcome_mode: str,
        settled_usd: float,
        line_items: list[dict[str, Any]],
        turns: list[NegotiationTurn],
        cond_rule: InvoiceConditionalRuleSpec,
        mandate: SpendMandateToken,
        mandate_msg: str,
        negotiation_engine: str,
        telemetry_log: list[PayPalApiCallTelemetry],
    ) -> dict[str, Any]:

        # Call 1 [Invoices v2]: Create Draft & Send Invoice with PAY_BY_BANK
        inv_res, inv_tel = self.client.invoke_sandbox_endpoint(
            pact_id=pact_id,
            api_family="Invoices v2",
            http_method="POST",
            endpoint="/v2/invoicing/invoices",
            agent_toolkit_tool="create_invoice",
            payload={
                "detail": {"currency_code": "USD", "note": f"PactPal A2A Contract {pact_id}"},
                "invoicer": {"email_address": scenario["merchant_email"]},
                "items": line_items,
                "amount": {"currency_code": "USD", "value": f"{settled_usd:.2f}"},
            },
            summary_template="Created PayPal Sandbox Invoice {id} with PAY_BY_BANK enabled",
        )
        telemetry_log.append(inv_tel)
        invoice_id = inv_res["id"]

        # Call 2 [Invoices v2 Conditional Rules]: Attach programmable discount/SLA rule
        _, rule_tel = self.client.invoke_sandbox_endpoint(
            pact_id=pact_id,
            api_family="Invoices v2 Conditional Rules",
            http_method="POST",
            endpoint=f"/v2/invoicing/invoices/{invoice_id}/conditional-rules",
            agent_toolkit_tool="create_conditional_rules_for_invoice",
            payload=asdict(cond_rule),
            summary_template="Attached Conditional Pricing Rule {id} (early discount & SLA gate)",
        )
        telemetry_log.append(rule_tel)

        # Call 3 [Invoices v2 QR Code]: Generate mobile scannable QR code
        qr_res, qr_tel = self.client.invoke_sandbox_endpoint(
            pact_id=pact_id,
            api_family="Invoices v2 QR",
            http_method="POST",
            endpoint=f"/v2/invoicing/invoices/{invoice_id}/generate-qr-code",
            agent_toolkit_tool="generate_invoice_qr_code",
            payload={"width": 300, "height": 300, "action": "pay"},
            summary_template="Generated PayPal Invoice QR Code {id}",
        )
        telemetry_log.append(qr_tel)

        # Call 4 [Orders v2]: Create Order with intent="AUTHORIZE"
        ord_res, ord_tel = self.client.invoke_sandbox_endpoint(
            pact_id=pact_id,
            api_family="Orders v2",
            http_method="POST",
            endpoint="/v2/checkout/orders",
            agent_toolkit_tool="create_order",
            payload={
                "intent": "AUTHORIZE",
                "purchase_units": [
                    {
                        "reference_id": pact_id,
                        "custom_id": mandate.mandate_id,
                        "amount": {"currency_code": "USD", "value": f"{settled_usd:.2f}"},
                    }
                ],
            },
            summary_template="Created PayPal Order {id} (intent=AUTHORIZE)",
        )
        telemetry_log.append(ord_tel)
        order_id = ord_res["id"]

        # Call 5 [Orders v2 Authorize]: Lock buyer funds in PayPal Escrow Hold
        auth_res, auth_tel = self.client.invoke_sandbox_endpoint(
            pact_id=pact_id,
            api_family="Orders v2 Auth Hold",
            http_method="POST",
            endpoint=f"/v2/checkout/orders/{order_id}/authorize",
            agent_toolkit_tool="pay_order",
            payload={"mandate_signature": mandate.signature[:24]},
            summary_template=f"Locked Escrow Authorization Hold {{id}} (${settled_usd:.2f})",
        )
        telemetry_log.append(auth_tel)
        auth_id = auth_res["id"]

        # Call 6 [Shipment Tracking v1]: Register verifiable delivery & SLA artifact hash
        _, trk_tel = self.client.invoke_sandbox_endpoint(
            pact_id=pact_id,
            api_family="Shipment Tracking v1",
            http_method="POST",
            endpoint="/v1/shipping/trackers-batch",
            agent_toolkit_tool="create_shipment_tracking",
            payload={
                "transaction_id": auth_id,
                "status": "DELIVERED",
                "carrier": "PACTPAL_TELEMETRY_ORACLE",
            },
            summary_template="Registered PayPal Delivery & SLA Telemetry Tracker {id}",
        )
        telemetry_log.append(trk_tel)

        # Stage 3: Evaluate SLA Telemetry
        verdict = self.evaluate_sla_telemetry(settled_usd, outcome_mode)
        payout_splits: list[PayoutRecipientSplit] = []
        dispute_courtroom_record: dict[str, Any] | None = None

        if verdict.epistemic_zone == "GREEN_FULL_CAPTURE":
            # Stage 4A: Full Order Capture + 3-Way Multiparty Batch Payout
            _, cap_tel = self.client.invoke_sandbox_endpoint(
                pact_id=pact_id,
                api_family="Payments v2 Capture",
                http_method="POST",
                endpoint=f"/v2/payments/authorizations/{auth_id}/capture",
                agent_toolkit_tool="pay_order",
                payload={"amount": {"currency_code": "USD", "value": f"{settled_usd:.2f}"}, "final_capture": True},
                summary_template=f"Captured 100% of Escrow (${settled_usd:.2f}) under Capture {{id}}",
            )
            telemetry_log.append(cap_tel)

            split_1 = round(settled_usd * 0.75, 2)
            split_2 = round(settled_usd * 0.20, 2)
            split_3 = round(settled_usd - split_1 - split_2, 2)
            payout_splits = [
                PayoutRecipientSplit("Primary Merchant (75%)", scenario["merchant_email"], 75.0, split_1, "Primary SLA settlement"),
                PayoutRecipientSplit("Sub-Agent Fulfillment (20%)", scenario["sub_agent_email"], 20.0, split_2, "Autonomous verifier & compute split"),
                PayoutRecipientSplit("Guild Referral Partner (5%)", scenario["referrer_email"], 5.0, split_3, "Clearinghouse royalty"),
            ]
            _, pay_tel = self.client.invoke_sandbox_endpoint(
                pact_id=pact_id,
                api_family="Batch Payouts v1",
                http_method="POST",
                endpoint="/v1/payments/payouts",
                agent_toolkit_tool="create_batch_payout",
                payload={
                    "sender_batch_header": {"sender_batch_id": f"BATCH-{pact_id}", "email_subject": "PactPal Multiparty Settlement"},
                    "items": [asdict(s) for s in payout_splits],
                },
                summary_template="Executed 3-Way Multiparty Batch Payout {id}",
            )
            telemetry_log.append(pay_tel)
            final_status = "SETTLED_FULL_SLA_PAYOUT"

        elif verdict.epistemic_zone == "RED_AUTO_VOID":
            # Stage 4C: Void the escrow hold and cancel the invoice; buyer keeps 100% of funds
            _, void_tel = self.client.invoke_sandbox_endpoint(
                pact_id=pact_id,
                api_family="Payments v2 Void",
                http_method="POST",
                endpoint=f"/v2/payments/authorizations/{auth_id}/void",
                agent_toolkit_tool="void_authorization",
                payload={},
                summary_template=f"Voided Escrow Authorization {auth_id}: ${settled_usd:.2f} released to buyer",
            )
            telemetry_log.append(void_tel)
            _, cancel_tel = self.client.invoke_sandbox_endpoint(
                pact_id=pact_id,
                api_family="Invoices v2 Cancel",
                http_method="POST",
                endpoint=f"/v2/invoicing/invoices/{invoice_id}/cancel",
                agent_toolkit_tool="cancel_sent_invoice",
                payload={"subject": f"PactPal {pact_id} voided", "note": "; ".join(verdict.checks_failed), "send_to_invoicer": True},
                summary_template=f"Cancelled Invoice {invoice_id} after SLA failure",
            )
            telemetry_log.append(cancel_tel)
            final_status = "VOIDED_SLA_FAILURE_FULL_BUYER_REFUND"

        else:
            # Stage 4B: Autonomous Sandbox Dispute Courtroom & Partial-Cure Settlement
            disp_res, disp_tel = self.client.invoke_sandbox_endpoint(
                pact_id=pact_id,
                api_family="Disputes v1 (Sandbox)",
                http_method="POST",
                endpoint=f"/v1/customer/disputes/PP-D-{pact_id[-6:]}/require-evidence",
                agent_toolkit_tool="get_dispute",
                payload={"disputed_transactions": [{"seller_transaction_id": auth_id}], "reason": "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED"},
                summary_template="Triggered Sandbox Dispute {id} into REQUIRED_ACTION state",
            )
            telemetry_log.append(disp_tel)
            dispute_id = disp_res["id"]

            _, evid_tel = self.client.invoke_sandbox_endpoint(
                pact_id=pact_id,
                api_family="Disputes v1 Evidence",
                http_method="POST",
                endpoint=f"/v1/customer/disputes/{dispute_id}/provide-evidence",
                agent_toolkit_tool="provide_dispute_evidence",
                payload={
                    "evidence_type": "PROOF_OF_FULFILLMENT_AND_SLA_TELEMETRY",
                    "notes": "; ".join(verdict.checks_failed),
                },
                summary_template="Uploaded Cryptographic SLA Breach Telemetry Evidence {id}",
            )
            telemetry_log.append(evid_tel)

            offer_res, offer_tel = self.client.invoke_sandbox_endpoint(
                pact_id=pact_id,
                api_family="Disputes v1 Make Offer",
                http_method="POST",
                endpoint=f"/v1/customer/disputes/{dispute_id}/make-offer",
                agent_toolkit_tool="make_dispute_offer",
                payload={
                    "offer": {
                        "offer_type": "REFUND",
                        "offer_amount": {"currency_code": "USD", "value": f"{verdict.recommended_partial_refund_usd:.2f}"},
                        "note": (
                            f"Autonomous Seller Defense AI proposes 24% Partial-Cure Credit "
                            f"(${verdict.recommended_partial_refund_usd:.2f} refund; "
                            f"${verdict.net_merchant_capture_usd:.2f} net capture) matching exact SLA defect ratio."
                        ),
                    }
                },
                summary_template=f"Seller AI Proposed Partial-Cure Offer {{id}} (-${verdict.recommended_partial_refund_usd:.2f})",
            )
            telemetry_log.append(offer_tel)

            adj_res, adj_tel = self.client.invoke_sandbox_endpoint(
                pact_id=pact_id,
                api_family="Disputes v1 Adjudicate",
                http_method="POST",
                endpoint=f"/v1/customer/disputes/{dispute_id}/adjudicate",
                agent_toolkit_tool="accept_dispute_claim",
                payload={
                    "adjudication_outcome": "BUYER_PAYOUT_PARTIAL_CURE",
                    "refund_amount": {"currency_code": "USD", "value": f"{verdict.recommended_partial_refund_usd:.2f}"},
                    "net_captured_amount": {"currency_code": "USD", "value": f"{verdict.net_merchant_capture_usd:.2f}"},
                },
                summary_template=f"Sandbox Courtroom Adjudicated {dispute_id}: Settled at ${verdict.net_merchant_capture_usd:.2f} net ({{id}})",
            )
            telemetry_log.append(adj_tel)

            dispute_courtroom_record = {
                "dispute_id": dispute_id,
                "reason": "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED (SLA 76.0% < 90.0% Gate)",
                "seller_offer_id": offer_res["id"],
                "partial_refund_usd": verdict.recommended_partial_refund_usd,
                "net_merchant_settlement_usd": verdict.net_merchant_capture_usd,
                "resolution_status": adj_res["dispute_outcome"],
            }
            final_status = "RESOLVED_VIA_PARTIAL_CURE_COURTROOM"

        return {
            "pact_id": pact_id,
            "scenario_title": scenario["title"],
            "status": final_status,
            "negotiation_engine": negotiation_engine,
            "financial_summary": {
                "initial_ask_usd": scenario["initial_ask_usd"],
                "negotiated_invoice_usd": settled_usd,
                "buyer_refund_or_savings_usd": round(
                    (scenario["initial_ask_usd"] - settled_usd) + verdict.recommended_partial_refund_usd, 2
                ),
                "partial_cure_refund_usd": verdict.recommended_partial_refund_usd,
                "final_net_settled_usd": verdict.net_merchant_capture_usd,
            },
            "mandate_verification": {"allowed": True, "reason": mandate_msg, "mandate": asdict(mandate)},
            "negotiation_turns": [asdict(t) for t in turns],
            "conditional_invoice_rule": asdict(cond_rule),
            "invoice_id": invoice_id,
            "order_id": order_id,
            "authorization_id": auth_id,
            "qr_code_svg_path": qr_res.get("qr_code_svg_path", "/api/qr/default.svg"),
            "sla_verdict": asdict(verdict),
            "payout_splits": [asdict(s) for s in payout_splits],
            "dispute_courtroom": dispute_courtroom_record,
            "paypal_telemetry": [t.to_dict() for t in telemetry_log],
        }
