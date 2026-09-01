"""Submit live TradingAgents decisions to the AlphArena leaderboard.

Equities only. Live-forward runs only — see guard.py for why.
"""

from .client import AlpharenaClient, register_agent
from .errors import AlpharenaError, ConfigError, HistoricalRunRejected, SubmissionRejected
from .config import Config, load_config
from .guard import assert_live_run
from .submit import SubmitResult, submit_run
from .thesis import build_thesis

__all__ = [
    "AlpharenaClient", "register_agent", "Config", "load_config", "AlpharenaError", "ConfigError", "HistoricalRunRejected",
    "SubmissionRejected", "assert_live_run", "SubmitResult", "submit_run", "build_thesis",
]
__version__ = "0.1.0"
