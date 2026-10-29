"""Telegram trade messages: entry, exit, floating P&L, news pause. Best-effort; never raises."""
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
    return f"{'+' if x >= 0 else '-'}${abs(x):.2f}"


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
    alerts.send_html(alerts.table(f"{'🟢' if is_buy else '🔴'} TRADE OPENED", [
        ("Time", alerts.ist_stamp()),
        ("Strategy", _name(strategy)),
        ("Action", f"{'BUY' if is_buy else 'SELL'} {lots:.2f} lots"),
        ("Entry", f"{price:.2f}"),
        ("Stop", f"{sl:.2f} ({_money(risk)})" if sl and risk is not None else (f"{sl:.2f}" if sl else "none")),
        ("Target", f"{tp:.2f} ({_money(reward)})" if tp and reward is not None else (f"{tp:.2f}" if tp else "none")),
        ("R:R", f"1 : {abs(reward / risk):.1f}" if risk and reward else None),
        ("P&L", "$0.00 (Open)"),
        ("Ticket", f"#{ticket}"),
    ]))


@_safe
def closed(ticket, deals, pl: float, strategy: str) -> None:
    in_d = [d for d in deals if d.entry == mt5.DEAL_ENTRY_IN]
    out_d = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
    first, last = (in_d[0] if in_d else deals[0]), out_d[-1]
    is_buy = first.type == mt5.DEAL_TYPE_BUY
    acct = mt5.account_info()
    title = "✅ TRADE CLOSED · WIN" if pl > 0 else "❌ TRADE CLOSED · LOSS" if pl < 0 else "➖ TRADE CLOSED · BREAKEVEN"
    alerts.send_html(alerts.table(title, [
        ("Time", _at(last.time)),
        ("Strategy", _name(strategy)),
        ("Action", f"{'BUY' if is_buy else 'SELL'} {first.volume:.2f} lots"),
        ("Entry", f"{first.price:.2f} @ {_at(first.time)[7:15]}"),
        ("Exit", f"{last.price:.2f} @ {_at(last.time)[7:15]}"),
        ("Held", _dur(last.time - first.time)),
        ("Result", _EXIT_REASON.get(getattr(last, "reason", -1), "Closed")),
        ("P&L", _money(pl)),
        ("Balance", f"${acct.balance:.2f}" if acct else None),
        ("Ticket", f"#{ticket}"),
    ]))


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
    rows, total = [("Time", alerts.ist_stamp())], 0.0
    for i, p in enumerate(positions, 1):
        pl = p.profit + p.swap
        total += pl
        side = "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL"
        rows += [(f"#{i}", f"{side} {p.volume:.2f} {_name(p.comment)}"),
                 ("  P&L", _money(pl)),
                 ("  Price", f"{p.price_open:.2f} -> {p.price_current:.2f}"),
                 ("  Open", _dur(now - p.time))]
    acct = mt5.account_info()
    rows += [("Floating", _money(total)), ("Equity", f"${acct.equity:.2f}" if acct else None)]
    alerts.send_html(alerts.table(f"📊 OPEN TRADES ({len(positions)})", rows))


STATUS_TIMES_IST = [t.strip() for t in os.environ.get("ULTRA_STATUS_TIMES_IST", "06:00,18:00").split(",") if t.strip()]
_status_sent: set = set()


@_safe
def maybe_status_report(now_ist: datetime, own_positions, todays_pl: float, floors: dict | None = None) -> None:
    """'Still alive' snapshot at fixed IST times on weekdays, so silence means something is wrong."""
    if now_ist.weekday() >= 5:
        return
    due = [t for t in STATUS_TIMES_IST if now_ist.strftime("%H:%M") >= t]
    if not due:
        return
    key = f"{now_ist:%Y-%m-%d} {due[-1]}"
    if key in _status_sent:
        return
    if not _status_sent:  # first call after a (re)start: don't replay slots already passed today
        _status_sent.update(f"{now_ist:%Y-%m-%d} {t}" for t in due)
        return
    _status_sent.add(key)
    acct = mt5.account_info()
    floating = sum(p.profit + p.swap for p in own_positions) if own_positions else 0.0
    rows = [("Time", alerts.ist_stamp()),
            ("Bot", "Running"),
            ("Account", f"{acct.login} {acct.server}" if acct else "MT5 not connected"),
            ("Balance", f"${acct.balance:.2f}" if acct else None),
            ("Equity", f"${acct.equity:.2f}" if acct else None),
            ("Open", f"{len(own_positions or [])} trade(s), {_money(floating)}"),
            ("Today", _money(todays_pl))]
    if floors and acct:
        rows += [("DD floor", f"${floors['trailing_floor']:.2f} ({_money(acct.equity - floors['trailing_floor'])} room)"),
                 ("Day floor", f"${floors['daily_floor']:.2f}")]
    alerts.send_html(alerts.table("🟦 STATUS", rows))


@_safe
def news_pause(reason: str) -> None:
    key = re.sub(r"\(.*?\)|\d+ ?min", "", reason).strip()
    if key in _news_alerted:
        return
    _news_alerted.add(key)
    alerts.send_html(alerts.table("📰 NEWS PAUSE", [
        ("Time", alerts.ist_stamp()),
        ("Event", reason),
        ("Status", "No new entries"),
        ("Open", "SL/TP stay in place"),
    ]))
