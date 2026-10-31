# PactPal production

Project started 2026-10-30 from a private hackathon blueprint (not included in this repo).

## Gates (in order; do not expand scope past a failed gate)

- **Gate 0 — Rules.** PASSED 2026-10-30: official rules summarized in docs/RESEARCH.md. Deadline Thu Nov 12 12:00 PT. Still open: entrant confirms personal eligibility.
- **Gate 1 — Sandbox credentials.** PASSED 2026-10-30: Sandbox app with Invoicing, Payouts and Disputes; Personal buyer account.
- **Gate 2 — Amber path decision.** PASSED 2026-10-30: real buyer dispute → seller make-offer (INQUIRY) → buyer accepts in Resolution Center → PayPal refunds automatically. The two buyer steps (open dispute, accept) are buyer actions PayPal does not allow a merchant app to perform.
- **Gate 3 — Core loop live.** PASSED 2026-10-30 for all three paths (A capture + payout, B dispute partial refund, C void + cancel); recordings in `vault/recorded_runs/`.
- **Gate 4 — Self-imposed checkpoint, Thu Nov 5** (not in the rules). Public repo and licence done; draft video and Devpost draft outstanding.
- **Gate 5 — Final, submit by Thu Nov 12 09:30 PT** (buffer before 12:00 PT). Video under 3:00, Devpost text, judge access instructions, clean-checkout check. Keep the demo working until Dec 15.

## Components

| Component | Files | Status |
| :--- | :--- | :--- |
| Sandbox client: OAuth refresh + 401 retry, idempotency, replay vault, honest failures | src/backend/paypal_sandbox_client.py | Done, live-verified |
| Spend mandate and data models | src/apimatic_sdk/models.py | Done |
| Engine: mandate check, SLA zones, capture / dispute / void settlement | src/backend/pactpal_engine.py | Done, live-verified |
| AI agents: NVIDIA Nemotron or Claude, limits enforced in code | src/backend/negotiation_agents.py | Done, live-verified (Nemotron Lightning) |
| API server, buyer return page, recorded runs | src/backend/app.py, vault/recorded_runs/ | Done |
| Command center: AG Grid ledger, milestones, replay, guardrail test | src/frontend/index.html | Done; not yet checked visually by us |
| Video, Devpost, optional Render deploy | docs/VIDEO_SCRIPT.md, docs/DEVPOST.md, render.yaml | Script written; recording and entry outstanding |

## Log

- 2026-10-31: Reconciled the blueprint's video script with the app: simulated Path B now follows the real dispute lifecycle; outcome-coloured milestones; guardrail button; honest tool labels; docs/VIDEO_SCRIPT.md written.

- 2026-10-30: Live Sandbox Path A (capture $390 + payout batch) and Path B (dispute PP-R-VBQ-10195354 resolved with $93.60 partial refund) both completed end to end.

- 2026-10-30: Added Claude buyer/seller agents (claude-opus-5-5, mandate-clamped), red void path, live-error halt (no simulated substitution), Source column + raw JSON drawer, Devpost draft. 10/10 tests pass; three paths verified through the server.

- 2026-10-30: Implemented blueprint Steps 1–7 as written (src/apimatic_sdk, src/backend, src/frontend, tests, render.yaml). 3/3 tests pass; server verified: Path A, Path B, mandate block, QR, MCP tool list.

- 2026-10-30: Official rules checked; sponsor target set to AG Grid; Nov 5 reclassified as self-imposed.
- 2026-10-30: Scaffolded repo, ledger of verified/unverified blueprint claims, foundation module with offline tests.
