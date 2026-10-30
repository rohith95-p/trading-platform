"""Telegram trade messages: entry, exit, floating P&L, news pause. Best-effort; never raises.

Short, phone-first layout (owner 2026-10-30): headline says what happened, two or three lines say the
numbers. Trades push with sound; floating updates and news pauses are silent (alerts.INFO)."""
from __future__ import annotations

import logging
import os
import re
import time as _time
from datetime import datetime, timezone

import MetaTrader5 as mt5

from src.core import alerts

log = logging.getLogger(__name__)

FLOAT_UPDATE_MIN = float(os.environ.get("ULTRA_FLOAT_UPDATE_MIN", "30"))

_last_float_ts = 0.0
_news_alerted: set = set()

_EXIT_REASON = {4: "Stop loss hit", 5: "Take profit hit", 3: "Closed by bot", 0: "Closed manually",
                1: "Closed manually", 2: "Closed manually", 6: "Stop-out"}


def _name(strategy: str) -> str:
    s = re.sub(r"_?V\d+$", "", (strategy or "Unknown").replace("_PYR", ""))
    return s.replace("_", " ").title()


def _money(x: float) -> str:
    return f"{'+' if x >= 0 else '−'}${abs(x):,.2f}"


def _usd(x: float) -> str:
    return f"${x:,.2f}"


def _at(ts: float) -> str:
    return alerts.ist_stamp(datetime.fromtimestamp(ts, timezone.utc))


def _dur(seconds: float) -> str:
    m = int(seconds // 60)
    return f"{m // 60}h {m % 60}m" if m >= 60 else f"{m}m"


def _pnl_at(symbol: str, is_buy: bool, lots: float, entry: float, price: float):
    try:
        kind = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
        return mt5.order_calc_profit(kind, symbol, lots, entry, price)
    except Exception:
        return None


def _safe(fn):
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as e:
            log.warning(f"trade alert {fn.__name__} failed: {e}")
    return wrapper


@_safe
def entry(strategy: str, is_buy: bool, lots: float, price: float, sl: float, tp: float,
          ticket, symbol: str) -> None:
    risk = _pnl_at(symbol, is_buy, lots, price, sl) if sl else None
    reward = _pnl_at(symbol, is_buy, lots, price, tp) if tp else None
    stop = f"Stop {sl:.2f}" + (f" ({_money(risk)})" if risk is not None else "") if sl else "Stop none"
    target = f"Target {tp:.2f}" + (f" ({_money(reward)})" if reward is not None else "") if tp else "Target none"
    alerts.notify(alerts.Alert(
        f"{'BUY' if is_buy else 'SELL'} {lots:.2f} lot · {_name(strategy)}",
        (f"Entry {price:.2f}", f"{stop} · {target}", f"Ticket #{ticket}"),
        alerts.TRADE, icon="🟢" if is_buy else "🔴"))


@_safe
def closed(ticket, deals, pl: float, strategy: str) -> None:
    in_d = [d for d in deals if d.entry == mt5.DEAL_ENTRY_IN]
    out_d = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
    first, last = (in_d[0] if in_d else deals[0]), out_d[-1]
    is_buy = first.type == mt5.DEAL_TYPE_BUY
    acct = mt5.account_info()
    icon = "✅" if pl > 0 else "❌" if pl < 0 else "➖"
    result = _EXIT_REASON.get(getattr(last, "reason", -1), "Closed")
    alerts.notify(alerts.Alert(
        f"{_money(pl)} · {_name(strategy)}",
        (f"{'BUY' if is_buy else 'SELL'} {first.volume:.2f} · {first.price:.2f} → {last.price:.2f} · "
         f"held {_dur(last.time - first.time)}",
         f"{result}" + (f" · Balance {_usd(acct.balance)}" if acct else "")),
        alerts.TRADE, icon=icon))


@_safe
def maybe_floating_update(positions) -> None:
    global _last_float_ts
    if FLOAT_UPDATE_MIN <= 0:
        return
    now = _time.time()
    if not positions:
        _last_float_ts = now
        return
    if now - _last_float_ts < FLOAT_UPDATE_MIN * 60:
        return
    _last_float_ts = now
    total = sum(p.profit + p.swap for p in positions)
    lines = [f"{'BUY' if p.type == mt5.POSITION_TYPE_BUY else 'SELL'} {p.volume:.2f} {_name(p.comment)} "
             f"{_money(p.profit + p.swap)} ({_dur(now - p.time)})" for p in positions]
    acct = mt5.account_info()
    if acct:
        lines.append(f"Equity {_usd(acct.equity)}")
    n = len(positions)
    alerts.notify(alerts.Alert(f"{n} open trade{'s' if n > 1 else ''} · {_money(total)}", tuple(lines),
                               alerts.INFO, icon="📊"))


@_safe
def news_pause(reason: str) -> None:
    key = re.sub(r"\(.*?\)|\d+ ?min", "", reason).strip()
    if key in _news_alerted:
        return
    _news_alerted.add(key)
    alerts.notify(alerts.Alert(f"News pause: {reason}",
                               ("No new trades until it passes. Open trades keep their stop and target.",),
                               alerts.INFO, icon="📰"))
