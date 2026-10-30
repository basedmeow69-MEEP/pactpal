"""AI Buyer Procurement and Seller Deal-Desk agents for the A2A Nash Deal-Desk.

Each agent proposes structured offers with an LLM: Claude (Anthropic) or NVIDIA Nemotron
(NVIDIA API catalog, OpenAI-compatible). Deterministic code keeps every offer inside
the agent's private limits (buyer SpendMandate cap, seller floor) so the model can bargain but
can never commit funds outside the signed mandate.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

import httpx
from pydantic import BaseModel, Field, ValidationError

CLAUDE_MODEL = os.environ.get("PACTPAL_CLAUDE_MODEL", "claude-opus-5-5")
NVIDIA_MODEL = os.environ.get("PACTPAL_NVIDIA_MODEL", "nvidia/nemotron-3.5-super-vl-120b-a12b")
# Used when the primary model's hosted endpoint errors or stalls (Super VL returned 500s after ~130s on 2026-10-30).
NVIDIA_FALLBACK_MODEL = os.environ.get("PACTPAL_NVIDIA_FALLBACK_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
NVIDIA_PRIMARY_TIMEOUT = float(os.environ.get("PACTPAL_NVIDIA_PRIMARY_TIMEOUT", "25"))
NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
MAX_ROUNDS = 6


class AgentOffer(BaseModel):
    price_usd: float = Field(description="Proposed total contract price in USD")
    early_discount_pct: float = Field(description="Early-settlement discount percent written into the invoice conditional rule")
    sla_guarantee_score: float = Field(description="Minimum SLA compliance score (0-100) the seller guarantees")
    accept_counterparty_offer: bool = Field(description="True only to accept the other agent's latest offer exactly as stated")
    rationale: str = Field(description="One or two sentences explaining the move to the other agent")


def ai_provider() -> str | None:
    """anthropic | nvidia | None. PACTPAL_AI picks one explicitly; auto uses whichever key is set."""
    choice = os.environ.get("PACTPAL_AI", "auto").lower()
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    has_nvidia = bool(os.environ.get("NVIDIA_API_KEY"))
    if choice == "off":
        return None
    if choice in ("anthropic", "nvidia"):
        return choice if {"anthropic": has_anthropic, "nvidia": has_nvidia}[choice] else None
    return "anthropic" if has_anthropic else "nvidia" if has_nvidia else None


_nvidia_model_in_use: str | None = None


def ai_model_label() -> str:
    nvidia = _nvidia_model_in_use or NVIDIA_MODEL
    return {"anthropic": CLAUDE_MODEL, "nvidia": nvidia}.get(ai_provider() or "", "scripted")


def claude_available() -> bool:
    return ai_provider() is not None


def _nvidia_offer_fn() -> Callable[[str, str], AgentOffer | None]:
    client = httpx.Client(
        base_url=NVIDIA_BASE_URL,
        headers={"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}"},
        timeout=120,
    )
    models = [NVIDIA_MODEL] + ([NVIDIA_FALLBACK_MODEL] if NVIDIA_FALLBACK_MODEL != NVIDIA_MODEL else [])

    def complete(messages: list[dict[str, str]]) -> str:
        """Ask the first model that answers; once the primary fails, stay on the fallback."""
        global _nvidia_model_in_use
        start = models.index(_nvidia_model_in_use) if _nvidia_model_in_use in models else 0
        last_error: Exception | None = None
        for i, model in enumerate(models[start:], start):
            try:
                response = client.post(
                    "/chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.6,
                        "max_tokens": 1024,
                        "chat_template_kwargs": {"enable_thinking": False},
                    },
                    timeout=NVIDIA_PRIMARY_TIMEOUT if i == 0 and len(models) > 1 else 120,
                )
                response.raise_for_status()
                _nvidia_model_in_use = model
                return response.json()["choices"][0]["message"].get("content") or ""
            except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
        raise last_error or RuntimeError("no NVIDIA model available")
    schema = json.dumps(AgentOffer.model_json_schema()["properties"])

    def ask(system: str, transcript: str) -> AgentOffer | None:
        messages = [
            {
                "role": "system",
                "content": system + "\n\nReply with only one JSON object with exactly these fields: " + schema,
            },
            {"role": "user", "content": transcript},
        ]
        for _ in range(2):  # one retry if the reply is not a valid offer
            content = complete(messages)
            match = re.search(r"\{.*\}", content, re.S)
            try:
                if match:
                    return AgentOffer.model_validate_json(match.group(0))
            except ValidationError:
                pass
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": "That was not valid. Reply with only the JSON object."})
        return None

    return ask


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
            "early-settlement discount for price. Concede in small steps. Never reveal your floor or say how "
            "close you are to it; your rationale is read by the buyer. Accept only when the buyer's latest offer is acceptable."
        )
    return (
        "You are the Buyer Procurement Agent in PactPal, negotiating a contract settled through PayPal escrow. "
        f"Deliverables: {items}. Seller list price ${scenario['initial_ask_usd']:.2f}. "
        f"Your signed SpendMandate caps total spend at ${scenario['buyer_max_budget_usd']:.2f}; never offer above it. "
        "Minimize price, require an SLA guarantee of at least 90, and prefer a meaningful early-settlement discount. "
        "Open well below your cap and concede gradually; jumping to your cap wastes your leverage. Never reveal your "
        "cap or budget; your rationale is read by the seller. Argue from value, SLA risk and market price instead. "
        "Accept only when the seller's latest offer is acceptable and within your cap."
    )


def run_claude_negotiation(
    scenario: dict[str, Any],
    offer_fn: Callable[[str, str], AgentOffer | None] | None = None,
) -> dict[str, Any] | None:
    """Alternate seller/buyer offers until one side accepts. Returns None if Claude cannot be used."""
    if offer_fn is None:
        provider = ai_provider()
        if provider is None:
            return None
        offer_fn = _nvidia_offer_fn() if provider == "nvidia" else _claude_offer_fn()
    ask = offer_fn
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
                "speaker_agent": f"{'Seller Deal-Desk' if role == 'seller' else 'Buyer Procurement'} Agent ({ai_model_label().split('/')[-1]})",
                "role_badge": "MERCHANT_AI" if role == "seller" else "BUYER_AI",
                "proposed_price_usd": round(price, 2),
                "early_discount_pct": round((last[other] if accepted else offer).early_discount_pct, 1),
                "sla_guarantee_score": round(max((last[other] if accepted else offer).sla_guarantee_score, 0.0), 1),
                "rationale": ("ACCEPTED. " if accepted else "") + offer.rationale,
            }
        )
        last[role] = offer.model_copy(update={"price_usd": round(price, 2)})
        if accepted and floor <= price <= cap:
            return _settle(turns, price, turns[-1]["early_discount_pct"], "Agreement reached by the AI agents")

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
