"""What the bot tells the outside world about itself.

Pulled out of main_loop.py on 2026-11-01: the status snapshot the watchdog reads
for its hourly pulse (the watchdog has no MT5 session of its own), the ops
heartbeat, and the alert for positions on our symbol that are not ours.

Nothing here may raise or block -- a failed status write must never stop a scan.
"""
from __future__ import annotations

import logging
import time as _time
from typing import Any

from src.core import atlas_bridge, ops, resilience, scope, trade_log

log = logging.getLogger(__name__)

mt5: Any = None          # set by main_loop at import time

SYMBOL = ""              # set by main_loop at import time

_LAST_HB = {"t": None}
_FOREIGN_SEEN: dict = {"tickets": None}


def bind(mt5_module: Any, symbol: str) -> None:
    """main_loop hands over its terminal handle and symbol."""
    global mt5, SYMBOL
    mt5 = mt5_module
    SYMBOL = symbol


def _alert_foreign_exposure(foreign) -> None:
    """Alert when the foreign ticket set changes, and re-alert every 30 min while it persists."""
    tickets = tuple(sorted(p.ticket for p in foreign))
    if tickets == _FOREIGN_SEEN["tickets"] and (not foreign or _time.time() - _FOREIGN_SEEN.get("t", 0) < 1800):
        return
    _FOREIGN_SEEN["t"] = _time.time()
    prev, _FOREIGN_SEEN["tickets"] = _FOREIGN_SEEN["tickets"], tickets
    if not foreign:
        if prev:
            log.info("Foreign exposure cleared.")
        return
    rep = scope.foreign_report(foreign)
    msg = (f"FOREIGN EXPOSURE DETECTED on {SYMBOL}: {rep}. New Ultra Core entries are blocked; "
           f"foreign positions are left untouched.")
    log.error(msg)
    trade_log.gate("foreign_exposure", allowed=False, reason="another system holds positions on this symbol",
                   foreign=rep, risk_scope="account")
    try:
        from src.core import alerts
        alerts.send(f"Other trades found on {SYMBOL}: new entries blocked", alerts.CRITICAL,
                    context={"found": rep}, action="Close them in MT5 (the bot never touches them).")
    except Exception:
        pass


def _write_status(fetcher) -> None:
    """logs/status.json for the watchdog's hourly pulse (the watchdog has no MT5 session). Never raises."""
    try:
        acct = mt5.account_info()
        if acct is None:
            return
        own = fetcher.get_own_positions()
        snap = {"login": acct.login, "server": acct.server, "balance": float(acct.balance),
                "equity": float(acct.equity), "open": len(own),
                "floating": float(sum(p.profit + p.swap for p in own)),
                "today": float(fetcher.get_todays_closed_pl())}
        eng, st = atlas_bridge.RUNTIME.get("engine"), atlas_bridge.RUNTIME.get("state")
        if eng and st:
            snap.update(trailing_floor=float(eng.trailing_floor(st)), daily_floor=float(eng.daily_floor(st)))
        resilience.write_status(snap)
    except Exception as e:
        log.debug(f"status snapshot skipped: {e}")


def _push_ops_heartbeat(fetcher, drawdown_shutdown: bool) -> None:
    """Send the status heartbeat. Never raises and never blocks the loop (push runs in a daemon thread)."""
    try:
        now = _time.time()
        interval = None if _LAST_HB["t"] is None else now - _LAST_HB["t"]
        _LAST_HB["t"] = now
        tick = fetcher.get_tick()
        quote_age = (now - float(tick.time)) if tick is not None else None
        orders = mt5.orders_get(symbol=SYMBOL)
        acct = mt5.account_info()
        mode = {0: "demo", 1: "contest", 2: "real"}.get(getattr(acct, "trade_mode", None), "unknown") if acct else "unknown"
        payload = ops.build_status(
            account=mode, scan_interval_s=interval, quote_age_s=quote_age,
            open_positions=len(fetcher.get_own_positions()), pending_orders=len(orders) if orders else 0,
            daily_pnl=fetcher.get_todays_closed_pl(), drawdown_shutdown=drawdown_shutdown)
        payload["foreign_positions"] = len(fetcher.get_foreign_positions())
        ops.push_status(payload)
    except Exception as e:
        log.debug(f"ops heartbeat skipped: {e}")
