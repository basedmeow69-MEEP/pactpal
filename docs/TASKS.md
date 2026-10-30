# PactPal production

Project started 2026-10-30 from docs/BLUEPRINT_SOURCE.md. Airlock (Hackathons repo) is due first; PactPal work should not take time from Airlock's live gates before Nov 2.

## Gates (in order; do not expand scope past a failed gate)

- **Gate 0 — Rules.** Human pastes the official rules into docs/RESEARCH.md. Confirm deadline, early-review date, license, video cap, eligibility, creation period.
- **Gate 1 — Sandbox credentials.** Create a Sandbox REST app and a buyer Sandbox account. `scripts/sandbox_smoke.py` gets a token and creates/authorizes/voids one order. Record IDs.
- **Gate 2 — Amber path decision.** Prove whether a dispute can be opened and driven through `make-offer` → (buyer) `accept-offer` or `adjudicate` without manual UI steps. If not within half a day, ship the partial-refund fallback and describe disputes as future work.
- **Gate 3 — Core loop live.** Green, amber and red runs complete against Sandbox; responses recorded into the mock vault.
- **Gate 4 — Early eligibility submission** (if Gate 0 confirms Nov 5). Public repo, LICENSE visible, README, working build, draft video.
- **Gate 5 — Final.** Video, Devpost text, hosted demo, clean-checkout check.

## Work packages (non-overlapping ownership)

| Package | Files | Status |
| :--- | :--- | :--- |
| Foundation: settings, Sandbox client (token cache + refresh, idempotency), spend mandate | src/pactpal/{config,paypal_client,mandate}.py, tests | Started |
| Engine: negotiation bounds, SLA scoring, settlement routing | src/pactpal/engine.py | Not started |
| Agents: LLM buyer/seller wrapped by deterministic bounds | src/pactpal/agents.py | Not started; choose model provider |
| API server + mock vault | src/pactpal/app.py, vault/ | Not started |
| Frontend command center | frontend/ | Not started |
| Deploy + video + Devpost | render.yaml, docs/SUBMISSION.md | Not started |

## Log

- 2026-10-30: Scaffolded repo, ledger of verified/unverified blueprint claims, foundation module with offline tests.
