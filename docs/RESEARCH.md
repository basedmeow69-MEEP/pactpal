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

## Official rules (checked 2026-10-30 against the rules page text pasted by the user)

- **Dates.** Submissions Oct 1 9:15 PT – **Thu Nov 12, 2026, 12:00 PT**. Judging Dec 1–15. Winners around Dec 21. The blueprint's Nov 5 "early eligibility gate" is NOT in the rules; it came from a Devpost email we have not seen. Treat Nov 5 as a self-imposed checkpoint only.
- **What to build.** An app that integrates the PayPal developer platform (free Sandbox) plus any AI tool, model or platform. "Any AI tool works, as long as PayPal integration is central to the project." New projects are fine; PactPal was created 2026-10-30, inside the period.
- **Demo access.** Judges must be able to run or interact with a working build: complete setup/run instructions in the repo OR a hosted URL. Mockups or non-functional demos fail. Include "any test account credentials, API keys, or sandbox login details necessary", or clear instructions for obtaining access. Keep it free and available until judging ends (Dec 15). Judges may judge from text, images and video alone.
- **Functionality.** Must install, run consistently, and "function as depicted in the video". Mock footage must therefore be labeled and must match what the build does.
- **Repository.** Public on GitHub, Bitbucket or GitLab, with all source, assets and instructions, and "an open source license file ... detectable and visible at the top of the repository page (in the About section)." Root LICENSE confirmed necessary.
- **Video.** Under 3:00 (judges need not watch past 3:00), shows the project running, public on YouTube, no third-party trademarks or copyrighted music or material without permission.
- **English** materials. Multiple submissions allowed only if substantially different.
- **IP.** Original work owned by the entrant; open source allowed if licenses are followed; third-party SDKs/APIs used only as their licenses allow.
- **Judging.** Stage One pass/fail: fits the theme and reasonably applies the required APIs/SDKs. Stage Two, equally weighted, and ties broken in this order: 1 Technological Implementation, 2 Design, 3 Potential Impact, 4 Innovation/Idea, 5 Presentation. Judging may use panels, peer review or "automated AI-driven analysis", so the README and description should state features and evidence plainly.
- **Prizes.** Grand: $12,000 / $8,000 / $5,000. Honorable mentions, $5,000 each: Most Creative, Most Impactful, Best Demo Delivery, Best Use of PayPal + AI, Best Use of Agentic Commerce. Sponsor prizes, each for submissions "that use any <sponsor> tools": AG Grid $5,000 / $2,000 / $1,000 ×3; APIMatic $1,000 + 6 months business subscription ×3; Bryntum $1,000 ×3; Channel3 $1,500 ×1; Render $1,000 / $750 / $500 credits. Totals: $67,500 cash + $2,250 credits (blueprint total was right).
- **Stacking.** At most one Grand Prize OR one Honorable Mention, plus one Sponsor Prize.
- **Sponsor tool list** also names Astropods, Elastic, KERNEL, Postman and Zapier, but they have no prizes.
- **Eligibility.** Age of majority where you live; individuals, teams and organizations allowed. Excluded: residents of Brazil, Quebec, Russia, Crimea, Cuba, Iran, North Korea and OFAC-sanctioned places; sponsor/administrator staff and families; judges and their employers. Confirm your own eligibility.
- **Judges** are not named in the rules and "may change". The blueprint's judge names remain unverified; do not tailor the pitch to individuals.
- **Participants.** The page shows 24,666 registered.

## Consequences for the plan

- **Sponsor target: AG Grid.** It has the most sponsor money ($10,000 over 5 prizes) and only one sponsor prize can stack. "Any AG Grid tools" means the MIT-licensed Community edition qualifies, so Enterprise-only features are optional. Render is a cheap second choice (credits only), mainly useful as the hosted demo.
- **Bryntum:** only pursue if its trial or license terms allow publishing it in a public open-source repo.
- **Judge access to Sandbox.** Default: README tells judges how to create their own free Sandbox app and run live, plus a clearly labeled mock mode that works with no keys. Optional: a hosted demo holding our Sandbox keys server-side. Never commit keys.
- **Honorable mention fit:** "Best Use of Agentic Commerce" and "Most Creative" match the concept.

## Discarded

Crowd-saturation percentages, participant count, the 99/100 self-score, market-size and "$3.75 per disputed dollar" figures: no sources. Do not use in the submission without a citation.

## Sponsor-tool risks

- AG Grid row grouping and sparklines are Enterprise features (license / watermark). Confirm what the sponsor prize accepts.
- Bryntum is commercial; the blueprint's "Bryntum-style" timeline would not be a Bryntum integration.

## Live Sandbox findings (2026-10-30)

- Invoicing scope must be enabled on the app; PayPal keeps reusing an already-issued token (up to 9h), so revoke it (`/v1/oauth2/token/terminate`) after changing features.
- Invoice create: do not send a top-level `amount` (PayPal computes it; mismatch is `calculation_error`). Returns only a link unless `Prefer: return=representation`.
- Conditional rules: documented body (`rules[]` with `EARLY_PAYMENT_DISCOUNT`/`AUTO_CANCEL`, `rule_expiry_terms`) returns intermittent 422/500 in this Sandbox for draft and recipient invoices. Treated as non-blocking; failure shown in the ledger.
- Send invoice (`send_to_recipient: false`) works. QR code works only after send and only with a non-JSON `Accept`; response is multipart PNG.
- Orders `AUTHORIZE`: create works; `/authorize` returns 422 `ORDER_NOT_APPROVED` until the Sandbox buyer approves.
