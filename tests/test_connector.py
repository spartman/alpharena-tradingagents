"""Tests for the parts that protect the leaderboard, not the happy path.

The live-forward guard is the reason this connector is safe to hand to 102k
strangers. It gets the most coverage.
"""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alpharena_tradingagents.errors import HistoricalRunRejected  # noqa: E402
from alpharena_tradingagents.guard import assert_live_run  # noqa: E402
from alpharena_tradingagents.submit import parse_direction, submit_run, SubmitResult  # noqa: E402
from alpharena_tradingagents.thesis import build_thesis, SOFT_CHAR_LIMIT  # noqa: E402

TODAY = date(2026, 9, 1)


class TestLiveForwardGuard:
    def test_accepts_today(self):
        assert assert_live_run("2026-09-01", today=TODAY) == TODAY

    @pytest.mark.parametrize("stale", ["2024-03-01", "2026-08-31", "2020-01-01"])
    def test_refuses_backtest_dates(self, stale):
        with pytest.raises(HistoricalRunRejected):
            assert_live_run(stale, today=TODAY)

    def test_refuses_future(self):
        with pytest.raises(HistoricalRunRejected):
            assert_live_run("2026-09-02", today=TODAY)

    def test_refuses_unparseable_rather_than_passing_it_through(self):
        # An unverifiable date must not default to "probably live".
        with pytest.raises(HistoricalRunRejected):
            assert_live_run("last tuesday", today=TODAY)

    def test_accepts_datetime_and_date_objects(self):
        assert assert_live_run(datetime(2026, 9, 1, 14, 30, tzinfo=timezone.utc), today=TODAY) == TODAY
        assert assert_live_run(TODAY, today=TODAY) == TODAY

    def test_error_names_the_import_path(self):
        with pytest.raises(HistoricalRunRejected) as exc:
            assert_live_run("2024-03-01", today=TODAY)
        assert "/v1/trades/import" in str(exc.value)


class TestDirection:
    @pytest.mark.parametrize("decision,expected", [
        ("BUY", "long"), ("STRONG BUY", "long"), ("SELL", "short"),
        ("HOLD", None), ("", None), (None, None), ("maybe?", None),
    ])
    def test_parses(self, decision, expected):
        assert parse_direction(decision) == expected


class TestThesis:
    def test_carries_debate_sections(self):
        state = {"investment_debate_state": {"bull_history": "bull text", "bear_history": "bear text"}}
        out = build_thesis(state, "BUY")
        assert "bull text" in out and "bear text" in out and "Decision: BUY" in out

    def test_returns_empty_rather_than_inventing_one(self):
        assert build_thesis({}, None) == ""

    def test_respects_soft_limit(self):
        state = {"investment_debate_state": {"bull_history": "x" * (SOFT_CHAR_LIMIT + 5000)}}
        out = build_thesis(state, "BUY")
        assert len(out) <= SOFT_CHAR_LIMIT + 200
        assert "truncated" in out


class _StubClient:
    def __init__(self):
        self.calls = []

    def submit_trade(self, **kwargs):
        self.calls.append(kwargs)
        return {"trade_id": "t1"}


class TestSubmitRun:
    def test_backtest_never_reaches_the_network(self):
        client = _StubClient()
        result = submit_run(
            ticker="NVDA", run_date="2024-03-01", state={}, decision="BUY",
            entry_price=100.0, client=client,
        )
        assert result.submitted is False
        assert client.calls == [], "a historical run must not hit the API at all"

    def test_hold_is_not_a_trade(self):
        client = _StubClient()
        result = submit_run(
            ticker="NVDA", run_date=date.today(), state={}, decision="HOLD",
            entry_price=100.0, client=client,
        )
        assert result.submitted is False and client.calls == []

    def test_live_buy_submits_as_equity(self):
        client = _StubClient()
        result = submit_run(
            ticker="NVDA", run_date=date.today(), state={
                "investment_debate_state": {"bull_history": "demand accelerating"}},
            decision="BUY", entry_price=100.0, client=client,
        )
        assert result.submitted is True
        assert client.calls[0]["direction"] == "long"
        assert "demand accelerating" in client.calls[0]["thesis"]

    def test_api_failure_does_not_raise_into_the_caller(self):
        class Boom:
            def submit_trade(self, **kwargs):
                raise RuntimeError("network on fire")

        result = submit_run(
            ticker="NVDA", run_date=date.today(), state={}, decision="BUY",
            entry_price=100.0, client=Boom(),
        )
        assert isinstance(result, SubmitResult)
        assert result.submitted is False and "network on fire" in result.error
