# PactPal

Settlement and dispute layer for agent commerce, built on the PayPal Sandbox. Two agents negotiate a contract; PactPal invoices it, holds funds under a signed spend mandate, scores delivery against the agreed SLA, then captures, partially remedies, or voids.

Status: early build. See docs/BRIEF.md (scope), docs/TASKS.md (gates), docs/RESEARCH.md (what is verified), docs/SUBMISSION.md.

## Setup
Requires Python 3.12+.
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest
```

## Sandbox
Copy .env.example to .env and fill it from a Sandbox REST app at https://developer.paypal.com/dashboard/. Credentials stay server-side and out of git. Gate 1 check: `python scripts/sandbox_smoke.py create`, approve the link as the Sandbox buyer, then `python scripts/sandbox_smoke.py void ORDER_ID`.

`PAYPAL_MODE=mock` (default) replays recorded Sandbox responses and is labeled MOCK in the UI. It is not evidence of a live Sandbox run.
