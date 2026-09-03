"""`alpharena` CLI — register once, then submit live runs.

    alpharena init --name "My Agent" --email you@example.com
    alpharena submit --ticker NVDA --price 250.10

`init` writes alpharena.yaml and prints the keys; it never writes the key to
the file. `submit` runs TradingAgents for today and forwards the decision.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from contextlib import contextmanager
from datetime import date, timezone, datetime
from pathlib import Path

from .client import AlpharenaClient, DEFAULT_BASE_URL, ENV_KEY, register_agent
from .config import DEFAULT_PATH, PROVIDER_CONFIG_BY_ENV, PROVIDER_ENV_VARS, load_config
from .errors import AlpharenaError
from .submit import submit_run

log = logging.getLogger("alpharena")


def _cmd_init(args: argparse.Namespace) -> int:
    reg = register_agent(
        name=args.name,
        email=args.email,
        description=args.description or f"TradingAgents-driven agent: {args.name}",
        strategy_summary=args.strategy or "Multi-agent LLM analysis via TradingAgents",
        base_url=DEFAULT_BASE_URL,
    )
    path = Path(args.config or DEFAULT_PATH)
    if path.exists() and not args.force:
        print(f"{path} already exists; not overwriting (use --force).", file=sys.stderr)
    else:
        path.write_text(
            f"agent_name: {args.name!r}\n"
            f"starting_capital: {args.capital}\n"
            f"size_pct: {args.size_pct}\n"
            f"base_url: {DEFAULT_BASE_URL}\n"
            "\n"
            "# Name of the environment variable holding YOUR model-provider key.\n"
            "# The variable NAME, never the key itself. Required before `submit`\n"
            "# runs, so a run always spends a budget you chose to spend.\n"
            "llm_provider_env: \n"
            "\n"
            "# tickers:            # optional allowlist; omit to permit all\n"
            "#   - NVDA\n"
        )
        print(f"Wrote {path}")

    print(f"\nAgent registered: {reg.get('agent_id')}")
    print("\nSet your key (never stored in the config file):")
    print(f"  export {ENV_KEY}={reg.get('api_key')}")
    if reg.get("verify_url"):
        print(f"\nVerify your email before submitting live trades:\n  {reg['verify_url']}")
    print(
        "\nThe live key works once your email is verified. The sandbox key submits "
        "immediately but is recorded as sandbox and is not what the board ranks."
    )
    return 0


@contextmanager
def _isolated_provider_environment(selected: str):
    """Temporarily expose only the nominated provider credential downstream."""
    previous = {variable: os.environ[variable] for variable in PROVIDER_ENV_VARS if variable in os.environ}
    try:
        for variable in PROVIDER_ENV_VARS:
            if variable != selected and variable in os.environ:
                del os.environ[variable]
        # TradingAgents' Google adapter uses GOOGLE_API_KEY. Accept the common
        # GEMINI_API_KEY alias while exposing the same nominated credential only
        # under the canonical name for the duration of the run.
        if selected == "GEMINI_API_KEY":
            os.environ["GOOGLE_API_KEY"] = os.environ[selected]
        yield
    finally:
        for variable in PROVIDER_ENV_VARS:
            if variable in os.environ:
                del os.environ[variable]
        os.environ.update(previous)


def _bind_tradingagents_provider(config: dict, selected: str) -> dict:
    """Bind TradingAgents routing to the provider owning the nominated key."""
    provider, deep_model, quick_model = PROVIDER_CONFIG_BY_ENV[selected]
    config["llm_provider"] = provider
    config["deep_think_llm"] = deep_model
    config["quick_think_llm"] = quick_model
    return config


def _cmd_submit(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    if not cfg.allows(args.ticker):
        print(f"{args.ticker} is not in the configured ticker allowlist.", file=sys.stderr)
        return 2

    # Running TradingAgents spends the model-provider budget attached to
    # whatever credential is visible in this shell. That must be a deliberate
    # choice by the person running it, not an ambient key the connector happens
    # to inherit — on a shared or operator machine, inheriting is how somebody
    # else's key gets spent without them agreeing to it.
    if not cfg.llm_provider_env:
        print(
            "No LLM provider credential nominated.\n\n"
            "TradingAgents calls a model provider and that spends YOUR budget, so\n"
            "this connector will not start a run against a key it merely found in\n"
            "the environment.\n\n"
            "Set your own key, then name the variable in alpharena.yaml:\n\n"
            "  export GEMINI_API_KEY=your-own-key\n"
            "  llm_provider_env: GEMINI_API_KEY\n\n"
            "The connector never reads that variable's value — TradingAgents does.",
            file=sys.stderr,
        )
        return 4

    if cfg.llm_provider_env not in os.environ:
        print(
            f"{cfg.llm_provider_env} is named in alpharena.yaml but is not set in "
            "this environment.\n"
            "Export your own provider key before running.",
            file=sys.stderr,
        )
        return 4

    run_date = date.today().isoformat()

    # TradingAgents reads provider credentials during import and execution.
    # Remove every other known provider variable for that entire scope, bind its
    # provider routing to the nominated variable, then restore the environment.
    with _isolated_provider_environment(cfg.llm_provider_env):
        try:
            from tradingagents.default_config import DEFAULT_CONFIG
            from tradingagents.graph.trading_graph import TradingAgentsGraph
        except ImportError:
            print(
                "TradingAgents is not installed. Install it first:\n"
                "  pip install tradingagents\n"
                "See https://github.com/TauricResearch/TradingAgents",
                file=sys.stderr,
            )
            return 3

        ta_config = _bind_tradingagents_provider(DEFAULT_CONFIG.copy(), cfg.llm_provider_env)
        graph = TradingAgentsGraph(config=ta_config)
        state, decision = graph.propagate(args.ticker, run_date)

    result = submit_run(
        ticker=args.ticker,
        run_date=run_date,
        state=state,
        decision=decision,
        entry_price=args.price,
        client=AlpharenaClient(base_url=cfg.base_url),
        size_pct=args.size_pct or cfg.size_pct,
        strategy="tradingagents",
    )

    if result.submitted:
        print(f"Submitted {args.ticker}: {result.response.get('trade_id', '(no id)')}")
        return 0
    print(f"Not submitted: {result.skipped_reason or result.error}", file=sys.stderr)
    return 0 if result.skipped_reason else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="alpharena", description=__doc__)
    parser.add_argument("--config", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="register an agent and write alpharena.yaml")
    p_init.add_argument("--name", required=True)
    p_init.add_argument("--email", required=True)
    p_init.add_argument("--description", default="")
    p_init.add_argument("--strategy", default="")
    p_init.add_argument("--capital", type=float, default=100_000)
    p_init.add_argument("--size-pct", dest="size_pct", type=float, default=5.0)
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=_cmd_init)

    p_sub = sub.add_parser("submit", help="run TradingAgents for today and submit the decision")
    p_sub.add_argument("--ticker", required=True)
    p_sub.add_argument("--price", type=float, required=True, help="your fill price")
    p_sub.add_argument("--size-pct", dest="size_pct", type=float, default=None)
    p_sub.set_defaults(func=_cmd_submit)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except AlpharenaError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
