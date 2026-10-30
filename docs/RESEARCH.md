# Verification ledger

Research performed 2026-10-30. The source blueprint is AI-generated; treat every claim in it as unverified until listed here as checked.

## Checked against official PayPal sources

| Claim in blueprint | Status | Notes |
| :--- | :--- | :--- |
| Disputes `require-evidence` and `adjudicate` are Sandbox-only | TRUE | Both marked "for sandbox use only" in Customer Disputes v1 reference. |
| `provide-evidence`, `make-offer`, `accept-offer` exist | TRUE | |
| Flow `require-evidence → provide-evidence → make-offer` | WRONG ORDER | `make-offer` requires the dispute to be in the `INQUIRY` stage. `require-evidence` moves it past that. Offer must come first. |
| PactPal (merchant app) can call `accept-offer` | NO | `accept-offer` is a customer action (`disputes/update-buyer` scope). A merchant app cannot play both sides with one credential. |
| A dispute can be opened from the API in seconds | UNVERIFIED | Sandbox disputes are normally opened by a buyer Sandbox account on a completed payment. Gate 2 must prove how. |
| Invoices v2 conditional rules endpoint | TRUE | `POST /v2/invoicing/invoices/{id}/conditional-rules`. |
| Invoice QR code endpoint | TRUE | `POST /v2/invoicing/invoices/{invoice_id}/generate-qr-code`. |
| Orders authorize, Payments v2 capture/void of an authorization | TRUE | `intent: AUTHORIZE` enum itself not yet checked on the create-order page. |
| `@paypal/agent-toolkit` v1.11.0 | WRONG | GitHub shows 1.8.0 as latest (15 Sep). MCP ships as separate `@paypal/mcp`. |
| Toolkit tools `create_conditional_rules_for_invoice`, `generate_invoice_qr_code`, `create_shipment_tracking`, `list_disputes`, `accept_dispute_claim` | TRUE | Python package `paypal-agent-toolkit` has a smaller payments list than TypeScript. |
| Toolkit has a dispute make-offer / adjudicate tool | NO | Only `list_disputes`, `get_dispute`, `accept_dispute_claim`. Use REST directly. |
| Agents can authorize an order autonomously | NO (as written) | An `AUTHORIZE` order still needs payer approval via its approve link (buyer Sandbox login) before `/authorize`, unless a saved/vaulted payment method is set up. The demo needs one approval step or vaulting; Gate 1 tests this. |
| Payouts sandbox works out of the box | UNVERIFIED | Reference page states no prerequisites; check the integration guide and the Sandbox account. |

## Not verifiable here (Devpost returned 403 to automated fetches)

Must be read by a human from https://paypalaihackathon.devpost.com/rules and pasted into this file:

- Deadline (blueprint: Thu 2026-11-12 12:00 PST) and the early eligibility review (blueprint: Thu 2026-11-05).
- License-file requirement wording, public-repo requirement, video length cap (blueprint: 3:00).
- Judging criteria, weights and tie-break order (blueprint: five equal criteria, Technological Implementation first).
- Prize amounts, sponsor prizes and their requirements, stacking rules.
- Eligibility: country, age, team size, project creation period / pre-existing code.
- Judge names. The blueprint lists names; do not tailor pitches to people until confirmed.

## Discarded

Crowd-saturation percentages, participant count, the 99/100 self-score, market-size and "$3.75 per disputed dollar" figures: no sources. Do not use in the submission without a citation.

## Sponsor-tool risks

- AG Grid row grouping and sparklines are Enterprise features (license / watermark). Confirm what the sponsor prize accepts.
- Bryntum is commercial; the blueprint's "Bryntum-style" timeline would not be a Bryntum integration.
