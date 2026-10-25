"""
No-Lookahead Bias Tests -- PRODUCTION_READINESS_PLAN.md Phase 1.5.

Every test here verifies that strategies and indicators only use data that
would have been available at the time the signal fires. A strategy at bar N
must only see bars 0..N-1 (or equivalently, m15_rates[-2] for the last CLOSED
bar, never m15_rates[-1] which is the still-forming candle).

These are static / unit tests -- they run without MT5.
"""
import numpy as np
import pytest
from datetime import datetime, timezone, timedelta


IST = timezone(timedelta(hours=5, minutes=30))


# ---------------------------------------------------------------------------
# Helpers: synthetic bar arrays
# ---------------------------------------------------------------------------

def _make_rates(n: int, base_close: float = 2000.0) -> np.ndarray:
    """Create a minimal structured rates array with n bars."""
    dtype = np.dtype([
        ("time", "i8"),
        ("open", "f8"),
        ("high", "f8"),
        ("low", "f8"),
        ("close", "f8"),
        ("tick_volume", "f8"),
        ("spread", "i4"),
        ("real_volume", "f8"),
    ])
    arr = np.zeros(n, dtype=dtype)
    start_ts = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    for i in range(n):
        arr["time"][i] = start_ts + i * 900  # M15 = 900s
        arr["open"][i] = base_close + i * 0.1
        arr["close"][i] = base_close + i * 0.1 + 0.05
        arr["high"][i] = base_close + i * 0.1 + 0.2
        arr["low"][i] = base_close + i * 0.1 - 0.1
        arr["tick_volume"][i] = 100
    return arr


# ---------------------------------------------------------------------------
# D1 gate lookahead check (from main_loop.py)
# ---------------------------------------------------------------------------

class TestD1GateNoLookahead:
    """The D1 EMA20 bias gate must read the CLOSED daily bar, not the forming one."""

    def test_d1_gate_reads_closed_bar(self):
        """
        The D1 gate must compare d1_closes[-2] vs d1_ema20[-2], not [-1].

        Index [-1] is the still-forming D1 candle -- it will be overwritten as
        gold moves intraday. Reading it would let the daily bias flip every
        minute instead of only on a confirmed daily close.

        Verified in main_loop.py: uses d1_closes[-2] and d1_ema20[-2].
        """
        from src.core import main_loop

        # Inspect the source to find the index used in the D1 bias block.
        import inspect
        src = inspect.getsource(main_loop)

        # The gate should use [-2] to read the closed bar
        assert "d1_closes[-2]" in src, (
            "D1 gate must read d1_closes[-2] (closed bar), not d1_closes[-1] "
            "(still-forming). See main_loop.py D1 gate block."
        )
        assert "d1_ema20[-2]" in src, (
            "D1 gate must read d1_ema20[-2] (closed bar), not d1_ema20[-1]."
        )

        # It must NOT read [-1] for the bias comparison
        # (it may appear in other contexts, but not inside the d1_bias assignment)
        # We check the specific pattern
        assert "d1_closes[-2] > d1_ema20[-2]" in src, (
            "D1 bias comparison must use closed bars: d1_closes[-2] > d1_ema20[-2]"
        )


# ---------------------------------------------------------------------------
# Signal candle dedup check
# ---------------------------------------------------------------------------

class TestSignalCandleDedup:
    """Strategies must deduplicate on the closed-bar timestamp, not the live candle."""

    def test_signal_candle_key_is_closed_bar(self):
        """
        The dedup key must be m15_rates[-2]['time'] (last CLOSED bar).

        If it were m15_rates[-1]['time'] (forming bar), the key would change
        every 15 minutes even with no new signal, potentially re-firing on
        what is actually the same candle after a restart.
        """
        from src.core import main_loop
        import inspect
        src = inspect.getsource(main_loop)

        # signal_candle should be set to [-2]["time"]
        assert 'signal_candle = int(m15_rates[-2]["time"])' in src, (
            "signal_candle dedup key must use m15_rates[-2] (last CLOSED bar). "
            "Using [-1] would key on the forming candle and allow re-fires."
        )


