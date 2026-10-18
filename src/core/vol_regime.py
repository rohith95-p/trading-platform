"""vol_regime.py -- deterministic, fail-closed volatility-regime risk governor (2026-10-18).

A RISK OVERLAY, not an edge. It maps (H1 ATR percentile, event proximity) to {allowed, risk multiplier}.
Frozen by research/registry/PREREG_VolGovernor_2026-10-18.md. Not wired into the live bot.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

WINDOW = 1440          # previous H1 ATR values used for the percentile (about 60 trading days)
MIN_HISTORY = 720      # fewer -> UNKNOWN (fail closed)
LOW_PCT, HIGH_PCT = 25.0, 85.0
EVENT_BEFORE_S, EVENT_AFTER_S = 30 * 60, 60 * 60


@dataclass(frozen=True)
class Regime:
    name: str          # LOW | NORMAL | HIGH | EVENT | UNKNOWN
    allowed: bool
    risk_multiplier: float


def atr_percentile(history: Sequence[float], value: Optional[float]) -> Optional[float]:
    """Percent of the previous WINDOW values strictly below `value` (current value excluded). None if not enough data."""
    if value is None or value != value:
        return None
    h = [x for x in history[-WINDOW:] if x == x]
    if len(h) < MIN_HISTORY:
        return None
    return 100.0 * sum(1 for x in h if x < value) / len(h)


def near_event(ts: int, event_times: Sequence[int]) -> bool:
    return any(e - EVENT_BEFORE_S <= ts <= e + EVENT_AFTER_S for e in event_times)


def classify(atr_pct: Optional[float], event: bool) -> Regime:
    if event:
        return Regime("EVENT", False, 0.0)
    if atr_pct is None:
        return Regime("UNKNOWN", False, 0.0)          # missing input -> fail closed
    if atr_pct > HIGH_PCT:
        return Regime("HIGH", True, 0.5)
    if atr_pct < LOW_PCT:
        return Regime("LOW", True, 0.5)
    return Regime("NORMAL", True, 1.0)
