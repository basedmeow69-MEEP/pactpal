# PactPal

Autonomous agent-to-agent clearinghouse, programmable SLA escrow and Sandbox dispute courtroom on the PayPal Developer Platform. Built from docs/BLUEPRINT_SOURCE.md.

## Run
Requires Python 3.12+.
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn src.backend.app:app --port 8000
```
Open http://127.0.0.1:8000 and choose a path:
- **Path A**: SLA verified (≥90%) → capture + 3-way batch payout
- **Path B**: SLA breach (76%) → dispute courtroom, 24% partial-cure offer
- **Path C**: SLA failure (41%) → void the authorization and cancel the invoice

Click any ledger row to see the raw PayPal response. The **Source** column shows whether each call was `LIVE SANDBOX`, `SIMULATED`, or a vault replay.

## AI agents
With `ANTHROPIC_API_KEY` set, the buyer and seller agents negotiate with Claude (`claude-opus-5-5`, structured offers). Code clamps every offer to the buyer's SpendMandate cap and the seller's floor, so the model can bargain but cannot commit funds outside the signed mandate. Without a key, or if Claude declines, the scripted negotiation runs and the UI says so.

## PayPal Sandbox
Copy .env.example to .env and set `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` from a Sandbox REST app at https://developer.paypal.com/dashboard/. `PAYPAL_MODE=hybrid` makes live Sandbox calls when credentials are set and replays `vault/paypal_replay_vault.json` otherwise. Credentials are read only from the environment. If a live Sandbox call fails, the run stops with status `HALTED_ON_PAYPAL_SANDBOX_ERROR` and PayPal's real error; simulated data is never substituted for a failed live call.

## Test
```sh
.venv/bin/python -m pytest -v
```
