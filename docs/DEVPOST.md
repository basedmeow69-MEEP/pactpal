# Devpost submission draft

**Name:** PactPal
**Tagline:** The trust and settlement layer for agent-to-agent commerce on PayPal.

## Inspiration
Agentic-commerce demos assume every transaction succeeds. Real deals go wrong: late delivery, partial quality, a vendor agent that overpromised. An autonomous buyer needs to negotiate, hold funds safely, check what it got, and settle fairly when delivery falls short, without overspending and without a destructive full chargeback.

## What it does
1. **Negotiate.** An AI buyer agent and an AI seller agent (NVIDIA Nemotron, or Claude) bargain over price, SLA guarantee and an early-payment discount. Code enforces each side's private limits, so the model can bargain but never commit money outside its signed mandate.
2. **Contract.** The deal becomes a PayPal invoice: created, sent, and given a scannable QR code.
3. **Mandate and hold.** An HMAC-signed SpendMandateToken caps spend and locks the payee. An Orders v2 `AUTHORIZE` order holds the buyer's funds after the buyer approves.
4. **Verify and settle.** Delivery is scored against the SLA:
   - **≥ 90%:** capture the payment, register the delivery tracker on it, and split it with a 3-way batch payout.
   - **60–89%:** a partial-cure refund through PayPal's Disputes API. The seller agent offers a refund matching the defect ratio while the dispute is still an inquiry, and the buyer accepts.
   - **< 60%:** void the hold and cancel the invoice.

Every PayPal call appears in an AG Grid ledger with its result (live, replay, simulated or failed), money moved, `PayPal-Request-Id` and the raw PayPal response.

## Proof it works (live PayPal Sandbox, 2026-10-30)
- **Path A:** $390.00 captured (`7XB25686Y40249606`); payout batch `QM9PAKJFTZA6J`.
- **Path B:** the buyer opened dispute `PP-R-VBQ-10195354`. PactPal's seller agent offered $93.60 (24%), the buyer accepted, and PayPal resolved it as `INQUIRY_OFFER_PARTIAL_REFUND`. The merchant kept $296.40 instead of losing the full $390.
- **Path C:** the AI agents negotiated $353.40; the authorization was voided and the invoice cancelled.

Recordings of all three ship in the repo, so judges can replay them without credentials.

## How we built it
Python, FastAPI, httpx, NVIDIA API catalog (Nemotron 3.5) and the Anthropic SDK, the PayPal REST APIs (Invoices v2, Orders v2, Payments v2, Shipment Tracking, Payouts v1, Customer Disputes v1), and AG Grid Community.

## Challenges
- **The dispute lifecycle dictates the order.** A seller can only make an offer while a dispute is in the INQUIRY stage, and only the buyer can accept it. We rebuilt the courtroom flow around the real lifecycle, and pause the pact for the buyer's two actions.
- **Payment holds need buyer approval.** An `AUTHORIZE` order cannot be authorized until the buyer approves it. PactPal pauses, sends the buyer to PayPal, and continues automatically when PayPal redirects back.
- **Small API details that only show up live:**
  - the invoice total must come from line items;
  - QR codes exist only for sent invoices, and arrive as a multipart PNG;
  - shipment trackers attach to the capture, not the authorization;
  - batch endpoints report errors inside a 200 response.
- **Stale permissions.** PayPal kept reusing a token issued before we enabled Invoicing, until we revoked it.
- **Model availability.** The first-choice Nemotron endpoint returned server errors, so the agents fall back to a second model automatically.
- **Conditional invoice rules** still fail in our Sandbox with the documented body. PactPal shows that call as failed rather than hiding it.

## What's next
<!-- fill in -->

## Built with
paypal, python, fastapi, nvidia, nemotron, ag-grid
