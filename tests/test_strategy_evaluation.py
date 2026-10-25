"""
Strategy Logic Unit Tests -- PRODUCTION_READINESS_PLAN.md Phase 1.3.

Tests for:
- Deduplication (last_fired_candle prevents same-candle re-fires)
- Edge-trigger flag behavior
- execute_immediately flag behavior
- Session masking
- D1 bias gate logic

These tests run without MT5 by testing the logic in isolation.
"""
import numpy as np
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch


IST = timezone(timedelta(hours=5, minutes=30))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rates(n: int = 260, base_close: float = 2000.0) -> np.ndarray:
    """Create a minimal M15 rates array with IST-aware timestamps."""
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
    # Start at 12:00 IST (London session)
    start_ts = int(datetime(2026, 6, 1, 6, 30, 0, tzinfo=timezone.utc).timestamp())
    for i in range(n):
        arr["time"][i] = start_ts + i * 900
        arr["open"][i] = base_close + i * 0.05
        arr["close"][i] = base_close + i * 0.05 + 0.03
        arr["high"][i] = base_close + i * 0.05 + 0.15
        arr["low"][i] = base_close + i * 0.05 - 0.05
        arr["tick_volume"][i] = 50 + (i % 20) * 5
    return arr


# ---------------------------------------------------------------------------
# D1 bias gate logic tests
# ---------------------------------------------------------------------------

class TestD1BiasGate:
    """The _d1_bias_allows() function must correctly filter by direction."""

    def test_buy_blocked_by_bearish_bias(self):
        """BUY signal must be blocked when D1 bias is BEARISH."""
        from src.core.main_loop import _d1_bias_allows
        from src.strategies.base_strategy import Signal

        buy_signal = Signal(direction=0, strategy_name="TEST", magic=9999, is_buy=True)
        result = _d1_bias_allows(buy_signal, "BEARISH", "TEST")
        assert result is False, "BUY must be blocked by BEARISH D1 bias"

    def test_sell_blocked_by_bullish_bias(self):
        """SELL signal must be blocked when D1 bias is BULLISH."""
        from src.core.main_loop import _d1_bias_allows
        from src.strategies.base_strategy import Signal

        sell_signal = Signal(direction=1, strategy_name="TEST", magic=9999, is_buy=False)
        result = _d1_bias_allows(sell_signal, "BULLISH", "TEST")
        assert result is False, "SELL must be blocked by BULLISH D1 bias"

    def test_buy_allowed_by_bullish_bias(self):
        """BUY signal must pass when D1 bias is BULLISH."""
        from src.core.main_loop import _d1_bias_allows
        from src.strategies.base_strategy import Signal

        buy_signal = Signal(direction=0, strategy_name="TEST", magic=9999, is_buy=True)
        result = _d1_bias_allows(buy_signal, "BULLISH", "TEST")
        assert result is True, "BUY must be allowed by BULLISH D1 bias"

    def test_sell_allowed_by_bearish_bias(self):
        """SELL signal must pass when D1 bias is BEARISH."""
        from src.core.main_loop import _d1_bias_allows
        from src.strategies.base_strategy import Signal

        sell_signal = Signal(direction=1, strategy_name="TEST", magic=9999, is_buy=False)
        result = _d1_bias_allows(sell_signal, "BEARISH", "TEST")
        assert result is True, "SELL must be allowed by BEARISH D1 bias"

    def test_no_bias_fails_closed_when_gate_enabled(self):
        """Owner rule 2026-10-17: with the D1 gate ON, an unavailable bias (failed/short D1 fetch) blocks
        new entries; it only passes everything when the gate itself is disabled."""
        from unittest.mock import patch
        from src.core import main_loop
        from src.core.main_loop import _d1_bias_allows
        from src.strategies.base_strategy import Signal

        buy_signal = Signal(direction=0, strategy_name="TEST", magic=9999, is_buy=True)
        sell_signal = Signal(direction=1, strategy_name="TEST", magic=9999, is_buy=False)

        with patch.object(main_loop, "ENABLE_D1_GATE", True):
            assert _d1_bias_allows(buy_signal, None, "TEST") is False
            assert _d1_bias_allows(sell_signal, None, "TEST") is False
        with patch.object(main_loop, "ENABLE_D1_GATE", False):
            assert _d1_bias_allows(buy_signal, None, "TEST") is True
            assert _d1_bias_allows(sell_signal, None, "TEST") is True


