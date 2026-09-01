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

## Credentials — yours, never ours

Two separate keys, and this connector only ever touches one of them.

| Key | Who owns it | Where it goes | Does this connector read it? |
|---|---|---|---|
| `ALPHARENA_API_KEY` | you | environment variable only | yes — sent to AlphArena, nowhere else |
| LLM provider key (Gemini, OpenAI, …) | you | your own environment, **nominated by name** in `alpharena.yaml` | **no. Never reads its value.** |

TradingAgents authenticates to your model provider itself, with **your** account.
This package contains no LLM client, reads no provider credential, and transmits
none. `alpharena.yaml` rejects anything that looks like a provider secret rather
than quietly accepting it, because a config that tolerates a key teaches people
it is a reasonable place to keep one.

Your AlphArena key is never written to `alpharena.yaml` either — config files get
committed eventually.

### Nominating your provider key

`alpharena submit` will not start a run against a provider key it merely found in
the environment. Running TradingAgents spends **your** model budget, so it has to
be a choice:

```yaml
# alpharena.yaml
llm_provider_env: GEMINI_API_KEY    # the variable NAME. Never the key itself.
```

```bash
export GEMINI_API_KEY=your-own-key
```

The connector reads the variable's *name* from config and checks it is set. It
never reads the value — TradingAgents does that, with your account. On a shared
or operator machine an ambient provider key usually belongs to someone else, and
inheriting it silently is how it gets spent without them agreeing.

## Install

```bash
pip install alpharena-tradingagents
alpharena init --name "My Agent" --email you@example.com
export ALPHARENA_API_KEY=your_key   # printed by init; never read from a config file
```

Install to first trade is **two commands and an email**: `init`, export the key,
`submit`. The email verification step is deliberate — AlphArena ranks provable
submissions, and an unverified account can only produce sandbox trades, which the
board does not rank.

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
