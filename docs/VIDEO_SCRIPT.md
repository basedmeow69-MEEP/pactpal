# Demo video script (target 2:40, hard limit under 3:00)

Every shot below uses a real control in the app, and every voiceover line describes something the build actually does. Record at 1920×1080. Use no music, or only music you have rights to.

## Before recording
1. Start the server with your live keys in `.env`: `.venv/bin/uvicorn src.backend.app:app --port 8000`.
2. Keep two windows ready:
   - **PactPal** at http://127.0.0.1:8000
   - a **private window** logged into https://www.sandbox.paypal.com as the **Personal** buyer
3. Do one warm-up run so the NVIDIA model is responsive. Its first call can take about 25 s before falling back to Lightning. Cut any waiting in editing.
4. Open case **PP-R-VBQ-10195354** in the buyer's Resolution Center, ready for shot 5.

## Shots

| Time | On screen (exactly what to click) | Voiceover |
|---|---|---|
| **0:00–0:15** Hook | PactPal home page; the ledger shows a recorded run. | "AI agents can already pay. But what happens when the vendor agent delivers late, or only partly delivers? Today it's all or nothing: pay in full, or fight a chargeback. PactPal is the settlement layer that handles the middle." |
| **0:15–0:45** Negotiate | Pick **Scenario 1**, click **Run Path A**. Scroll the negotiation panel as the rounds appear; point at **Negotiation engine: nemotron…**. | "Two AI agents, running on NVIDIA Nemotron, negotiate price, an SLA guarantee and an early-payment discount. Each has private limits: the buyer's budget is in a signed spend mandate, and the code, not the model, enforces it. They never reveal their limits to each other." |
| **0:45–1:05** Contract and hold | The ledger fills with **LIVE** rows: invoice, send, QR code, order. The panel shows **Approve as Sandbox buyer**: click it, approve in the PayPal window, PayPal shows **Payment approved**, and PactPal continues by itself. | "The deal becomes a real PayPal invoice with a QR code. The buyer approves once, and PayPal holds the funds: an authorization, not a payment, so nothing settles until delivery is checked." |
| **1:05–1:25** Path A: delivered | Milestones turn **green**. Ledger: capture **+$390.00**, the tracker, and the payout row. Point at the stats strip. | "Delivery scores 96 percent against the SLA. PactPal captures the payment, attaches the delivery tracker, and splits the money three ways with a PayPal batch payout." |
| **1:25–2:05** Path B: partial delivery | Click **Replay B · real dispute, $93.60 partial refund**. Show the purple **RECORDED LIVE SANDBOX RUN** banner, then the courtroom panel and the ledger rows *list disputes → read dispute → make offer → resolved*, and the totals' **refunded $93.60**. Cut to the PayPal buyer window: case **PP-R-VBQ-10195354** showing the seller's $93.60 offer accepted. | "Now the hard case. This delivery scored 76 percent. The buyer opened a real PayPal dispute. PactPal's seller agent answered with a partial refund matching the 24 percent shortfall: 93 dollars 60. The buyer accepted, and PayPal refunded it and closed the case. The merchant keeps 296 dollars 40 instead of losing the full 390 to a chargeback." |
| **2:05–2:20** Path C and guardrail | Click **Replay C · void + cancel**; milestones turn **red**. Then click **Test guardrail: $300 spend cap**: status **BLOCKED_BY_SPEND_MANDATE_GUARDRAIL**, ledger empty. | "If delivery fails outright, the hold is voided and the invoice cancelled, so the buyer pays nothing. And if a deal would exceed the signed budget, PactPal blocks it before a single PayPal call." |
| **2:20–2:40** Trust and close | Click a ledger row to show the raw PayPal response and its `PayPal-Request-Id`. Point at the red **FAILED** row (discount rule). End on the GitHub repo page showing the **MIT** licence. | "Every call is logged with PayPal's real response and an idempotency key, so a retrying agent can't charge twice. Failures are shown, not hidden. Everything here ran on the PayPal Sandbox. It's open source, and judges can replay these exact runs without any keys." |

## If something goes wrong while recording
- **The NVIDIA model is slow:** cut the wait. The badge shows which model answered; mention it only if it's visible.
- **You'd rather not wait for live approval:** use **Replay A** for 0:45–1:25, and say "this recorded live run" instead of "now".
- **Never present a SIMULATED row as live.** If one appears, re-record that shot or say so.

## Blueprint script vs this script
| Blueprint line | Changed to | Why |
|---|---|---|
| "PayPal Agent Toolkit v1.11.0" | (not mentioned) | The app calls the REST APIs directly. The toolkit's latest version is 1.8.0. |
| "PAY_BY_BANK", "eight-percent conditional rule" | Shown honestly as a FAILED row | The conditional-rules call fails in this Sandbox; PAY_BY_BANK isn't implemented. |
| "Nash equilibrium at $390" | Whatever price the agents reach live | Real AI agents; the price varies per run. |
| Tracker verifies delivery *before* capture | Tracker attaches *after* capture | PayPal only accepts trackers on a captured payment. |
| `require-evidence → provide-evidence → make-offer → adjudicate`, "in eleven seconds" | Buyer opens dispute → seller offer → buyer accepts | Offers are only allowed in INQUIRY, and only the buyer can accept. |
| "Bryntum SLA timeline" | Pact milestones coloured by outcome | No Bryntum integration. |
| "Schema-validated with APIMatic" | (not mentioned) | Not used. |
| "Deployed live on Render" | GitHub + replayable recordings | Not deployed (optional). |
| "Two live paths side-by-side" | A live, B and C from recorded live runs | Live disputes need real buyer actions that take minutes. |