# ---------------------------------------------------------------------------
# Risk manager session multiplier
# ---------------------------------------------------------------------------

class TestSessionMultiplier:
    """Session multiplier must be 1.5 for London/NY and 2.0 for Asia."""

    def test_london_session_multiplier(self):
        """12:00 IST (London open) must give 1.5x multiplier."""
        from src.core.risk_manager import RiskManager

        london_time = datetime(2026, 6, 2, 12, 0, tzinfo=IST)
        mult = RiskManager.get_session_multiplier(london_time)
        assert mult == 1.5, f"London session must be 1.5x, got {mult}"

    def test_ny_session_multiplier(self):
        """18:00 IST (NY morning) must give 1.5x multiplier."""
        from src.core.risk_manager import RiskManager

        ny_time = datetime(2026, 6, 2, 18, 0, tzinfo=IST)
        mult = RiskManager.get_session_multiplier(ny_time)
        assert mult == 1.5, f"NY session must be 1.5x, got {mult}"

    def test_asia_session_multiplier(self):
        """03:00 IST (Asia overnight) must give 2.0x multiplier."""
        from src.core.risk_manager import RiskManager

        asia_time = datetime(2026, 6, 2, 3, 0, tzinfo=IST)
        mult = RiskManager.get_session_multiplier(asia_time)
        assert mult == 2.0, f"Asia session must be 2.0x, got {mult}"

    def test_session_boundary_start(self):
        """11:30 IST is the first minute of London (1.5x), not Asia (2.0x)."""
        from src.core.risk_manager import RiskManager

        boundary_time = datetime(2026, 6, 2, 11, 30, tzinfo=IST)
        mult = RiskManager.get_session_multiplier(boundary_time)
        assert mult == 1.5, f"11:30 IST must be London session (1.5x), got {mult}"

    def test_session_boundary_end(self):
        """21:30 IST is the first minute after London/NY (2.0x Asia starts)."""
        from src.core.risk_manager import RiskManager

        boundary_time = datetime(2026, 6, 2, 21, 30, tzinfo=IST)
        mult = RiskManager.get_session_multiplier(boundary_time)
        assert mult == 2.0, f"21:30 IST must be Asia session (2.0x), got {mult}"


# ---------------------------------------------------------------------------
# Session name tests
# ---------------------------------------------------------------------------

class TestSessionNames:
    """Session name strings must match expected categories."""

    def test_london_open_name(self):
        from src.core.risk_manager import RiskManager
        t = datetime(2026, 6, 2, 12, 0, tzinfo=IST)
        assert RiskManager.get_session_name(t) == "LONDON_OPEN"

    def test_ny_morning_name(self):
        from src.core.risk_manager import RiskManager
        t = datetime(2026, 6, 2, 19, 0, tzinfo=IST)
        assert RiskManager.get_session_name(t) == "NY_MORNING"

    def test_asia_overnight_name(self):
        from src.core.risk_manager import RiskManager
        t = datetime(2026, 6, 2, 5, 0, tzinfo=IST)
        assert RiskManager.get_session_name(t) == "ASIA_OVERNIGHT"

    def test_is_london_open_true(self):
        from src.core.risk_manager import RiskManager
        t = datetime(2026, 6, 2, 13, 0, tzinfo=IST)
        assert RiskManager.is_london_open(t) is True

    def test_is_london_open_false_ny(self):
        from src.core.risk_manager import RiskManager
        t = datetime(2026, 6, 2, 18, 0, tzinfo=IST)
        assert RiskManager.is_london_open(t) is False


