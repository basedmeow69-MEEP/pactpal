# Devpost submission draft

**Name:** PactPal
**Tagline:** The trust and settlement layer for agent-to-agent commerce on PayPal.

## Inspiration
Agentic-commerce demos assume every transaction succeeds. Real deals go wrong: late delivery, partial quality, a vendor agent that overpromised. An autonomous buyer needs to negotiate, hold funds safely, check what it got, and settle fairly when delivery falls short, without a human and without overspending.

## What it does
1. **Negotiate.** A Claude buyer agent and a Claude seller agent bargain over price, SLA guarantee and an early-settlement discount. Code enforces each side's private limits.
2. **Contract.** The deal becomes a PayPal Invoices v2 invoice with a conditional rule and a QR code.
3. **Mandate and hold.** An HMAC-signed SpendMandateToken caps spend and locks the payee. An Orders v2 `AUTHORIZE` order holds the funds.
4. **Verify.** Delivery is registered through Shipment Tracking and scored against the SLA.
5. **Settle.** Green (≥90%): capture the authorization, then a 3-way batch payout. Amber (60–89%): dispute flow with a computed partial-cure refund offer. Red (<60%): void the hold and cancel the invoice.

Every PayPal call appears in an AG Grid ledger with its `PayPal-Request-Id`, HTTP status, source and raw response.

## How we built it
Python, FastAPI, the Anthropic SDK (Claude structured outputs), the PayPal REST APIs (Invoices v2, Orders v2, Payments v2, Shipment Tracking, Payouts v1, Customer Disputes v1), and AG Grid Community. Deployable to Render with `render.yaml`.

## Engineering details
- OAuth token cached and refreshed 5 minutes before expiry.
- Deterministic `PayPal-Request-Id` per pact, endpoint and payload, so agent retries cannot double-charge.
- The SpendMandateToken is verified before any money movement; over-budget deals are blocked before the first PayPal call.
- A failed live Sandbox call halts the run and shows PayPal's real error.
- Replay vault for judges without credentials, clearly labeled in the ledger.

## Challenges
<!-- fill in from real Sandbox runs, e.g. how disputes were opened in Sandbox -->

## What's next
<!-- fill in -->

## Built with
paypal, python, fastapi, anthropic, claude, ag-grid, render
