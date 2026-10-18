"""news_filter.py -- REAL_MONEY_READINESS.md III.5.

Blocks new entries around scheduled tier-1 macro events that spike XAUUSD
spreads and cause unpredictable slippage. The FVG_NY leg has a ~$5 stop;
a rollover-hour spread spike alone can hit it. A CPI or NFP release can spike
spread to 50-100 points -- catastrophic for a position sized to 0.5×ATR.

This module is passive: it never raises. Failed file reads or network errors
return allow_entry=True (safer than silently blocking during a data gap).

Configuration
─────────────
Events are stored in two places:
  1. The hardcoded TIER1_EVENTS dict below -- a Q4-2026 baseline.
     Format: { "YYYY-MM-DD": [{"name": str, "utc_time": "HH:MM"}, ...] }
  2. An optional override JSON at NEWS_CALENDAR_PATH -- operator updates
     this monthly. Keys/values identical to TIER1_EVENTS.
     Override entries are MERGED with (and take precedence over) hardcoded ones.

The blackout window is ±NEWS_BLACKOUT_MINUTES around each event's UTC time.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

# --- config ------------------------------------------------------------------
NEWS_BLACKOUT_MINUTES = 15      # block ±this many minutes around each event
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NEWS_CALENDAR_PATH = os.path.join(_ROOT, "docs", "plans", "news_calendar.json")
ENABLE_NEWS_FILTER = True       # set False to bypass entirely (e.g. in tests)

# ---------------------------------------------------------------------------
# Hardcoded Q4-2026 tier-1 events (UTC times)
# Refreshed manually each quarter -- see operator instructions at end of file.
# Source: https://www.forexfactory.com / https://www.investing.com/economic-calendar/
# ---------------------------------------------------------------------------
TIER1_EVENTS: Dict[str, List[dict]] = {
    # ---- September 2026 ----
    "2026-09-16": [{"name": "FOMC Rate Decision", "utc_time": "18:00"},
                   {"name": "FOMC Press Conference", "utc_time": "18:30"}],
    "2026-09-25": [{"name": "US PCE Price Index", "utc_time": "12:30"}],

    # ---- October 2026 ----
    "2026-10-02": [{"name": "US Non-Farm Payrolls", "utc_time": "12:30"},
                   {"name": "US Unemployment Rate", "utc_time": "12:30"}],
    "2026-10-14": [{"name": "US CPI m/m", "utc_time": "12:30"},
                   {"name": "US Core CPI m/m", "utc_time": "12:30"}],
    "2026-10-15": [{"name": "US Retail Sales", "utc_time": "12:30"}],
    # Corrected 2026-10-19 from official sources: Fed FOMC calendar (federalreserve.gov), BLS schedules (cpi, empsit),
    # BEA release schedule (GDP and Personal Income & Outlays = PCE). 08:30 ET = 12:30 UTC until 1 Nov (EDT), 13:30 UTC after (EST).
    "2026-10-28": [{"name": "FOMC Rate Decision", "utc_time": "18:00"},
                   {"name": "FOMC Press Conference", "utc_time": "18:30"}],
    "2026-10-29": [{"name": "US GDP q/q Advance", "utc_time": "12:30"},
                   {"name": "US PCE Price Index", "utc_time": "12:30"}],

    # ---- November 2026 ----
    "2026-11-06": [{"name": "US Non-Farm Payrolls", "utc_time": "13:30"},
                   {"name": "US Unemployment Rate", "utc_time": "13:30"}],
    "2026-11-10": [{"name": "US CPI m/m", "utc_time": "13:30"},
                   {"name": "US Core CPI m/m", "utc_time": "13:30"}],
    "2026-11-25": [{"name": "US GDP q/q Second", "utc_time": "13:30"},
                   {"name": "US PCE Price Index", "utc_time": "13:30"}],

    # ---- December 2026 ----
    "2026-12-04": [{"name": "US Non-Farm Payrolls", "utc_time": "13:30"},
                   {"name": "US Unemployment Rate", "utc_time": "13:30"}],
    "2026-12-09": [{"name": "FOMC Rate Decision", "utc_time": "19:00"},
                   {"name": "FOMC Press Conference", "utc_time": "19:30"}],
    "2026-12-10": [{"name": "US CPI m/m", "utc_time": "13:30"},
                   {"name": "US Core CPI m/m", "utc_time": "13:30"}],
    "2026-12-23": [{"name": "US GDP q/q Third", "utc_time": "13:30"},
                   {"name": "US PCE Price Index", "utc_time": "13:30"}],
}


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

_calendar_cache: Optional[Dict[str, List[dict]]] = None


def _load_calendar() -> Dict[str, List[dict]]:
    """Merge hardcoded events with any operator-supplied override JSON."""
    global _calendar_cache
    if _calendar_cache is not None:
        return _calendar_cache

    merged: Dict[str, List[dict]] = {k: list(v) for k, v in TIER1_EVENTS.items()}

    try:
        if os.path.exists(NEWS_CALENDAR_PATH):
            with open(NEWS_CALENDAR_PATH, "r", encoding="utf-8") as fh:
                overrides: Dict[str, List[dict]] = json.load(fh)
            for date_str, events in overrides.items():
                existing = {e["utc_time"] for e in merged.get(date_str, [])}
                merged.setdefault(date_str, [])
                for ev in events:
                    if ev.get("utc_time") not in existing:
                        merged[date_str].append(ev)
            log.info(f"news_filter: loaded {len(overrides)} override day(s) from {NEWS_CALENDAR_PATH}")
    except (OSError, json.JSONDecodeError, KeyError) as e:
        log.warning(f"news_filter: override load failed ({e}) -- using hardcoded calendar only")

    _calendar_cache = merged
    return _calendar_cache


def invalidate_cache() -> None:
    """Force reload on next call -- call this at bot startup."""
    global _calendar_cache
    _calendar_cache = None


def is_near_news_event(now: Optional[datetime] = None) -> Tuple[bool, str]:
    """Returns (blocked, reason) for the current moment.

    Checks if NOW is within NEWS_BLACKOUT_MINUTES of any tier-1 event.
    If ENABLE_NEWS_FILTER is False, always returns (False, '').
    On any error, returns (False, '') -- the failure mode is permissive.
    """
    if not ENABLE_NEWS_FILTER:
        return False, ""

    try:
        now = (now or datetime.now(IST)).astimezone(UTC)
        calendar = _load_calendar()
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        # Check yesterday, today, and tomorrow (events near midnight span adjacent days)
        for date_str in (yesterday_str, today_str, tomorrow_str):
            for event in calendar.get(date_str, []):
                try:
                    h, m = map(int, event["utc_time"].split(":"))
                    event_utc = datetime.strptime(date_str, "%Y-%m-%d").replace(
                        hour=h, minute=m, second=0, microsecond=0, tzinfo=UTC
                    )

                    delta_min = abs((now - event_utc).total_seconds()) / 60
                    if delta_min <= NEWS_BLACKOUT_MINUTES:
                        direction = "before" if now < event_utc else "after"
                        return (
                            True,
                            f"news blackout: {event['name']} at {event['utc_time']} UTC "
                            f"({delta_min:.0f} min {direction}, ±{NEWS_BLACKOUT_MINUTES} min window)"
                        )
                except (KeyError, ValueError):
                    continue  # malformed event entry -- skip

    except Exception as e:
        log.warning(f"news_filter: check failed ({e}) -- not blocking")

    return False, ""


def upcoming_events(hours_ahead: float = 4.0,
                    now: Optional[datetime] = None) -> List[dict]:
    """Return events occurring within `hours_ahead` hours from now.

    Useful for daily plan generation or logging the session context.
    Returns list of dicts with keys: name, utc_time, minutes_away, date.
    """
    result: List[dict] = []
    try:
        now_utc = (now or datetime.now(IST)).astimezone(UTC)
        calendar = _load_calendar()
        cutoff = now_utc + timedelta(hours=hours_ahead)

        for date_str, events in calendar.items():
            for event in events:
                try:
                    h, m = map(int, event["utc_time"].split(":"))
                    base = datetime.strptime(date_str, "%Y-%m-%d").replace(
                        hour=h, minute=m, tzinfo=UTC)
                    if now_utc <= base <= cutoff:
                        result.append({
                            "name": event["name"],
                            "utc_time": event["utc_time"],
                            "date": date_str,
                            "minutes_away": int((base - now_utc).total_seconds() / 60),
                        })
                except (KeyError, ValueError):
                    continue
    except Exception as e:
        log.warning(f"news_filter.upcoming_events failed: {e}")

    return sorted(result, key=lambda x: x["minutes_away"])


# ---------------------------------------------------------------------------
# Operator instructions (kept here so they travel with the code)
# ---------------------------------------------------------------------------
# Monthly update ritual (1st of each month, ~5 minutes):
#
#   1. Open https://www.forexfactory.com (or investing.com economic calendar)
#   2. Filter: Currencies=USD, Impact=Red, next 4 weeks
#   3. Add new events to docs/plans/news_calendar.json in the format:
#        { "YYYY-MM-DD": [{"name": "Event Name", "utc_time": "HH:MM"}] }
#      Use UTC times only (the filter converts internally).
#   4. Restart main_loop (it calls invalidate_cache() on startup).
#
# Key recurring events to never miss:
#   - US Non-Farm Payrolls (first Friday of each month, 12:30 or 13:30 UTC)
#   - US CPI (mid-month, usually 12:30 or 13:30 UTC)
#   - FOMC Rate Decision (8 times/year, 19:00 UTC + presser 19:30 UTC)
#   - US PCE Price Index (last Friday of month, 12:30 UTC)
#   - US GDP Advance/Preliminary/Final releases
#   - Jackson Hole (late August), Fed Chair speeches
# ---------------------------------------------------------------------------
