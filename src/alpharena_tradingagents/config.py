"""Connector configuration.

One file, `alpharena.yaml`, holding everything except the API key. The key comes
from ALPHARENA_API_KEY only — a config file gets committed to somebody's repo
eventually, and it will not be ours that leaked it.

Parsed without a YAML dependency: the schema is five flat scalars and one list,
so requiring PyYAML would cost an install step for no benefit. Anything more
complex than this subset raises rather than guessing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .errors import ConfigError

DEFAULT_PATH = "alpharena.yaml"


@dataclass
class Config:
    agent_name: str = ""
    starting_capital: float = 100_000.0
    size_pct: float = 5.0
    base_url: str = "https://alpharena.io"
    tickers: List[str] = field(default_factory=list)

    def allows(self, ticker: str) -> bool:
        """Empty allowlist means every ticker is permitted."""
        return not self.tickers or ticker.upper() in {t.upper() for t in self.tickers}


def _strip_comment(line: str) -> str:
    # Only strips a comment that starts the token — avoids mangling a value
    # containing '#', which a URL legitimately can.
    out, in_quotes = [], ""
    for ch in line:
        if in_quotes:
            out.append(ch)
            if ch == in_quotes:
                in_quotes = ""
        elif ch in "\"'":
            in_quotes = ch
            out.append(ch)
        elif ch == "#" and (not out or out[-1] in " \t"):
            break
        else:
            out.append(ch)
    return "".join(out).strip()


# Provider credentials must never live in this file, and must never be read by
# this connector. TradingAgents authenticates to the model provider on its own,
# with the operator's own account. Anything that looks like a provider secret is
# rejected loudly rather than silently ignored — a config that quietly accepts a
# key teaches people it is a reasonable place to put one.
_CREDENTIAL_HINTS = (
    "openai", "anthropic", "gemini", "google_api", "groq", "mistral", "deepseek",
    "qwen", "azure", "bedrock", "together", "openrouter", "llm_key", "secret",
    "token", "password", "credential",
)


def _looks_like_credential(key: str) -> bool:
    lowered = key.lower()
    return any(hint in lowered for hint in _CREDENTIAL_HINTS) or lowered.endswith("_key")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def load_config(path: Optional[str] = None) -> Config:
    target = Path(path or os.environ.get("ALPHARENA_CONFIG", DEFAULT_PATH))
    cfg = Config()
    if not target.exists():
        if path:  # explicitly asked for, so its absence is an error
            raise ConfigError(f"Config file not found: {target}")
        return cfg  # defaults are usable; the CLI can write one

    pending_list: Optional[str] = None
    for raw in target.read_text().splitlines():
        line = _strip_comment(raw)
        if not line:
            continue
        if line.startswith("- ") and pending_list == "tickers":
            cfg.tickers.append(_unquote(line[2:].strip()).upper())
            continue
        if ":" not in line:
            raise ConfigError(f"Cannot parse line in {target}: {raw!r}")
        key, _, value = line.partition(":")
        key, value = key.strip(), _unquote(value.strip())
        pending_list = key if not value else None

        if key == "agent_name":
            cfg.agent_name = value
        elif key == "starting_capital":
            cfg.starting_capital = float(value)
        elif key == "size_pct":
            cfg.size_pct = float(value)
        elif key == "base_url":
            cfg.base_url = value.rstrip("/")
        elif key == "tickers":
            if value:  # inline form: tickers: [NVDA, AAPL]
                cfg.tickers = [t.strip().upper() for t in value.strip("[]").split(",") if t.strip()]
        elif key.startswith("api_key"):
            raise ConfigError(
                "Remove api_key from alpharena.yaml. The key is read from "
                "ALPHARENA_API_KEY so it never lands in a committed file."
            )
        elif _looks_like_credential(key):
            raise ConfigError(
                f"Remove {key!r} from alpharena.yaml.\n\n"
                "This connector never reads, stores or transmits LLM provider "
                "credentials. TradingAgents authenticates to your model provider "
                "itself — configure that key in TradingAgents' own config or "
                "environment, using YOUR account.\n\n"
                "Nothing in this file is sent anywhere except AlphArena."
            )
    return cfg