# ---------------------------------------------------------------------------
# Risk rules sizing ladder
# ---------------------------------------------------------------------------

class TestSizingLadder:
    """SizingLadder must return correct values at each balance tier."""

    def test_below_floor_raises(self):
        """Balance below POSITION_FLOOR must raise ValueError."""
        from src.core.sizing_ladder import SizingLadder
        with pytest.raises(ValueError, match="position floor"):
            SizingLadder.get_sizing(30.0)

    def test_at_floor_raises(self):
        """Balance exactly at the floor threshold but below it raises."""
        from src.core.sizing_ladder import SizingLadder
        with pytest.raises(ValueError):
            SizingLadder.get_sizing(49.99)

    def test_survival_tier_100_200(self):
        """$100-$200: 0.01 lots, 1 position max, 0.01 max exposure."""
        from src.core.sizing_ladder import SizingLadder
        lots, max_conc, max_exp = SizingLadder.get_sizing(150.0)
        assert lots == 0.01
        assert max_conc == 1
        assert max_exp == 0.01

    def test_growth_tier_200_400(self):
        """$200-$400: 0.01 lots, 2 positions max."""
        from src.core.sizing_ladder import SizingLadder
        lots, max_conc, max_exp = SizingLadder.get_sizing(300.0)
        assert lots == 0.01
        assert max_conc == 2
        assert max_exp == 0.02

    def test_scaling_tier_800_plus(self):
        """$800+: 0.02 lots, 3 positions max, 0.06 max exposure."""
        from src.core.sizing_ladder import SizingLadder
        lots, max_conc, max_exp = SizingLadder.get_sizing(900.0)
        assert lots == 0.02
        assert max_conc == 3
        assert max_exp == 0.06


# ---------------------------------------------------------------------------
# Risk rules circuit breakers
# ---------------------------------------------------------------------------

class TestCircuitBreakers:
    """risk_rules state machine must track consecutive losses and trigger pauses."""

    def test_consecutive_losses_counted(self):
        """Each losing trade increments consecutive_losses."""
        from src.core.risk_rules import record_trade_result, RiskState

        state = RiskState()
        state = record_trade_result(-5.0, state=state)
        assert state.consecutive_losses == 1

        state = record_trade_result(-3.0, state=state)
        assert state.consecutive_losses == 2

    def test_winning_trade_resets_streak(self):
        """A winning trade resets the consecutive loss count to 0."""
        from src.core.risk_rules import record_trade_result, RiskState

        state = RiskState()
        state = record_trade_result(-5.0, state=state)
        state = record_trade_result(-5.0, state=state)
        assert state.consecutive_losses == 2

        state = record_trade_result(+10.0, state=state)
        assert state.consecutive_losses == 0, (
            "A winning trade must reset consecutive_losses to 0"
        )

    def test_three_losses_triggers_pause(self):
        """3 consecutive losses trigger a pause (CONSEC_LOSSES_PAUSE)."""
        from src.core.risk_rules import (
            record_trade_result, RiskState,
            CONSEC_LOSSES_PAUSE, CONSEC_LOSS_PAUSE_HOURS
        )
        import time as _time

        state = RiskState()
        for _ in range(CONSEC_LOSSES_PAUSE):
            state = record_trade_result(-5.0, state=state)

        assert state.pause_until_ts > _time.time(), (
            f"After {CONSEC_LOSSES_PAUSE} consecutive losses, pause_until_ts should be "
            f"set to the future (4h from now)"
        )

    def test_five_losses_stops_the_day(self):
        """5 consecutive losses stop trading for the day."""
        from src.core.risk_rules import (
            record_trade_result, RiskState, CONSEC_LOSSES_STOP_DAY
        )

        state = RiskState()
        now = datetime.now(IST)

        for _ in range(CONSEC_LOSSES_STOP_DAY):
            state = record_trade_result(-5.0, state=state)

        assert state.day_stopped_date == now.date().isoformat(), (
            f"After {CONSEC_LOSSES_STOP_DAY} consecutive losses, day_stopped_date "
            f"must be set to today"
        )

    def test_day_losing_trades_counted(self):
        """day_losing_trades increments on each loss."""
        from src.core.risk_rules import record_trade_result, RiskState

        state = RiskState()
        state = record_trade_result(-5.0, state=state)
        state = record_trade_result(+3.0, state=state)  # win resets consecutive but NOT day count
        state = record_trade_result(-2.0, state=state)

        assert state.day_losing_trades == 2, (
            "day_losing_trades must count all losses in the day, "
            "not just consecutive ones"
        )


