"""Gate 1: prove Sandbox credentials and the authorize/void path.

  python scripts/sandbox_smoke.py create          # prints an approval link
  (approve it while logged in as the Sandbox *buyer* account)
  python scripts/sandbox_smoke.py void ORDER_ID   # authorizes, then voids

Reads PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET from the environment.
"""
from __future__ import annotations

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pactpal.paypal_client import SandboxClient, request_id  # noqa: E402


def main() -> None:
    client = SandboxClient(os.environ["PAYPAL_CLIENT_ID"], os.environ["PAYPAL_CLIENT_SECRET"])
    run = f"smoke-{uuid.uuid4().hex[:8]}"
    if sys.argv[1:2] == ["create"]:
        body = {
            "intent": "AUTHORIZE",
            "purchase_units": [{"amount": {"currency_code": "USD", "value": "1.00"}, "custom_id": run}],
        }
        order = client.call("POST", "/v2/checkout/orders", json_body=body, idempotency_key=request_id(run, "create", body))
        approve = next(link["href"] for link in order["links"] if link["rel"] in ("approve", "payer-action"))
        print(json.dumps({"order_id": order["id"], "status": order["status"], "approve": approve}, indent=2))
    elif sys.argv[1:2] == ["void"] and len(sys.argv) == 3:
        order_id = sys.argv[2]
        order = client.call("POST", f"/v2/checkout/orders/{order_id}/authorize", json_body={}, idempotency_key=request_id(run, "authorize", order_id))
        auth = order["purchase_units"][0]["payments"]["authorizations"][0]
        client.call("POST", f"/v2/payments/authorizations/{auth['id']}/void", idempotency_key=request_id(run, "void", auth["id"]))
        final = client.call("GET", f"/v2/payments/authorizations/{auth['id']}")
        print(json.dumps({"order_id": order_id, "authorization_id": auth["id"], "authorization_status": final["status"]}, indent=2))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
