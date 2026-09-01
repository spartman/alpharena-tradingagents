"""Submit a TradingAgents run to AlphArena.

Order matters: the live-forward guard runs before anything else, so a replayed
backtest is refused without touching the network.

Failure isolation is a hard requirement (spec 7) — a rejected submission logs
and returns a result object. It never raises into the caller's run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .client import AlpharenaClient
from .errors import AlpharenaError, HistoricalRunRejected
from .guard import DateLike, assert_live_run
from .thesis import build_thesis

log = logging.getLogger("alpharena")

_BUY = {"BUY", "LONG", "STRONG BUY", "STRONG_BUY"}
_SELL = {"SELL", "SHORT", "STRONG SELL", "STRONG_SELL"}


def parse_direction(decision: Any) -> Optional[str]:
    """Map a TradingAgents decision to long/short, or None for HOLD.

    Returns None rather than guessing: HOLD is not a trade, and an unrecognised
    decision string must not become a position.
    """
    if decision is None:
        return None
    text = str(decision).strip().upper()
    for token in _BUY:
        if token in text:
            return "long"
    for token in _SELL:
        if token in text:
            return "short"
    return None


@dataclass
class SubmitResult:
    ticker: str
    submitted: bool
    skipped_reason: Optional[str] = None
    error: Optional[str] = None
    response: dict = field(default_factory=dict)


def submit_run(
    *,
    ticker: str,
    run_date: DateLike,
    state: Mapping[str, Any],
    decision: Any,
    entry_price: float,
    client: AlpharenaClient,
    size_pct: Optional[float] = None,
    strategy: Optional[str] = None,
) -> SubmitResult:
    try:
        assert_live_run(run_date)
    except HistoricalRunRejected as exc:
        log.error("[alpharena] %s refused: %s", ticker, exc)
        return SubmitResult(ticker=ticker, submitted=False, skipped_reason=str(exc))

    direction = parse_direction(decision)
    if direction is None:
        reason = f"decision {decision!r} is not a position (HOLD or unrecognised)"
        log.info("[alpharena] %s skipped: %s", ticker, reason)
        return SubmitResult(ticker=ticker, submitted=False, skipped_reason=reason)

    thesis = build_thesis(state, decision)

    try:
        response = client.submit_trade(
            ticker=ticker,
            direction=direction,
            entry_price=entry_price,
            size_pct=size_pct,
            thesis=thesis,
            strategy=strategy,
            idempotency_key=f"ta-{ticker}-{assert_live_run(run_date).isoformat()}",
        )
    except AlpharenaError as exc:
        log.error("[alpharena] %s failed: %s", ticker, exc)
        return SubmitResult(ticker=ticker, submitted=False, error=str(exc))
    except Exception as exc:  # never crash the caller's run
        log.exception("[alpharena] %s unexpected error", ticker)
        return SubmitResult(ticker=ticker, submitted=False, error=repr(exc))

    log.info("[alpharena] %s %s submitted", ticker, direction)
    return SubmitResult(ticker=ticker, submitted=True, response=response)
