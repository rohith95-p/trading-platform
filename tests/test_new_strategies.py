"""Smoke / causality tests for the active Atlas portfolio strategies."""
import os

import numpy as np
import pytest

from src.strategies.base_strategy import Signal
from src.strategies.momentum_strategies import DonchianTrendV6
from src.strategies.asian_range_filtered import AsianRangeFilteredV6
from src.strategies.asian_breakout import AsianBreakoutV6

DATA = os.path.join(os.path.dirname(__file__), "..", "research", "data", "XAUUSDm_M15.npy")
DTYPE = [("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"),
         ("close", "<f8"), ("tick_volume", "<u8"), ("spread", "<i4"), ("real_volume", "<u8")]
T0 = 1704067200  # Monday 2024-01-01 00:00 UTC
STRATS = [DonchianTrendV6, AsianRangeFilteredV6, AsianBreakoutV6]


def _make(n, drift=0.0, sigma=0.3, seed=1, t0=T0):
    rng = np.random.default_rng(seed)
    close = 2000.0 + np.cumsum(drift + sigma * rng.standard_normal(n))
    r = np.zeros(n, dtype=DTYPE)
    r["time"] = t0 + 900 * np.arange(n)
    r["close"] = close
    r["open"] = np.concatenate([[2000.0], close[:-1]])
    r["high"] = np.maximum(r["open"], r["close"]) + 0.1
    r["low"] = np.minimum(r["open"], r["close"]) - 0.1
    r["tick_volume"] = 100
    return r


def _key(sig):
    return None if sig is None else sig.is_buy


@pytest.fixture(scope="module")
def real():
    if not os.path.exists(DATA):
        pytest.skip("real M15 data not available")
    return np.load(DATA)


@pytest.mark.parametrize("cls", STRATS)
def test_attributes_present(cls):
    s = cls()
    assert s.magic in (7310, 7311, 7320)
    assert hasattr(s, 'sl_atr_mult') and hasattr(s, 'tp_atr_mult')
    assert s.sl_atr_mult > 0 and s.tp_atr_mult > 0
    assert s.name and isinstance(s.name, str)


@pytest.mark.parametrize("cls", STRATS)
def test_synthetic_never_raises(cls):
    s = cls()
    for seed, drift in ((1, 0.0), (2, 0.05), (3, -0.05)):
        r = _make(1500, drift=drift, seed=seed)
        for end in range(300, len(r), 7):
            out = s.evaluate(r[max(0, end - 600):end])
            assert out is None or isinstance(out, Signal)


def _alter_forming(w):
    a = w.copy()
    a["open"][-1] += 37.0
    a["high"][-1] += 91.0
    a["low"][-1] -= 83.0
    a["close"][-1] += 55.0
    return a


@pytest.mark.parametrize("cls", [AsianRangeFilteredV6, AsianBreakoutV6])
def test_real_sliding_and_lookahead(cls, real):
    s = cls()
    ends = range(len(real) - 12000, len(real), 4)
    n_sig = 0
    for e in ends:
        w = real[e - 600:e]
        out = s.evaluate(w)
        assert out is None or isinstance(out, Signal)
        alt = s.evaluate(_alter_forming(w))
        assert _key(out) == _key(alt), f"lookahead at end={e}"
        if out is not None:
            n_sig += 1
            assert out.magic == s.magic and out.strategy_name == s.name
            assert out.direction in (0, 1)
    assert n_sig >= 1


@pytest.mark.skipif(
    not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "research", "data", "XAUUSDm_D1.npy")),
    reason="DonchianTrend needs D1 data for evaluate()"
)
def test_donchian_no_crash_on_real(real):
    s = DonchianTrendV6()
    for e in range(600, min(len(real), 1200), 4):
        out = s.evaluate(real[e - 600:e])
        assert out is None or isinstance(out, Signal)


def test_portfolio_magics_unique():
    magics = [cls().magic for cls in STRATS]
    assert len(magics) == len(set(magics))


def test_portfolio_names_unique():
    names = [cls().name for cls in STRATS]
    assert len(names) == len(set(names))