# ---------------------------------------------------------------------------
# ATR calculation lookahead
# ---------------------------------------------------------------------------

class TestATRNoLookahead:
    """ATR at bar N must only use bars 0..N."""

    def test_atr_does_not_use_future_bars(self):
        """RiskManager.calc_atr must not look ahead."""
        from src.core.risk_manager import RiskManager

        rates = _make_rates(50)

        # Compute ATR on the first 30 bars
        atr_30 = RiskManager.calc_atr(rates[:30])
        # Compute ATR on the first 31 bars
        atr_31 = RiskManager.calc_atr(rates[:31])

        # The last value of atr_30 must equal atr_31[-2] (same bar, same history)
        # (last valid of 30-bar array is at index 29; same bar in 31-bar array is at index 29)
        last_valid_30 = atr_30[~np.isnan(atr_30)][-1] if any(~np.isnan(atr_30)) else None
        val_in_31 = atr_31[29]  # index 29 in the 31-bar array

        assert last_valid_30 is not None, "ATR should have valid values after 14 bars"
        assert abs(last_valid_30 - val_in_31) < 1e-9, (
            f"ATR at bar 29 changed when bar 30 was added: "
            f"was {last_valid_30:.6f}, became {val_in_31:.6f}. "
            "This indicates lookahead bias in the ATR calculation."
        )

    def test_atr_nan_before_warmup(self):
        """ATR must be NaN for the first period-1 bars (no data to compute from)."""
        from src.core.risk_manager import RiskManager

        rates = _make_rates(20)
        atr = RiskManager.calc_atr(rates, period=14)

        # First 13 bars (0..12) should be NaN -- can't compute ATR(14) yet
        for i in range(13):
            assert np.isnan(atr[i]), (
                f"ATR[{i}] should be NaN (not enough bars for ATR(14)), "
                f"but got {atr[i]:.4f}"
            )

        # Bar 13 onwards should have valid values
        assert not np.isnan(atr[13]), (
            f"ATR[13] should be valid (first bar with full 14-bar history), "
            f"but got NaN"
        )


# ---------------------------------------------------------------------------
# Strategy evaluate() reads closed bar
# ---------------------------------------------------------------------------

class TestStrategyEvaluateClosedBar:
    """_SessionSpecialist.evaluate() must read m15_rates[-2], not [-1]."""

    def test_atlas_strategies_use_closed_bar(self):
        """Atlas portfolio strategies must use closed bars for signals (no lookahead)."""
        from src.strategies.portfolio_atlas import PORTFOLIO
        import inspect

        for cls in PORTFOLIO:
            src = inspect.getsource(cls.evaluate)
            assert "[-1]" not in src or "[-2]" in src, (
                f"{cls.__name__}.evaluate may use lookahead: check bar indexing."
            )


# ---------------------------------------------------------------------------
# EMA calculation
# ---------------------------------------------------------------------------

class TestEMANoLookahead:
    """main_loop's _calc_ema must be causal (no future bars)."""

    def test_ema_causal(self):
        """EMA at bar N must equal EMA computed with only bars 0..N."""
        from src.core.main_loop import _calc_ema

        closes = np.array([2000.0 + i for i in range(30)])

        ema_30 = _calc_ema(closes, 20)  # Full 30-bar array
        ema_29 = _calc_ema(closes[:29], 20)  # First 29 bars

        # Bar 28 (index) should have the same EMA in both arrays
        assert not np.isnan(ema_30[28]), "EMA[28] should be valid with 30-bar array"
        assert not np.isnan(ema_29[28]), "EMA[28] should be valid with 29-bar array"
        assert abs(ema_30[28] - ema_29[28]) < 1e-9, (
            f"EMA[28] changed when bar 29 was added: "
            f"was {ema_29[28]:.6f}, became {ema_30[28]:.6f}. Lookahead detected."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
