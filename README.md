# PactPal

The trust and settlement layer for agent-to-agent commerce on PayPal. Two AI agents negotiate a contract; PactPal invoices it, holds the buyer's funds under a signed spend mandate, scores delivery against the agreed SLA, then **captures**, **settles a partial refund through a real PayPal dispute**, or **voids** the hold.

All three paths have been run end to end against the live PayPal Sandbox. Recordings of those runs ship in `vault/recorded_runs/` so you can inspect them without any credentials.

## Quick start (no credentials)
Requires Python 3.12+.
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn src.backend.app:app --port 8000
```
Open http://127.0.0.1:8000. The page opens on a recorded live Sandbox run. Use the **Replay** buttons to view all three, or **Run Path A/B/C** to run a new pact. Without PayPal credentials, new runs use clearly labelled `SIMULATED` responses.

## The three paths
| Path | SLA score | What happens on PayPal | Recorded live result |
|---|---|---|---|
| A | ≥ 90% | Capture the authorization, register the delivery tracker, 3-way batch payout | $390.00 captured, payout batch `QM9PAKJFTZA6J` |
| B | 60–89% | Capture, find the buyer's dispute, seller agent offers a partial-cure refund in the INQUIRY stage, buyer accepts | Dispute `PP-R-VBQ-10195354` resolved, $93.60 refunded |
| C | < 60% | Void the authorization, cancel the invoice | Authorization `559694531V423780Y` VOIDED, invoice CANCELLED |

Every PayPal call appears in the AG Grid ledger with its result (`LIVE`, `REPLAY · LIVE`, `SIMULATED` or `FAILED`), HTTP status, money moved, `PayPal-Request-Id` and the raw PayPal response (click a row).

## Run it live on your own PayPal Sandbox
1. At https://developer.paypal.com → **Apps & Credentials** (Sandbox), create an app. Under **Features**, enable **Invoicing**, **Payouts** and **Disputes**.
2. Copy `.env.example` to `.env` and set `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`. `.env` is git-ignored; credentials stay on the server.
3. Under **Testing Tools → Sandbox Accounts**, note the **Personal** buyer account. The buyer has to:
   - approve each payment (PayPal redirects back to PactPal, and the pact continues automatically);
   - for Path B, open a dispute on the payment and then accept the seller's offer in the Sandbox Resolution Center.

   These are buyer actions in PayPal; a merchant app cannot perform them.

If you enable a feature after a token was issued, PayPal keeps returning the old token for up to 9 hours. Revoke it (`POST /v1/oauth2/token/terminate`) to pick up the new permission.

## AI agents
Set `NVIDIA_API_KEY` (NVIDIA API catalog) or `ANTHROPIC_API_KEY` in `.env`. The buyer and seller agents then negotiate price, SLA guarantee and early-payment discount:
- **NVIDIA:** tries `nvidia/nemotron-3.5-super-vl-120b-a12b` first, and falls back to `nvidia/nemotron-3.5-lightning-30b-a3b` if that endpoint fails.
- **Anthropic:** uses `claude-opus-5-5`.

Code, not the model, enforces the limits: the buyer can never offer above its signed SpendMandate cap, and the seller never below its floor. Without a key, a scripted negotiation runs, and the UI says which engine ran.

## Safety and correctness
- **Spend mandate:** an HMAC-signed SpendMandateToken caps spend and locks the payee. An over-budget deal is blocked before any PayPal call.
- **Idempotency:** a deterministic `PayPal-Request-Id` per pact, endpoint and payload, so retries cannot double-charge.
- **Tokens:** the OAuth token is cached and refreshed before expiry. On a 401 it is refreshed and the call retried once.
- **Honest failures:** a failed live call stops the pact with PayPal's real error. Simulated data is never substituted. Batch endpoints that report errors inside a 200 body are treated as failures.
- **Known Sandbox issue:** invoice conditional rules returned 500/422 in our Sandbox with the documented body. The step is non-blocking and shows as `FAILED` in the ledger.

## Test
```sh
.venv/bin/python -m pytest -q
```
Tests never read `.env`, so they make no live calls.

## License
MIT, see `LICENSE`.
