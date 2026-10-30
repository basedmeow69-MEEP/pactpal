"""PayPal Developer Platform Sandbox Client with OAuth2 Auto-Refresh, Idempotency & SHA-256 Vault.

Integrates:
  1. OAuth 2.0 Client Credentials (/v1/oauth2/token) with pre-expiry refresh
  2. Invoices v2 (/v2/invoicing/invoices, /conditional-rules, /generate-qr-code)
  3. Orders v2 & Payments v2 (/v2/checkout/orders, /authorize, /v2/payments/authorizations/{id}/capture)
  4. Shipment Tracking v1 (/v1/shipping/trackers-batch)
  5. Batch Payouts v1 (/v1/payments/payouts)
  6. Customer Disputes v1 (/v1/customer/disputes, /require-evidence, /make-offer, /accept-offer, /adjudicate)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from src.apimatic_sdk.models import PayPalApiCallTelemetry

PAYPAL_SANDBOX_BASE = os.environ.get("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "hybrid").lower()  # "mock" | "hybrid" | "live"
VAULT_FILE = Path(os.environ.get("PAYPAL_VAULT_PATH", "vault/paypal_replay_vault.json"))


class PayPalSandboxError(Exception):
    """A live Sandbox call failed. Carries PayPal's real response so the UI shows the failure."""

    def __init__(self, status: int, body: Any, telemetry: PayPalApiCallTelemetry) -> None:
        super().__init__(f"PayPal Sandbox returned HTTP {status} for {telemetry.endpoint}")
        self.status = status
        self.body = body
        self.telemetry = telemetry


