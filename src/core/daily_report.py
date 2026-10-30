"""daily_report.py -- Generates and sends a daily P&L summary."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from src.core import alerts, risk_rules, news_filter, trade_log

log = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))


def _compute_rolling_pf(log_dir: str, lookback_days: int = 60, n_trades: int = 30) -> float | None:
    """Compute rolling N-trade profit factor from the JSONL trade logs.

    Scans the last `lookback_days` of daily log files and returns the PF for
    the most recent `n_trades` closed trades, or None if there are fewer.
    """
    now_ist = datetime.now(IST)
    pls = []

    for d in range(lookback_days):
        date_str = (now_ist - timedelta(days=d)).strftime("%Y-%m-%d")
        path = os.path.join(log_dir, f"{date_str}.jsonl")
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get("kind") == "closed":
                            pls.append((rec.get("ts", 0), rec.get("profit", 0.0)))
                    except (json.JSONDecodeError, KeyError):
                        pass
        except OSError:
            pass

    if len(pls) < n_trades:
        return None

    pls.sort(key=lambda x: x[0])
    recent = [p for _, p in pls[-n_trades:]]

    wins = sum(p for p in recent if p > 0)
    losses = sum(abs(p) for p in recent if p < 0)
    if losses == 0:
        return float("inf")
    return round(wins / losses, 3)


def generate_report(date_str: str) -> "alerts.Alert":
    """Generate daily P&L report string for the given date (YYYY-MM-DD).

    Includes:
    - Day P&L, trades, win rate
    - Risk state (consecutive losses, DD today)
    - VI.3 rolling 30-trade PF with tripwire status
    - Circuit breaker status
    - Next-24h news events
    """
    log_dir = trade_log.LOG_DIR
    log_path = os.path.join(log_dir, f"{date_str}.jsonl")
    trades = []

    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("kind") == "closed":
                        trades.append(rec)
                except json.JSONDecodeError:
                    pass

    n_trades = len(trades)
    wins = [t for t in trades if t.get("profit", 0) > 0]
    losses = [t for t in trades if t.get("profit", 0) <= 0]
    win_rate = (len(wins) / n_trades * 100) if n_trades > 0 else 0
    day_pl = sum(t.get("profit", 0) for t in trades)

    state = risk_rules.load_state()
    # If state is missing a start balance, approximate with current peak equity
    ref_balance = state.day_start_balance if state.day_start_balance > 0 else state.peak_equity
    balance = ref_balance + day_pl

    # VI.3: Rolling 30-trade profit factor
    rolling_pf = _compute_rolling_pf(log_dir)

    # Check for tomorrow's news (next 24 hours from now)
    now_ist = datetime.now(IST)
    upcoming = news_filter.upcoming_events(hours_ahead=24, now=now_ist)

    try:   # the broker's balance, when the terminal is reachable; else the risk-state estimate
        import MetaTrader5 as _mt5
        _acct = _mt5.account_info()
        if _acct is not None:
            balance = float(_acct.balance)
    except Exception:
        pass

    day = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a %d %b")
    sign = "+" if day_pl >= 0 else "−"
    lines = [f"Trades {n_trades} · {len(wins)} won, {len(losses)} lost · net {sign}${abs(day_pl):,.2f}"
             if n_trades else "No trades",
             f"Balance ${balance:,.2f}"]

    if state.hard_halt_reason:
        lines.append(f"⛔ Halted: {state.hard_halt_reason}")
    elif state.day_stopped_date == now_ist.date().isoformat():
        lines.append("⛔ Stopped for today (loss streak)")
    elif state.pause_until_ts > now_ist.timestamp():
        lines.append(f"⏸ Paused {(state.pause_until_ts - now_ist.timestamp()) / 60:.0f} more min (loss streak)")

    if rolling_pf is not None and rolling_pf != float("inf"):
        lines.append(f"Last 30 trades: profit factor {rolling_pf:.2f}")

    if upcoming:
        ev = upcoming[0]
        lines.append(f"Next news: {ev['name']} at {ev['utc_time']} UTC")

    return alerts.Alert(f"Day summary · {day}", tuple(lines), alerts.INFO, icon="📅")


def send_daily_report(force: bool = False) -> None:
    """Send the daily report. If force is True, sends for today, else for yesterday."""
    now = datetime.now(IST)
    if force:
        date_str = now.strftime("%Y-%m-%d")
    else:
        date_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    # Check if there was activity before sending, unless forced
    log_path = os.path.join(trade_log.LOG_DIR, f"{date_str}.jsonl")
    if not force and not os.path.exists(log_path):
        log.info(f"daily_report: No activity found for {date_str}, skipping report.")
        return

    alerts.notify(generate_report(date_str))
