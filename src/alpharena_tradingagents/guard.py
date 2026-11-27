"""Live-forward-only enforcement.

TradingAgents' entry point is ``ta.propagate(ticker, date)`` — the date is an
explicit argument, which is exactly where a replayed backtest becomes
distinguishable from a live decision. This module is that check.

Deliberately strict: an ambiguous or unparseable date is refused, not waved
through. A missed live trade costs one row; an accepted backtest costs the
credibility of the whole board.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Union

from .errors import HistoricalRunRejected

DateLike = Union[str, date, datetime]

# fromisoformat validates calendar dates and times, but accepts arbitrary
# date/time separators and can silently normalize out-of-range offset fields.
_ISO_RUN_DATE = re.compile(
    r"""
    (?:[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{8}|[0-9]{4}-?W[0-9]{2}(?:-?[0-9])?)
    (?:
        [T ][0-9]{2}(?:(?P<tsep>:?)[0-9]{2}(?:(?P=tsep)[0-9]{2})?)?
        (?:[.,][0-9]+)?
        (?:
            Z
            | [+-](?:[01][0-9]|2[0-3])
              (?:(?P<osep>:?)[0-5][0-9](?:(?P=osep)[0-5][0-9](?:[.,][0-9]+)?)?)?
        )?
    )?
    """,
    re.VERBOSE,
)


def _coerce(value: DateLike) -> date:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            if not _ISO_RUN_DATE.fullmatch(value):
                raise ValueError("expected an ISO date or timestamp")
            # Python 3.10's fromisoformat does not accept a trailing Z.
            text = value[:-1] + "+00:00" if value.endswith("Z") else value
            return _coerce(datetime.fromisoformat(text))
        except (ValueError, OverflowError) as exc:
            raise HistoricalRunRejected(
                f"Could not parse run date {value!r}. Refusing to submit: an "
                "unverifiable date cannot be confirmed as live."
            ) from exc
    raise HistoricalRunRejected(
        f"Unsupported run date type {type(value).__name__}. Refusing to submit."
    )


def assert_live_run(run_date: DateLike, *, today: date | None = None) -> date:
    """Return the run date, or raise if it is not today.

    Future dates are refused too — the API rejects them anyway, and a
    forward-dated run is not a live decision either.
    """
    resolved = _coerce(run_date)
    current = today or datetime.now(timezone.utc).date()

    if resolved < current:
        raise HistoricalRunRejected(
            f"Run dated {resolved.isoformat()} is in the past (today is "
            f"{current.isoformat()}). AlphArena ranks live decisions only.\n\n"
            "This is a backtest or replay. Submitting it would put unverified "
            "history on a public leaderboard.\n\n"
            "To import an existing record deliberately, use the /v1/trades/import "
            "endpoint — imported history is labelled as such on the board."
        )
    if resolved > current:
        raise HistoricalRunRejected(
            f"Run dated {resolved.isoformat()} is in the future (today is "
            f"{current.isoformat()}). Refusing to submit."
        )
    return resolved