class PayPalSandboxClient:
    """Resilient PayPal Sandbox REST client with SHA-256 replay vault and idempotency."""

    def __init__(
        self,
        client_id: str = PAYPAL_CLIENT_ID,
        client_secret: str = PAYPAL_CLIENT_SECRET,
        base_url: str = PAYPAL_SANDBOX_BASE,
        mode: str = PAYPAL_MODE,
        vault_path: Path = VAULT_FILE,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.mode = mode
        self.vault_path = vault_path
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        self._vault: dict[str, dict[str, Any]] = self._load_vault()
        self._access_token: str = ""
        self._token_expires_at: float = 0.0
        self._call_counter: int = 0

    def _load_vault(self) -> dict[str, dict[str, Any]]:
        if self.vault_path.exists():
            try:
                return json.loads(self.vault_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_vault(self) -> None:
        self.vault_path.write_text(json.dumps(self._vault, indent=2), encoding="utf-8")

    @staticmethod
    def build_idempotency_key(pact_id: str, endpoint: str, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        raw = f"{pact_id}::{endpoint}::{canonical}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:36]

    @property
    def is_live(self) -> bool:
        return self.mode != "mock" and bool(self.client_id and self.client_secret)

    def get_oauth_token(self) -> str:
        """Obtain or refresh a PayPal Sandbox OAuth2 Bearer token (/v1/oauth2/token)."""
        now = time.time()
        if self._access_token and now < self._token_expires_at - 300:
            return self._access_token

        if self.mode == "mock" or not (self.client_id and self.client_secret):
            self._access_token = "sandbox_oauth2_token_cached_2026"
            self._token_expires_at = now + 28800
            return self._access_token

        creds = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode("utf-8")).decode("ascii")
        req = urllib.request.Request(
            f"{self.base_url}/v1/oauth2/token",
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {creds}",
                "Accept": "application/json",
                "Accept-Language": "en_US",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self._access_token = str(data["access_token"])
        self._token_expires_at = now + float(data.get("expires_in", 28800))
        return self._access_token

    def invoke_sandbox_endpoint(
        self,
        pact_id: str,
        api_family: str,
        http_method: str,
        endpoint: str,
        agent_toolkit_tool: str,
        payload: dict[str, Any],
        summary_template: str,
    ) -> tuple[dict[str, Any], PayPalApiCallTelemetry]:
        """Execute or replay a PayPal Sandbox REST call with idempotency and telemetry."""
        self._call_counter += 1
        t0 = time.perf_counter()
        request_id = self.build_idempotency_key(pact_id, endpoint, payload)

        # 1. Check SHA-256 Vault in hybrid or mock mode
        # GETs read live state (e.g. buyer approval), so they are never served from the vault.
        if self.mode in ("hybrid", "mock") and http_method.upper() != "GET" and request_id in self._vault:
            cached = self._vault[request_id]
            elapsed = (time.perf_counter() - t0) * 1000.0
            telemetry = PayPalApiCallTelemetry(
                step_order=self._call_counter,
                api_family=api_family,
                http_method=http_method,
                endpoint=endpoint,
                agent_toolkit_tool=agent_toolkit_tool,
                paypal_request_id=request_id,
                resource_id=cached.get("id", f"PP-{request_id[:10].upper()}"),
                status_code=int(cached.get("_http_status", 200)),
                cache_hit=True,
                latency_ms=round(elapsed, 2),
                summary=summary_template.format(id=cached.get("id", "")),
                source=f"VAULT REPLAY ({cached.get('_source', 'SIMULATED')})",
                raw_Preview=cached,
            )
            return cached, telemetry

        # 2. Deterministic Sandbox schema synthesis if in mock mode or no live keys injected
        if self.mode == "mock" or not (self.client_id and self.client_secret):
            simulated = self._simulate_paypal_sandbox_response(endpoint, payload, request_id)
            simulated["_source"] = "SIMULATED"
            self._vault[request_id] = simulated
            self._save_vault()
            elapsed = (time.perf_counter() - t0) * 1000.0
            telemetry = PayPalApiCallTelemetry(
                step_order=self._call_counter,
                api_family=api_family,
                http_method=http_method,
                endpoint=endpoint,
                agent_toolkit_tool=agent_toolkit_tool,
                paypal_request_id=request_id,
                resource_id=simulated["id"],
                status_code=int(simulated.get("_http_status", 201)),
                cache_hit=False,
                latency_ms=round(elapsed, 2),
                summary=summary_template.format(id=simulated["id"]),
                source="SIMULATED",
                raw_Preview=simulated,
            )
            return simulated, telemetry

        # 3. Live execution against https://api-m.sandbox.paypal.com
        token = self.get_oauth_token()
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "PayPal-Request-Id": request_id,
        }
        req_data = json.dumps(payload).encode("utf-8") if http_method.upper() != "GET" else None
        req = urllib.request.Request(url, data=req_data, headers=headers, method=http_method.upper())
        try:
            with urllib.request.urlopen(req, timeout=25.0) as resp:
                raw_bytes = resp.read()
                body = json.loads(raw_bytes.decode("utf-8")) if raw_bytes else {"status": "COMPLETED"}
                body["_http_status"] = resp.status
                body["_source"] = "LIVE SANDBOX"
                body.setdefault("id", f"PP-{request_id[:10].upper()}")
        except urllib.error.HTTPError as exc:
            # Never substitute simulated data for a failed live call: surface PayPal's real error.
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                error_body: Any = json.loads(raw)
            except ValueError:
                error_body = raw
            telemetry = PayPalApiCallTelemetry(
                step_order=self._call_counter,
                api_family=api_family,
                http_method=http_method,
                endpoint=endpoint,
                agent_toolkit_tool=agent_toolkit_tool,
                paypal_request_id=request_id,
                resource_id="FAILED",
                status_code=exc.code,
                cache_hit=False,
                latency_ms=round((time.perf_counter() - t0) * 1000.0, 2),
                summary=f"FAILED: PayPal Sandbox returned HTTP {exc.code}",
                raw_Preview=error_body if isinstance(error_body, dict) else {"body": error_body},
                source="LIVE SANDBOX",
            )
            raise PayPalSandboxError(exc.code, error_body, telemetry) from exc

        self._vault[request_id] = body
        self._save_vault()
        elapsed = (time.perf_counter() - t0) * 1000.0
        telemetry = PayPalApiCallTelemetry(
            step_order=self._call_counter,
            api_family=api_family,
            http_method=http_method,
            endpoint=endpoint,
            agent_toolkit_tool=agent_toolkit_tool,
            paypal_request_id=request_id,
            resource_id=body["id"],
            status_code=int(body.get("_http_status", 200)),
            cache_hit=False,
            latency_ms=round(elapsed, 2),
            summary=summary_template.format(id=body["id"]),
            raw_Preview=body,
            source="LIVE SANDBOX",
        )
        return body, telemetry

    @staticmethod
    def _simulate_paypal_sandbox_response(
        endpoint: str, payload: dict[str, Any], request_id: str
    ) -> dict[str, Any]:
        """Return schema-exact PayPal Sandbox JSON responses for deterministic local & CI testing."""
        short = request_id[:10].upper()

        if endpoint.endswith("/v2/invoicing/invoices"):
            inv_id = f"INV2-{short[:4]}-{short[4:8]}-{short[8:10]}92"
            return {
                "id": inv_id,
                "status": "SENT",
                "detail": payload.get("detail", {}),
                "invoicer": payload.get("invoicer", {}),
                "amount": payload.get("amount", {}),
                "configuration": {"allow_tip": False, "pay_by_bank": True},
                "links": [
                    {"rel": "self", "href": f"https://api-m.sandbox.paypal.com/v2/invoicing/invoices/{inv_id}"},
                    {"rel": "payer-view", "href": f"https://www.sandbox.paypal.com/invoice/p/#{inv_id.replace('-', '')}"},
                ],
                "_http_status": 201,
            }

        if "/conditional-rules" in endpoint:
            rule_id = f"CRULE-{short}"
            return {
                "id": rule_id,
                "status": "ACTIVE",
                "rule_type": payload.get("rule_type", "EARLY_PAYMENT_DISCOUNT"),
                "discount_percent": payload.get("discount_percent", 8.0),
                "trigger_condition": payload.get("trigger_condition", "SLA_VERIFIED_UNDER_24H"),
                "_http_status": 201,
            }

        if "/generate-qr-code" in endpoint:
            return {
                "id": f"QR-{short}",
                "qr_code_svg_path": f"/api/qr/{short}.svg",
                "width": payload.get("width", 300),
                "height": payload.get("height", 300),
                "action": "pay",
                "_http_status": 200,
            }

        if endpoint.endswith("/v2/checkout/orders"):
            ord_id = f"5O190127TN{short[:7]}"
            return {
                "id": ord_id,
                "intent": "AUTHORIZE",
                "status": "CREATED",
                "purchase_units": payload.get("purchase_units", []),
                "links": [
                    {"rel": "self", "href": f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{ord_id}"},
                    {"rel": "approve", "href": f"https://www.sandbox.paypal.com/checkoutnow?token={ord_id}"},
                    {"rel": "authorize", "href": f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{ord_id}/authorize"},
                ],
                "_http_status": 201,
            }

        if endpoint.endswith("/authorize"):
            auth_id = f"0VF52814937{short[:6]}"
            return {
                "id": auth_id,
                "status": "AUTHORIZED",
                "expiration_time": "2026-11-29T23:59:59Z",
                "seller_protection": {"status": "ELIGIBLE"},
                "_http_status": 201,
            }

        if "/shipping/trackers-batch" in endpoint:
            trk_id = f"TRK-{short[:8]}"
            return {
                "id": trk_id,
                "tracker_identifiers": [{"transaction_id": t.get("transaction_id"), "tracking_number": trk_id} for t in payload.get("trackers", [])],
                "status": "DELIVERED",
                "_http_status": 200,
            }

        if endpoint.endswith("/void"):
            return {"id": f"VOID-{short[:8]}", "status": "VOIDED", "_http_status": 204}

        if endpoint.endswith("/cancel"):
            return {"id": f"CANCEL-{short[:8]}", "status": "CANCELLED", "_http_status": 204}

        if endpoint.endswith("/capture"):
            cap_id = f"2GG903537H{short[:7]}"
            return {
                "id": cap_id,
                "status": "COMPLETED",
                "final_capture": True,
                "amount": payload.get("amount", {}),
                "seller_receivable_breakdown": {
                    "gross_amount": payload.get("amount", {}),
                    "paypal_fee": {"currency_code": "USD", "value": "4.89"},
                },
                "_http_status": 201,
            }

        if endpoint.endswith("/v1/payments/payouts"):
            batch_id = f"PAYOUTBATCH-{short}"
            return {
                "id": batch_id,
                "batch_header": {
                    "payout_batch_id": batch_id,
                    "batch_status": "SUCCESS",
                    "sender_batch_header": payload.get("sender_batch_header", {}),
                },
                "items_count": len(payload.get("items", [])),
                "items": payload.get("items", []),
                "_http_status": 201,
            }

        if "/require-evidence" in endpoint:
            disp_id = f"PP-D-{short[:6]}"
            return {
                "id": disp_id,
                "dispute_id": disp_id,
                "reason": "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED",
                "status": "WAITING_FOR_SELLER_RESPONSE",
                "dispute_state": "REQUIRED_ACTION",
                "dispute_life_cycle_stage": "INQUIRY",
                "sandbox_trigger": "require-evidence",
                "_http_status": 200,
            }

        if "/provide-evidence" in endpoint:
            return {
                "id": f"EVID-{short[:8]}",
                "status": "EVIDENCE_SUBMITTED",
                "evidence_type": payload.get("evidence_type", "PROOF_OF_FULFILLMENT_AND_SLA_TELEMETRY"),
                "_http_status": 200,
            }

        if "/make-offer" in endpoint:
            return {
                "id": f"OFFER-{short[:8]}",
                "status": "OFFER_PROPOSED",
                "offer_type": payload.get("offer", {}).get("offer_type", "REFUND"),
                "offer_amount": payload.get("offer", {}).get("offer_amount", {}),
                "note": payload.get("offer", {}).get("note", ""),
                "_http_status": 200,
            }

        if "/accept-offer" in endpoint or "/adjudicate" in endpoint:
            return {
                "id": f"RESOLVED-{short[:8]}",
                "status": "RESOLVED",
                "dispute_outcome": "RESOLVED_PARTIAL_CURE_SETTLEMENT",
                "adjudication_mode": "SANDBOX_AUTONOMOUS_COURTROOM",
                "settled_refund_amount": payload.get("refund_amount", {}),
                "_http_status": 200,
            }

        return {"id": f"PP-{short}", "status": "SUCCESS", "_http_status": 200}
