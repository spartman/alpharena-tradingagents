# alpharena-tradingagents

Submit **live** [TradingAgents](https://github.com/TauricResearch/TradingAgents)
decisions to the [AlphArena](https://alpharena.io) leaderboard — with the
bull/bear debate carried through as the trade's thesis.

TradingAgents is backtest-focused and has no live scoreboard. AlphArena is the
scoreboard. This is the missing half of that loop.

## Why the thesis matters

AlphArena locks a written thesis at submission and never allows it to be edited —
that's what "documented" means on the leaderboard. Most integrations would have
to invent one. TradingAgents already produces it: the bull researcher, the bear
researcher and the risk manager's sign-off are a by-product of how the framework
works. This connector forwards them intact.

## Install

```bash
pip install alpharena-tradingagents
export ALPHARENA_API_KEY=your_key   # never read from a config file
```

## Use

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
from alpharena_tradingagents import AlpharenaClient, submit_run
from datetime import date

ta = TradingAgentsGraph(config=DEFAULT_CONFIG.copy())
today = date.today().isoformat()
state, decision = ta.propagate("NVDA", today)

result = submit_run(
    ticker="NVDA",
    run_date=today,
    state=state,
    decision=decision,
    entry_price=fill_price,       # your fill
    client=AlpharenaClient(),
    size_pct=5.0,
)
print(result.submitted, result.skipped_reason or result.error or "")
```

## Live runs only — by design

The connector **refuses to submit a historical or replayed run**, and refuses
before it touches the network.

`ta.propagate(ticker, date)` takes the date explicitly, so a backtest is
distinguishable from a live decision. AlphArena ranks on verified live
performance; letting replayed backtests onto a public board would make the
ranking self-reported, which is the one thing it claims not to be.

If you want an existing record on the board, that's a deliberate act with its own
endpoint — `/v1/trades/import` — and imported history is **labelled as imported**
on the leaderboard rather than passed off as live.

An unparseable date is refused too. A missed trade costs one row; an accepted
backtest costs the credibility of the board.

## It will not break your run

A rejected or failed submission is logged and returned as a `SubmitResult`.
Nothing raises into your TradingAgents run.

## Scope

Equities only. `asset_type` is always `stock` — AlphArena has no crypto path.

## Development

```bash
python -m pytest tests/ -q
```
