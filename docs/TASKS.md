# PactPal production

Project started 2026-10-30 from docs/BLUEPRINT_SOURCE.md. Airlock (Hackathons repo) is due first; PactPal work should not take time from Airlock's live gates before Nov 2.

## Gates (in order; do not expand scope past a failed gate)

- **Gate 0 — Rules.** PASSED 2026-10-30: official rules summarized in docs/RESEARCH.md. Deadline Thu Nov 12 12:00 PT. Still open: entrant confirms personal eligibility.
- **Gate 1 — Sandbox credentials.** Create a Sandbox REST app and a buyer Sandbox account. `scripts/sandbox_smoke.py` gets a token and creates/authorizes/voids one order. Record IDs.
- **Gate 2 — Amber path decision.** Prove whether a dispute can be opened and driven through `make-offer` → (buyer) `accept-offer` or `adjudicate` without manual UI steps. If not within half a day, ship the partial-refund fallback and describe disputes as future work.
- **Gate 3 — Core loop live.** Green, amber and red runs complete against Sandbox; responses recorded into the mock vault.
- **Gate 4 — Self-imposed checkpoint, Thu Nov 5** (not in the rules). Public repo, LICENSE visible in About, README, working build, draft video, Devpost draft saved.
- **Gate 5 — Final, submit by Thu Nov 12 09:30 PT** (buffer before 12:00 PT). Video under 3:00, Devpost text, judge access instructions, clean-checkout check. Keep the demo working until Dec 15.

## Work packages (non-overlapping ownership)

| Package | Files | Status |
| :--- | :--- | :--- |
| Foundation: settings, Sandbox client (token cache + refresh, idempotency), spend mandate | src/pactpal/{config,paypal_client,mandate}.py, tests | Started |
| Engine: negotiation bounds, SLA scoring, settlement routing | src/pactpal/engine.py | Not started |
| Agents: LLM buyer/seller wrapped by deterministic bounds | src/pactpal/agents.py | Not started; choose model provider |
| API server + mock vault | src/pactpal/app.py, vault/ | Not started |
| Frontend command center (AG Grid Community ledger) | frontend/ | Not started |
| Deploy + video + Devpost | render.yaml, docs/SUBMISSION.md | Not started |

## Log

- 2026-10-30: Added Claude buyer/seller agents (claude-opus-5-5, mandate-clamped), red void path, live-error halt (no simulated substitution), Source column + raw JSON drawer, Devpost draft. 10/10 tests pass; three paths verified through the server.

- 2026-10-30: Implemented blueprint Steps 1–7 as written (src/apimatic_sdk, src/backend, src/frontend, tests, render.yaml). 3/3 tests pass; server verified: Path A, Path B, mandate block, QR, MCP tool list.

- 2026-10-30: Official rules checked; sponsor target set to AG Grid; Nov 5 reclassified as self-imposed.
- 2026-10-30: Scaffolded repo, ledger of verified/unverified blueprint claims, foundation module with offline tests.
