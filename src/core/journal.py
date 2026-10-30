"""End-of-day trade journal (owner 2026-10-30: "auto-register trades at 23:59").

At 23:59 IST main_loop reads the day's closed trades straight from MT5 history, appends any not yet recorded to
logs/trade_journal.csv (one row per trade, deduplicated by ticket), and sends a one-line-per-item day summary.
Never raises into the trading loop.
"""
from __future__ import annotations

import csv
import logging
import os
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, List, Optional

from src.core import alerts, scope

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
JOURNAL_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "logs", "trade_journal.csv")
RUN_AT_IST = time(23, 59)
_REASON = {0: "manual", 1: "manual", 2: "manual", 3: "bot", 4: "stop loss", 5: "take profit", 6: "stop-out"}


@dataclass(frozen=True)
class ClosedTrade:
    ticket: int
    strategy: str
    side: str
    lots: float
    entry_time_ist: str
    entry_price: float
    exit_time_ist: str
    exit_price: float
    stop_loss: float
    target: float
    exit_reason: str
    profit: float
    commission: float
    swap: float
    net: float


def _ist(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(IST).strftime("%Y-%m-%d %H:%M:%S")


def closed_trades(mt5, since_ts: int, until_ts: int, symbol: str = "XAUUSDm") -> List[ClosedTrade]:
    """Own-magic positions whose final exit falls in [since_ts, until_ts). Epoch seconds (aware datetimes
    make the MT5 API return nothing)."""
    own = scope.load_own_magics()
    deals = [d for d in (mt5.history_deals_get(since_ts - 7 * 86400, until_ts + 3600) or []) if d.symbol == symbol]
    by_pos = {}
    for d in deals:
        by_pos.setdefault(d.position_id, []).append(d)
    out = []
    for pid, ds in by_pos.items():
        ds.sort(key=lambda d: d.time)
        ins = [d for d in ds if d.entry == 0]
        outs = [d for d in ds if d.entry in (1, 2)]
        if not ins or not outs or ins[0].magic not in own or not (since_ts <= outs[-1].time < until_ts):
            continue
        a, b = ins[0], outs[-1]
        orders = mt5.history_orders_get(position=pid) or []
        profit = sum(d.profit for d in ds)
        comm = sum(d.commission for d in ds)
        swap = sum(d.swap for d in ds)
        out.append(ClosedTrade(
            ticket=int(pid), strategy=a.comment or str(a.magic), side="BUY" if a.type == 0 else "SELL",
            lots=float(a.volume), entry_time_ist=_ist(a.time), entry_price=float(a.price),
            exit_time_ist=_ist(b.time), exit_price=float(b.price),
            stop_loss=float(next((o.sl for o in orders if o.sl), 0.0)),
            target=float(next((o.tp for o in orders if o.tp), 0.0)),
            exit_reason=_REASON.get(b.reason, str(b.reason)),
            profit=round(profit, 2), commission=round(comm, 2), swap=round(swap, 2),
            net=round(profit + comm + swap, 2)))
    return sorted(out, key=lambda t: t.entry_time_ist)


def append(trades: Iterable[ClosedTrade], path: Optional[str] = None) -> int:
    """Append trades not already in the CSV (by ticket). Returns how many were added."""
    path = path or JOURNAL_FILE
    seen = set()
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            seen = {row["ticket"] for row in csv.DictReader(f)}
    new = [t for t in trades if str(t.ticket) not in seen]
    if not new:
        return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    first = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[x.name for x in fields(ClosedTrade)])
        if first:
            w.writeheader()
        for t in new:
            w.writerow(asdict(t))
    return len(new)


def day_summary(day: date, trades: List[ClosedTrade], balance: Optional[float]) -> alerts.Alert:
    from src.core.trade_alerts import _money, _name
    lines = []
    for i, t in enumerate(trades, 1):
        lines += [f"{i}. {_name(t.strategy)}: {t.side} {t.lots:.2f}",
                  f"   Entry price: {t.entry_price:.2f} ({t.entry_time_ist[11:16]})",
                  f"   Exit price: {t.exit_price:.2f} ({t.exit_time_ist[11:16]}, {t.exit_reason})",
                  f"   Net: {_money(t.net)}"]
    net = sum(t.net for t in trades)
    wins = sum(1 for t in trades if t.net > 0)
    lines += [f"Trades: {len(trades)} ({wins} won, {len(trades) - wins} lost)" if trades else "Trades: none",
              f"Day net: {_money(net)}"]
    if balance is not None:
        lines.append(f"Balance: ${balance:,.2f}")
    lines.append("Saved to logs/trade_journal.csv")
    return alerts.Alert(f"Day summary · {day:%a %d %b}", tuple(lines), alerts.INFO, icon="📅")


_done: set = set()


def maybe_run(mt5, now_ist: datetime) -> None:
    """Once per IST day at/after 23:59: record the day's closed trades and send the summary."""
    if now_ist.time() < RUN_AT_IST or now_ist.date() in _done:
        return
    _done.add(now_ist.date())
    try:
        day = now_ist.date()
        start = int(datetime.combine(day, time(0), IST).timestamp())
        trades = closed_trades(mt5, start, start + 86400)
        # also sweep the last 3 days so a trade that closed after yesterday's 23:59 run is still recorded
        added = append(closed_trades(mt5, start - 3 * 86400, start + 86400))
        log.info(f"journal: {len(trades)} trade(s) closed today, {added} new row(s) written to {JOURNAL_FILE}")
        if trades or day.weekday() < 5:
            acct = mt5.account_info()
            alerts.notify(day_summary(day, trades, float(acct.balance) if acct else None))
    except Exception as e:
        log.warning(f"journal: end-of-day run failed: {e}")
