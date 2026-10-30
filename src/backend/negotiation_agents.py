"""Claude-powered Buyer Procurement and Seller Deal-Desk agents for the A2A Nash Deal-Desk.

Each agent proposes structured offers with Claude. Deterministic code keeps every offer inside
the agent's private limits (buyer SpendMandate cap, seller floor) so the model can bargain but
can never commit funds outside the signed mandate.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from pydantic import BaseModel, Field

CLAUDE_MODEL = os.environ.get("PACTPAL_CLAUDE_MODEL", "claude-opus-5-5")
MAX_ROUNDS = 6


class AgentOffer(BaseModel):
    price_usd: float = Field(description="Proposed total contract price in USD")
    early_discount_pct: float = Field(description="Early-settlement discount percent written into the invoice conditional rule")
    sla_guarantee_score: float = Field(description="Minimum SLA compliance score (0-100) the seller guarantees")
    accept_counterparty_offer: bool = Field(description="True only to accept the other agent's latest offer exactly as stated")
    rationale: str = Field(description="One or two sentences explaining the move to the other agent")


def claude_available() -> bool:
    if os.environ.get("PACTPAL_AI", "auto").lower() == "off":
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _claude_offer_fn() -> Callable[[str, str], AgentOffer | None]:
    import anthropic

    client = anthropic.Anthropic()

    def ask(system: str, transcript: str) -> AgentOffer | None:
        response = client.messages.parse(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            output_config={"effort": "low"},
            system=system,
            messages=[{"role": "user", "content": transcript}],
            output_format=AgentOffer,
        )
        if response.stop_reason == "refusal":
            return None
        return response.parsed_output

    return ask


def _agent_system_prompt(role: str, scenario: dict[str, Any], floor_usd: float) -> str:
    items = "; ".join(f"{i['name']} (${i['unit_amount']['value']})" for i in scenario["line_items"])
    if role == "seller":
        return (
            "You are the Seller Deal-Desk Agent in PactPal, negotiating a contract settled through PayPal escrow. "
            f"Deliverables: {items}. List price ${scenario['initial_ask_usd']:.2f}. "
            f"Your private floor is ${floor_usd:.2f}; never offer below it. "
            "Maximize price while closing the deal. You may trade a higher SLA guarantee or a larger "
            "early-settlement discount for price. Accept only when the buyer's latest offer is acceptable."
        )
    return (
        "You are the Buyer Procurement Agent in PactPal, negotiating a contract settled through PayPal escrow. "
        f"Deliverables: {items}. Seller list price ${scenario['initial_ask_usd']:.2f}. "
        f"Your signed SpendMandate caps total spend at ${scenario['buyer_max_budget_usd']:.2f}; never offer above it. "
        "Minimize price, require an SLA guarantee of at least 90, and prefer a meaningful early-settlement discount. "
        "Accept only when the seller's latest offer is acceptable."
    )


def run_claude_negotiation(
    scenario: dict[str, Any],
    offer_fn: Callable[[str, str], AgentOffer | None] | None = None,
) -> dict[str, Any] | None:
    """Alternate seller/buyer offers until one side accepts. Returns None if Claude cannot be used."""
    ask = offer_fn or _claude_offer_fn()
    cap = float(scenario["buyer_max_budget_usd"])
    floor = float(scenario.get("seller_floor_usd", round(float(scenario["negotiated_price_usd"]) * 0.95, 2)))
    prompts = {
        "seller": _agent_system_prompt("seller", scenario, floor),
        "buyer": _agent_system_prompt("buyer", scenario, floor),
    }
    turns: list[dict[str, Any]] = []
    last: dict[str, AgentOffer] = {}

    for round_num in range(1, MAX_ROUNDS + 1):
        role = "seller" if round_num % 2 == 1 else "buyer"
        other = "buyer" if role == "seller" else "seller"
        transcript = "Negotiation so far:\n" + (
            "\n".join(
                f"Round {t['round_num']} {t['speaker_agent']}: ${t['proposed_price_usd']:.2f}, "
                f"{t['early_discount_pct']}% early discount, SLA {t['sla_guarantee_score']}. {t['rationale']}"
                for t in turns
            )
            or "(no offers yet; make the opening offer)"
        ) + f"\n\nThis is round {round_num} of at most {MAX_ROUNDS}. Make your move."
        try:
            offer = ask(prompts[role], transcript)
        except Exception:
            return None
        if offer is None:
            return None

        # Deterministic guardrails: the model bargains, code enforces private limits.
        price = min(offer.price_usd, cap) if role == "buyer" else max(offer.price_usd, floor)
        accepted = offer.accept_counterparty_offer and other in last
        if accepted:
            agreed = last[other]
            price = agreed.price_usd
        turns.append(
            {
                "round_num": round_num,
                "speaker_agent": "Seller Deal-Desk Agent (Claude)" if role == "seller" else "Buyer Procurement Agent (Claude)",
                "role_badge": "MERCHANT_AI" if role == "seller" else "BUYER_AI",
                "proposed_price_usd": round(price, 2),
                "early_discount_pct": round((last[other] if accepted else offer).early_discount_pct, 1),
                "sla_guarantee_score": round(max((last[other] if accepted else offer).sla_guarantee_score, 0.0), 1),
                "rationale": ("ACCEPTED. " if accepted else "") + offer.rationale,
            }
        )
        last[role] = offer.model_copy(update={"price_usd": round(price, 2)})
        if accepted and floor <= price <= cap:
            return _settle(turns, price, turns[-1]["early_discount_pct"], "Agreement reached by Claude agents")

    # No acceptance: mediator splits the final gap inside both private limits.
    if "buyer" in last and "seller" in last:
        mid = round(min(max((last["buyer"].price_usd + last["seller"].price_usd) / 2, floor), cap), 2)
        if floor <= cap:
            discount = round((last["buyer"].early_discount_pct + last["seller"].early_discount_pct) / 2, 1)
            return _settle(turns, mid, discount, "Nash mediator split the remaining gap within both mandates")
    return None


def _settle(turns: list[dict[str, Any]], price: float, discount: float, why: str) -> dict[str, Any]:
    turns.append(
        {
            "round_num": len(turns) + 1,
            "speaker_agent": "Nash Clearinghouse Mediator",
            "role_badge": "PACT_LOCKED",
            "proposed_price_usd": round(price, 2),
            "early_discount_pct": discount,
            "sla_guarantee_score": 90.0,
            "rationale": f"{why} at ${price:.2f} USD with a {discount:.1f}% early-settlement conditional rule.",
        }
    )
    return {"price_usd": round(price, 2), "early_discount_pct": discount, "turns": turns}
