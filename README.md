# PactPal

Autonomous agent-to-agent clearinghouse, programmable SLA escrow and Sandbox dispute courtroom on the PayPal Developer Platform. Built from docs/BLUEPRINT_SOURCE.md.

## Run
Requires Python 3.12+.
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn src.backend.app:app --port 8000
```
Open http://127.0.0.1:8000 and use **Run Path A** (SLA verified → capture + 3-way batch payout) or **Run Path B** (SLA breach → dispute courtroom, 24% partial-cure offer).

## PayPal Sandbox
Copy .env.example to .env and set `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET` from a Sandbox REST app at https://developer.paypal.com/dashboard/. `PAYPAL_MODE=hybrid` makes live Sandbox calls when credentials are set and replays `vault/paypal_replay_vault.json` otherwise. Credentials are read only from the environment.

## Test
```sh
.venv/bin/python -m pytest -v
```
