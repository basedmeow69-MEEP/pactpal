"""HMAC-signed spend mandates: agents may only move money inside signed limits."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from decimal import Decimal


class MandateViolation(Exception):
    pass


@dataclass(frozen=True)
class SpendMandate:
    pact_id: str
    max_amount: str  # decimal string, e.g. "390.00"
    currency: str
    payee_email: str
    sla_rubric_sha256: str
    expires_at: int  # unix seconds


def _encode(mandate: SpendMandate) -> bytes:
    return json.dumps(asdict(mandate), sort_keys=True, separators=(",", ":")).encode()


def sign(mandate: SpendMandate, secret: str) -> str:
    payload = _encode(mandate)
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    return ".".join(base64.urlsafe_b64encode(part).decode().rstrip("=") for part in (payload, signature))


def verify(token: str, secret: str, *, now: float) -> SpendMandate:
    try:
        payload_b64, signature_b64 = token.split(".")
        payload = _b64decode(payload_b64)
        signature = _b64decode(signature_b64)
    except ValueError as exc:
        raise MandateViolation("malformed mandate") from exc
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise MandateViolation("bad mandate signature")
    mandate = SpendMandate(**json.loads(payload))
    if now >= mandate.expires_at:
        raise MandateViolation("mandate expired")
    return mandate


def authorize_spend(mandate: SpendMandate, *, amount: str, currency: str, payee_email: str) -> None:
    if currency != mandate.currency:
        raise MandateViolation(f"currency {currency} not allowed")
    if payee_email.lower() != mandate.payee_email.lower():
        raise MandateViolation("payee not in mandate")
    if Decimal(amount) > Decimal(mandate.max_amount):
        raise MandateViolation(f"{amount} exceeds mandate ceiling {mandate.max_amount}")


def _b64decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))