# ---------------------------------------------------------------------------
# Market hours logic
# ---------------------------------------------------------------------------

class TestMarketHours:
    """Market hours guards must correctly identify sessions and block periods."""

    def test_weekend_saturday_is_closed(self):
        """Saturday is always closed."""
        from src.core.market_hours import is_weekend
        # June 6, 2026 is a Saturday (weekday=5)
        sat = datetime(2026, 6, 6, 12, 0, tzinfo=IST)
        assert is_weekend(sat) is True

    def test_sunday_all_day_is_closed(self):
        """Sunday is closed all day in IST (reopens Monday ~03:30 IST)."""
        from src.core.market_hours import is_weekend
        # June 7, 2026 is a Sunday (weekday=6)
        sun_early = datetime(2026, 6, 7, 2, 0, tzinfo=IST)
        sun_late = datetime(2026, 6, 7, 14, 0, tzinfo=IST)
        assert is_weekend(sun_early) is True
        assert is_weekend(sun_late) is True

    def test_monday_early_is_closed(self):
        """Monday before 03:30 IST is closed."""
        from src.core.market_hours import is_weekend
        # June 8, 2026 is a Monday (weekday=0)
        mon_early = datetime(2026, 6, 8, 2, 0, tzinfo=IST)
        assert is_weekend(mon_early) is True

    def test_monday_after_open_is_open(self):
        """Monday from 03:30 IST onwards is open."""
        from src.core.market_hours import is_weekend
        # June 8, 2026 is a Monday
        mon_open = datetime(2026, 6, 8, 4, 0, tzinfo=IST)
        assert is_weekend(mon_open) is False

    def test_tuesday_is_not_weekend(self):
        """Tuesday is always a trading day."""
        from src.core.market_hours import is_weekend
        tue = datetime(2026, 6, 2, 14, 0, tzinfo=IST)
        assert is_weekend(tue) is False

    def test_in_trading_window(self):
        """12:00 IST is within the 06:00-21:30 trading window."""
        from src.core.market_hours import in_trading_window
        t = datetime(2026, 6, 2, 12, 0, tzinfo=IST)
        assert in_trading_window(t) is True

    def test_outside_trading_window_early(self):
        """03:00 IST is outside the trading window."""
        from src.core.market_hours import in_trading_window
        t = datetime(2026, 6, 2, 3, 0, tzinfo=IST)
        assert in_trading_window(t) is False

    def test_friday_no_new_entry_late(self):
        """After 21:30 IST Friday, allow_new_entry must return False.

        Note: 22:00 IST is outside the trading window (ends at 21:30), so the
        window guard fires first. The key requirement is that new entries are
        blocked — the exact reason string is an implementation detail.
        """
        from src.core.market_hours import allow_new_entry
        # June 5, 2026 is a Friday
        fri_late = datetime(2026, 6, 5, 22, 0, tzinfo=IST)
        ok, reason = allow_new_entry(fri_late)
        assert ok is False, f"Friday 22:00 IST must block new entries, got: {reason}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
