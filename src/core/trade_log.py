"""Structured event log -- Part IV.8 of REAL_MONEY_READINESS.md.

The stated goal there: "any trading day can be fully reconstructed from the log
alone." That was never built. `logs/trade_ledger.jsonl` existed but nothing
wrote to it -- a single stale line from 2026-08-31 was its entire contents, so
the only real record of live behaviour was free-text `main_loop.log` plus the
broker's own deal history.

This is the missing piece, and it is also the substrate for the 8-week paper
test (I.9): without a machine-readable record of what the bot did and why, a
weekly "live vs backtest" comparison can't be automated.

Writes JSON lines to logs/trades/YYYY-MM-DD.jsonl (IST calendar day, rotated
daily). Every record carries: ts (unix), ist (readable), kind, and a payload.
Never raises -- a logging failure must not take down the trading loop.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(_ROOT, "logs", "trades")

# Event kinds, so readers can filter without string-guessing.
SIGNAL = "signal"            # a strategy produced (or was denied) a signal
ORDER = "order"              # an order was sent, with the broker's reply
POSITION_CLOSED = "closed"   # a position finished, with realised P&L
GATE = "gate"                # a gate/breaker/cap decision
LIFECYCLE = "lifecycle"      # startup, shutdown, reconnect, kill switch
ERROR = "error"


def _path(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(IST)
    return os.path.join(LOG_DIR, f"{now.date().isoformat()}.jsonl")


def write(kind: str, **payload: Any) -> None:
    """Append one structured event. Silent on failure by design."""
    try:
        now = datetime.now(IST)
        rec = {
            "ts": int(now.timestamp()),
            "ist": now.strftime("%Y-%m-%d %H:%M:%S"),
            "kind": kind,
            **payload,
        }
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(_path(now), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    except Exception as e:  # never let logging break trading
        log.warning(f"trade_log write failed ({kind}): {e}")


# --- Convenience wrappers, so call sites stay readable ---------------------

# A signal that reaches a REAL gate and is blocked is worth a Telegram line (2026-10-21: a valid FVG sell was blocked by a
# risk halt and nobody was told). Routine blocks stay silent, and each (leg, direction, reason) alerts at most once an hour.
_QUIET_REASON_PREFIXES = ("D1 bias gate", "measurement-only", "reversal cooldown", "Highlander", "already acted")
_BLOCKED_ALERT_GAP_S = 3600
_blocked_alert_last: Dict[Any, float] = {}


def _maybe_alert_blocked(strategy: str, direction: str, reason: str) -> None:
    try:
        if not reason or reason.startswith(_QUIET_REASON_PREFIXES):
            return
        import re
        import time as _t
        key = (strategy, direction, re.sub(r"\d+", "#", reason))
        now = _t.time()
        if now - _blocked_alert_last.get(key, 0.0) < _BLOCKED_ALERT_GAP_S:
            return
        _blocked_alert_last[key] = now
        from src.core import alerts
        alerts.send(f"Signal blocked: {strategy} {direction} -- {reason}", severity=alerts.INFO)
    except Exception as e:                       # alerting must never break trading
        log.debug(f"blocked-signal alert skipped: {e}")


def signal(strategy: str, direction: str, action: str, reason: str = "", **ctx) -> None:
    """action: 'fired' | 'blocked' | 'deduped' | 'queued'."""
    write(SIGNAL, strategy=strategy, direction=direction, action=action, reason=reason, **ctx)
    if action == "blocked":
        _maybe_alert_blocked(strategy, direction, reason)


def order(strategy: str, direction: str, lots: float, price: Optional[float] = None,
          sl: Optional[float] = None, tp: Optional[float] = None,
          retcode: Optional[int] = None, ticket: Optional[int] = None,
          comment: str = "", dedup_key: Optional[str] = None,
          bar_time: Optional[int] = None, **ctx) -> None:
    write(ORDER, strategy=strategy, direction=direction, lots=lots, price=price,
          sl=sl, tp=tp, retcode=retcode, ticket=ticket, comment=comment,
          dedup_key=dedup_key, bar_time=bar_time, **ctx)


def position_closed(strategy: str, ticket: Optional[int], profit: float, **ctx) -> None:
    write(POSITION_CLOSED, strategy=strategy, ticket=ticket, profit=profit, **ctx)


def gate(name: str, allowed: bool, reason: str = "", **ctx) -> None:
    write(GATE, gate=name, allowed=allowed, reason=reason, **ctx)


def lifecycle(event: str, **ctx) -> None:
    write(LIFECYCLE, event=event, **ctx)


def error(where: str, message: str, **ctx) -> None:
    write(ERROR, where=where, message=message, **ctx)


# --- Reading back, for the weekly paper-test review & dedup restart ---------

def load_order_dedup_keys(days: int = 2) -> set[tuple[int, int, str]]:
    """Scan recent trade logs and return set of (magic, bar_time, direction) tuples.
    Persists across process restarts so duplicate fills can never occur."""
    keys: set[tuple[int, int, str]] = set()
    now = datetime.now(IST)
    for d in range(days):
        day = (now - timedelta(days=d)).date()
        p = os.path.join(LOG_DIR, f"{day.isoformat()}.jsonl")
        if not os.path.exists(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if rec.get("kind") == ORDER:
                        magic = rec.get("magic")
                        bar_time = rec.get("bar_time") or rec.get("candle")
                        direction = rec.get("direction")
                        if magic is not None and bar_time is not None and direction is not None:
                            keys.add((int(magic), int(bar_time), str(direction).upper()))
                        elif rec.get("dedup_key"):
                            parts = str(rec["dedup_key"]).split(":")
                            if len(parts) == 3:
                                try:
                                    keys.add((int(parts[0]), int(parts[1]), str(parts[2]).upper()))
                                except ValueError:
                                    pass
        except Exception as e:
            log.warning(f"Failed to read dedup keys from {p}: {e}")
    return keys


def read_range(start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """All events with ts in [start, end), across daily files."""
    out: List[Dict[str, Any]] = []
    day = start.astimezone(IST).date()
    last = end.astimezone(IST).date()
    while day <= last:
        p = os.path.join(LOG_DIR, f"{day.isoformat()}.jsonl")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    if start.timestamp() <= rec.get("ts", 0) < end.timestamp():
                        out.append(rec)
        day += timedelta(days=1)
    return out
