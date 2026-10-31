# PactPal: Settlement and Dispute Layer for Agent Commerce

Spec: built from a private hackathon blueprint (not included in this repo). Notes below are reference only.

## Summary

Two AI agents (buyer procurement, seller deal desk) negotiate a small service contract. PactPal turns the agreed terms into a PayPal Sandbox invoice, holds buyer funds with an Orders v2 authorization, scores the delivery against the agreed SLA, then either captures the payment or settles a partial remedy.

Thesis: agent-commerce demos assume every transaction succeeds. PactPal shows what happens when a delivery only partly meets its terms, and keeps agent spending inside a signed budget.

## Core loop (must ship)

1. **Negotiate.** Buyer and seller agents exchange bounded offers on price, delivery window and SLA threshold. Each offer is logged. The LLM proposes; deterministic code enforces bounds.
2. **Contract.** Create a Sandbox invoice (Invoices v2) with negotiated line items, attach a conditional rule, generate its QR code.
3. **Mandate and hold.** Sign an HMAC spend mandate (budget ceiling, payee, SLA rubric hash). Create an order with `intent: AUTHORIZE` and authorize it. No mutating call runs without a valid mandate.
4. **Verify.** Score the delivery 0–100 against the signed rubric. Green ≥ 90, amber 60–89, red < 60.
5. **Settle.**
   - Green: capture the authorization.
   - Amber: partial remedy. Preferred: Sandbox dispute flow. Fallback: capture then partial refund with the computed amount. Decide at Gate 2.
   - Red: void the authorization.
6. **Show it.** One page: negotiation transcript, ledger of every PayPal call (request id, status, raw JSON drawer), SLA timeline, invoice QR.

## Stretch (only after the core loop runs live in Sandbox)

- Batch payout split after green capture (needs Payouts enabled on the Sandbox account; unverified).
- PayPal MCP server / agent-toolkit tools driving the agents directly.
- Sponsor integrations: AG Grid ledger, Bryntum timeline, APIMatic SDK, Render deploy. Each must be the real product, not "-style"; confirm each sponsor prize's requirements and licensing first.

## Modes

`PAYPAL_MODE=mock|live`. Mock replays recorded Sandbox responses for judges and tests and is labeled MOCK on screen. Live calls `api-m.sandbox.paypal.com`. Never present mock output as a live Sandbox run.

## Stack

Python 3.12+, FastAPI, httpx, Pydantic; single static frontend served by the backend. Credentials only in environment variables, never in the browser or git.

## Non-goals

Production money movement, real accounts, blockchain, claims about competitor saturation or market size that we cannot cite.
