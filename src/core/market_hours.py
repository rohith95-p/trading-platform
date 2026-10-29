"""Broker-reality guards -- REAL_MONEY_READINESS.md IV.6.

Three things the live loop never handled, each of which has a real cost:

  * WEEKEND GAP. Gold gaps on the Sunday open. A position held over the weekend
    can gap straight through its stop -- the stop is a trigger price, not a
    guarantee, and the fill happens wherever the market reopens. The document's
    decision: flatten Friday ~21:00 IST, hold nothing over the weekend.
  * ROLLOVER. Spreads balloon around 00:00 server time. The FVG leg's ~$5.50
    stop is small enough that a rollover spread spike alone can take it out,
    so entries are skipped in a window around it.
  * MAINTENANCE / MARKET CLOSED. Exness has a short daily maintenance window.
    Without detection the loop retry-spams and fills the log with noise that
    hides real failures.

Times are IST (the project's convention) except the rollover window, which is
anchored to broker server time (UTC on Exness) because that is what the spread
actually keys off.
"""
from __future__ import annotations

import os
from datetime import datetime, time, timedelta, timezone
from typing import Optional, Tuple

IST = timezone(timedelta(hours=5, minutes=30))

# --- weekend ---------------------------------------------------------------
FRIDAY = 4
SATURDAY = 5
SUNDAY = 6
FRIDAY_FLATTEN_IST = time(22, 30)    # close everything from here on Friday
FRIDAY_NO_NEW_IST = time(21, 30)     # stop opening new positions an hour earlier

# --- rollover (server/UTC) -------------------------------------------------
ROLLOVER_HOUR_UTC = 0
ROLLOVER_SKIP_MINUTES = 10           # +/- around 00:00 UTC

# --- global trading window (owner decision 2026-09-06) ---------------------
# "We will trade 06:00 IST to 21:30 IST only."
# This is a hard outer boundary applied on top of each leg's own session, so a
# leg can never trade outside it even if its own window says otherwise.
TRADING_WINDOW_IST = (6.0, 21.5)
# Owner 2026-10-29: "trade 24/7". ULTRA_TRADE_24H=1 lifts this window; weekend,
# Friday cut-off and rollover checks below still apply.
ENFORCE_TRADING_WINDOW = os.getenv("ULTRA_TRADE_24H", "0") != "1"


def in_trading_window(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(IST)
    tv = now.hour + now.minute / 60.0
    lo, hi = TRADING_WINDOW_IST
    return lo <= tv < hi


def is_weekend(now: Optional[datetime] = None) -> bool:
    """Market closed: all of Saturday, all of Sunday, and Monday before ~03:30 IST reopen
    (which corresponds to Sunday 22:00 UTC / 17:00 EST global market open).
    """
    now = now or datetime.now(IST)
    if now.weekday() == SATURDAY:
        return True
    if now.weekday() == SUNDAY:
        return True
    if now.weekday() == 0:  # Monday morning before Sunday 22:00 UTC open
        return now.time() < time(3, 30)
    return False



def in_rollover_window(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(IST)
    utc = now.astimezone(timezone.utc)
    mins_from_rollover = abs((utc.hour - ROLLOVER_HOUR_UTC) * 60 + utc.minute)
    mins_from_rollover = min(mins_from_rollover, 1440 - mins_from_rollover)
    return mins_from_rollover <= ROLLOVER_SKIP_MINUTES


def should_flatten_for_weekend(now: Optional[datetime] = None) -> bool:
    """True once Friday's flatten time passes (or any time the market is shut)."""
    now = now or datetime.now(IST)
    if now.weekday() == FRIDAY and now.time() >= FRIDAY_FLATTEN_IST:
        return True
    return is_weekend(now)


def allow_new_entry(now: Optional[datetime] = None) -> Tuple[bool, str]:
    """The single check the loop calls before opening anything."""
    now = now or datetime.now(IST)
    if is_weekend(now):
        return False, "market closed (weekend)"
    if ENFORCE_TRADING_WINDOW and not in_trading_window(now):
        lo, hi = TRADING_WINDOW_IST
        return False, (f"outside the {lo:.2f}-{hi:.2f} IST trading window "
                       f"(owner rule 2026-09-06: no night trades)")
    if now.weekday() == FRIDAY and now.time() >= FRIDAY_NO_NEW_IST:
        return False, f"no new entries after {FRIDAY_NO_NEW_IST:%H:%M} IST Friday (weekend gap risk)"
    if in_rollover_window(now):
        return False, f"rollover window (+/-{ROLLOVER_SKIP_MINUTES}min around 00:00 UTC, spreads widen)"
    return True, ""


def market_closed_error(retcode: Optional[int], comment: str = "") -> bool:
    """Recognise broker 'market closed / trade disabled' so the loop can pause
    gracefully instead of retry-spamming. 10018 = market closed,
    10017 = trade disabled."""
    if retcode in (10018, 10017):
        return True
    c = (comment or "").lower()
    return "market closed" in c or "trade disabled" in c or "market is closed" in c
