"""Strongly-typed PayPal Sandbox API models & HMAC-SHA256 SpendMandateToken Guardrail.

Generated & validated against PayPal OpenAPI specifications (Orders v2, Invoicing v2,
Payouts Batch v1, and Customer Disputes v1) using APIMatic schema validation patterns.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any

MANDATE_SECRET = os.environ.get("PACTPAL_MANDATE_SECRET", "pactpal-sandbox-hmac-key-2026")


@dataclass
class SpendMandateToken:
    """Cryptographic spend approval token constraining autonomous agent PayPal calls."""
    mandate_id: str
    buyer_agent_id: str
    allowed_merchant_email: str
    max_budget_usd: float
    min_sla_score_for_full_capture: float
    currency_code: str
    issued_at: int
    expires_at: int
    signature: str = ""

    def compute_signature(self, secret: str = MANDATE_SECRET) -> str:
        payload = (
            f"{self.mandate_id}:{self.buyer_agent_id}:{self.allowed_merchant_email}:"
            f"{self.max_budget_usd:.2f}:{self.min_sla_score_for_full_capture:.1f}:"
            f"{self.currency_code}:{self.issued_at}:{self.expires_at}"
        ).encode("utf-8")
        return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    @classmethod
    def issue(
        cls,
        mandate_id: str,
        buyer_agent_id: str,
        allowed_merchant_email: str,
        max_budget_usd: float,
        min_sla_score_for_full_capture: float = 90.0,
        currency_code: str = "USD",
        ttl_seconds: int = 86400,
    ) -> SpendMandateToken:
        now = int(time.time())
        token = cls(
            mandate_id=mandate_id,
            buyer_agent_id=buyer_agent_id,
            allowed_merchant_email=allowed_merchant_email,
            max_budget_usd=round(float(max_budget_usd), 2),
            min_sla_score_for_full_capture=round(float(min_sla_score_for_full_capture), 1),
            currency_code=currency_code.upper(),
            issued_at=now,
            expires_at=now + ttl_seconds,
        )
        token.signature = token.compute_signature()
        return token

    def verify_for_execution(self, requested_amount_usd: float, merchant_email: str) -> tuple[bool, str]:
        expected_sig = self.compute_signature()
        if not hmac.compare_digest(self.signature, expected_sig):
            return False, "INVALID_HMAC_SIGNATURE: SpendMandateToken signature mismatch."
        if int(time.time()) > self.expires_at:
            return False, "MANDATE_EXPIRED: SpendMandateToken TTL has elapsed."
        if merchant_email.lower() != self.allowed_merchant_email.lower():
            return False, f"UNAUTHORIZED_PAYEE: '{merchant_email}' not in mandate allowlist."
        if round(requested_amount_usd, 2) > round(self.max_budget_usd, 2):
            return (
                False,
                f"BUDGET_CEILING_EXCEEDED: Requested ${requested_amount_usd:.2f} exceeds "
                f"mandate cap of ${self.max_budget_usd:.2f}.",
            )
        return True, "VERIFIED"


@dataclass
class InvoiceConditionalRuleSpec:
    """PayPal Invoicing v2 Conditional Pricing Rule (/v2/invoicing/invoices/{id}/conditional-rules)."""
    rule_type: str  # "EARLY_PAYMENT_DISCOUNT" | "SLA_MILESTONE_PENALTY"
    trigger_condition: str
    discount_percent: float
    auto_cancel_after_hours: int
    pay_by_bank_enabled: bool = True


@dataclass
class PayoutRecipientSplit:
    """PayPal Batch Payouts v1 item (/v1/payments/payouts)."""
    role: str
    receiver_email: str
    split_percent: float
    amount_usd: float
    note: str


@dataclass
class PayPalApiCallTelemetry:
    """Structured telemetry record for every PayPal Sandbox REST & Agent Toolkit invocation."""
    step_order: int
    api_family: str
    http_method: str
    endpoint: str
    agent_toolkit_tool: str
    paypal_request_id: str
    resource_id: str
    status_code: int
    cache_hit: bool
    latency_ms: float
    summary: str
    raw_Preview: dict[str, Any] = field(default_factory=dict)
    source: str = "SIMULATED"  # LIVE SANDBOX | SIMULATED | VAULT REPLAY (...)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
