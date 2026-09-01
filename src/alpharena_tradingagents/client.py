"""Thin AlphArena API client.

Auth is read from ALPHARENA_API_KEY only — never from the config file, never
logged (spec Requirement 5). The key is redacted from every error path.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Mapping, Optional

from .errors import ConfigError, SubmissionRejected

DEFAULT_BASE_URL = "https://alpharena.io"
ENV_KEY = "ALPHARENA_API_KEY"


class AlpharenaClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, api_key: Optional[str] = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        key = api_key or os.environ.get(ENV_KEY, "")
        if not key.strip():
            raise ConfigError(
                f"{ENV_KEY} is not set. Export your AlphArena API key; the connector "
                "never reads it from alpharena.yaml."
            )
        self._api_key = key.strip()

    def _post(self, path: str, payload: Mapping[str, Any]) -> dict:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": "alpharena-tradingagents",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:500]
            # Never echo the request — it carries the key in the header.
            raise SubmissionRejected(f"AlphArena returned {exc.code}: {body}") from None
        except urllib.error.URLError as exc:
            raise SubmissionRejected(f"Could not reach AlphArena: {exc.reason}") from None

    def submit_trade(
        self,
        *,
        ticker: str,
        direction: str,
        entry_price: float,
        size_pct: Optional[float] = None,
        thesis: str = "",
        confidence: Optional[float] = None,
        strategy: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "ticker": ticker,
            "direction": direction,
            "entry_price": entry_price,
            "asset_type": "stock",  # equities only; no crypto path exists server-side
        }
        if size_pct is not None:
            payload["size_pct"] = size_pct
        if thesis:
            payload["thesis"] = thesis
        if confidence is not None:
            payload["confidence"] = confidence
        if strategy:
            payload["strategy"] = strategy
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        # opened_at is deliberately omitted. The server stamps now, which makes a
        # backdated submission impossible from this client by construction —
        # belt and braces alongside the guard.
        return self._post("/api/v1/trades", payload)
