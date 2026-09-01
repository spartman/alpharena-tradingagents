"""Exceptions raised by the connector.

Every one of these is caught by the submit path and logged rather than raised
into the caller's run — Requirement 7 of the spec: a rejected submission must
never crash a TradingAgents run.
"""


class AlpharenaError(Exception):
    """Base class for connector errors."""


class ConfigError(AlpharenaError):
    """Missing or invalid configuration."""


class HistoricalRunRejected(AlpharenaError):
    """The run being submitted is dated in the past.

    AlphArena ranks live, forward-dated decisions. Backfilled records read as
    fabricated — the leaderboard's whole claim is "verified, not self-reported"
    — so the connector refuses them at the client rather than letting a replayed
    backtest land on a public ranking.

    History belongs on /v1/trades/import, which labels it as imported.
    """


class SubmissionRejected(AlpharenaError):
    """The API declined the trade."""
