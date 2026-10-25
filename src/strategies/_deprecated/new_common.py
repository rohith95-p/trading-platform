"""Shared causal helpers for the research-only `new_*` strategies (not live).

Everything here works on the CLOSED-bar view `closed(rates) == rates[:-1]`, so
the still-forming bar (index -1) can never influence a signal.
"""
from __future__ import annotations

import numpy as np

from src.strategies.base_strategy import BaseStrategy

IST_OFFSET = 19800          # UTC+5:30 in seconds
M15 = 900


def closed(rates: np.ndarray) -> np.ndarray:
    """Closed bars only: drops the forming bar [-1]."""
    return rates[:-1]


def ist_sec(t) -> np.ndarray:
    """Seconds since IST midnight for epoch-second timestamps."""
    return ((np.asarray(t, dtype="int64") % 86400) + IST_OFFSET) % 86400


def ist_day(t) -> np.ndarray:
    """IST calendar-day key."""
    return (np.asarray(t, dtype="int64") + IST_OFFSET) // 86400


def utc_day(t) -> np.ndarray:
    """UTC calendar-day key."""
    return np.asarray(t, dtype="int64") // 86400


def atr14(c: np.ndarray) -> np.ndarray:
    return BaseStrategy.atr(c["high"], c["low"], c["close"], 14)


def ema(values: np.ndarray, period: int) -> np.ndarray:
    return BaseStrategy.ema(values, period)
