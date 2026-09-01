"""Map a TradingAgents run state into an AlphArena thesis.

This is the differentiator, per the spec. AlphArena locks a written thesis at
submission and never lets it be edited; every other integration would have to
invent one. TradingAgents already produces it — the bull/bear researcher debate
and the risk manager's sign-off are a by-product of how the framework works.

We forward it whole. AlphArena enforces no maximum thesis length (checked
2026-09-01: minimum 8 characters, required above $2,000, stored intact), so
there are no compression rules here on purpose. The only ceiling is the 1 MB
request body, which SOFT_CHAR_LIMIT stays well inside.
"""

from __future__ import annotations

from typing import Any, Mapping

# Not a platform limit — a self-imposed ceiling so one pathological debate
# transcript cannot bloat a trade document or break page rendering.
SOFT_CHAR_LIMIT = 20_000

# Keys are read defensively: TradingAgents' state shape has changed across
# releases (v0.2.4 introduced structured-output agents, v0.4.0 reworked the
# decision log). Missing sections are skipped, never faked.
_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Bull case", ("bull_case", "bull_report", "investment_debate_state.bull_history")),
    ("Bear case", ("bear_case", "bear_report", "investment_debate_state.bear_history")),
    ("Research decision", ("investment_plan", "investment_debate_state.judge_decision")),
    ("Trader plan", ("trader_investment_plan", "trader_plan")),
    ("Risk assessment", ("final_trade_decision", "risk_debate_state.judge_decision")),
)


def _dig(state: Mapping[str, Any], dotted: str) -> Any:
    node: Any = state
    for part in dotted.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return None
        node = node[part]
    return node


def build_thesis(state: Mapping[str, Any], decision: Any = None) -> str:
    """Compose the thesis text. Returns '' when the state carries nothing usable.

    An empty return is meaningful: the caller must not invent a thesis to get
    past the API's minimum. A trade with no reasoning should submit without one
    and be flagged MISSING_THESIS by the server, which is the honest outcome.
    """
    parts: list[str] = []

    if decision is not None:
        text = str(decision).strip()
        if text:
            parts.append(f"Decision: {text}")

    for label, candidates in _SECTIONS:
        for key in candidates:
            value = _dig(state, key)
            if isinstance(value, str) and value.strip():
                parts.append(f"## {label}\n{value.strip()}")
                break

    thesis = "\n\n".join(parts).strip()

    if len(thesis) > SOFT_CHAR_LIMIT:
        # Trim at a section boundary where possible so the result stays readable
        # rather than ending mid-sentence, and say plainly that it was trimmed.
        cut = thesis.rfind("\n\n## ", 0, SOFT_CHAR_LIMIT)
        if cut == -1:
            cut = SOFT_CHAR_LIMIT
        thesis = thesis[:cut].rstrip() + "\n\n[Thesis truncated by the connector at 20,000 characters.]"

    return thesis
