"""Atlas MCP API monitoring — periodic account health queries.

Connects to https://mcp.atlasfunded.com/api/mcp using the Atlas MCP API key
(read from ATLAS_MCP_KEY env var). All calls are best-effort: a failure logs a
warning and returns None; the trading loop is never blocked or broken by a
monitoring failure.

No imports from MetaTrader5 or any trading module — this is a pure HTTP client.
"""
from __future__ import annotations

import json
import logging
import os
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

MCP_URL = "https://mcp.atlasfunded.com/api/mcp"
_HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _api_key() -> Optional[str]:
    return os.environ.get("ATLAS_MCP_KEY")


def _call(method: str, params: Optional[Dict] = None, timeout: float = 15.0) -> Optional[Any]:
    """JSON-RPC call to the Atlas MCP endpoint. Returns the result or None on error."""
    key = _api_key()
    if not key:
        return None
    import urllib.request
    import urllib.error
    headers = {**_HEADERS_BASE, "Authorization": f"Bearer {key}"}
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": method, "arguments": params or {}},
    }).encode()
    req = urllib.request.Request(MCP_URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            # SSE responses may have "data: " prefix lines
            lines = [l for l in raw.strip().splitlines() if l.startswith("data: ")]
            if lines:
                raw = lines[-1].removeprefix("data: ")
            doc = json.loads(raw)
            result = doc.get("result", {})
            content = result.get("content", [])
            for item in content:
                if item.get("type") == "text":
                    try:
                        return json.loads(item["text"])
                    except (json.JSONDecodeError, KeyError):
                        return item.get("text")
            return result
    except Exception as exc:
        log.debug(f"Atlas MCP call {method} failed: {exc}")
        return None


@dataclass
class AtlasMCPSnapshot:
    """Latest MCP monitoring snapshot."""
    ts: float = 0.0
    account_rules: Optional[Dict] = None
    profile: Optional[Dict] = None
    news_events: Optional[List[Dict]] = None
    error: Optional[str] = None


class AtlasMCPMonitor:
    """Best-effort background poller for Atlas account health via MCP API."""

    def __init__(self, poll_interval: float = 300.0):
        self.poll_interval = poll_interval
        self.snapshot = AtlasMCPSnapshot()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def available(self) -> bool:
        return _api_key() is not None

    def start(self) -> None:
        if not self.available:
            log.info("ATLAS MCP: no ATLAS_MCP_KEY env var — monitoring disabled.")
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="atlas-mcp")
        self._thread.start()
        log.info("ATLAS MCP: background monitor started.")

    def stop(self) -> None:
        self._stop.set()

    def _poll_loop(self) -> None:
        self._refresh()  # immediate first poll
        while not self._stop.wait(self.poll_interval):
            self._refresh()

    def _refresh(self) -> None:
        try:
            snap = AtlasMCPSnapshot(ts=time.time())
            snap.account_rules = _call("get_account_rules")
            snap.news_events = self._fetch_news()
            self.snapshot = snap
        except Exception as exc:
            log.debug(f"Atlas MCP refresh error: {exc}")
            self.snapshot.error = str(exc)

    def _fetch_news(self) -> Optional[List[Dict]]:
        result = _call("get_news_calendar")
        if isinstance(result, dict):
            return result.get("events", [])
        return None

    def get_news_events(self) -> List[Dict]:
        """High-impact news events from the latest MCP snapshot (for rule engine)."""
        evts = self.snapshot.news_events
        return evts if evts else []

    def get_breach_proximity(self) -> Optional[Dict]:
        """Latest account rules / breach proximity from MCP."""
        return self.snapshot.account_rules

    def force_refresh(self) -> AtlasMCPSnapshot:
        """Synchronous refresh — use sparingly (blocks for up to 15s)."""
        self._refresh()
        return self.snapshot
