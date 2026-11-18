"""Causal fill and coverage contracts on synthetic data, never market selection."""
from dataclasses import replace

import numpy as np
import pytest

from src.backtesting.costs import SCENARIOS
from src.backtesting.engine import BacktestEngine, EngineConfig, MissingM1Error
from tests.test_engine_live_parity import C_NY, Fire, make_bars, run


@pytest.mark.parametrize("delay", [1, 20, 59])
def test_subminute_delay_cannot_manufacture_quotes_from_future_close(delay):
    bars = make_bars()
    with pytest.raises(ValueError, match="timestamped quotes"):
        BacktestEngine(bars, SCENARIOS["observed"], EngineConfig(entry_delay_sec=delay))


@pytest.mark.parametrize("parity", [False, True])
def test_stop_is_active_in_entry_minute(parity):
    bars = make_bars()
    m1 = bars.m1.copy()
    j = np.flatnonzero(m1["time"] == C_NY + 900)[0]
    m1["high"][j], m1["low"][j] = 5000., 3000.
    _, result = run(replace(bars, m1=m1), [Fire(candles=[C_NY])],
                    live_exec_order=parity)
    trade = result.trades[0]
    assert trade.exit_time == trade.entry_time == C_NY + 900
    assert trade.exit_reason == "SL"
    assert trade.intrabar_ambiguous


@pytest.mark.parametrize("hole_offset", [0, 60, 840])
def test_require_rejects_partial_first_middle_and_last_minute(hole_offset):
    bars = make_bars()
    m1 = bars.m1[bars.m1["time"] != C_NY + 900 + hole_offset]
    with pytest.raises(MissingM1Error):
        run(replace(bars, m1=m1), [Fire(candles=[C_NY])])


def test_skip_partial_candle_blocks_entry_and_records_missing_minutes():
    bars = make_bars()
    m1 = bars.m1[bars.m1["time"] != C_NY + 900 + 60]
    _, result = run(replace(bars, m1=m1), [Fire(candles=[C_NY])], m1_policy="skip")
    assert result.diagnostics["partial_m1_candles"] == 1
    assert result.diagnostics["partial_m1_minutes_missing"] == 1
    assert result.diagnostics["bars_skipped_no_m1"] == 1
    assert not [t for t in result.trades if t.entry_time < C_NY + 1800]


def test_duplicate_minute_does_not_mask_a_missing_minute():
    bars = make_bars()
    m1 = bars.m1.copy()
    j = np.flatnonzero(m1["time"] == C_NY + 900 + 60)[0]
    m1["time"][j] = C_NY + 900
    with pytest.raises(MissingM1Error):
        run(replace(bars, m1=m1), [Fire(candles=[C_NY])])


def test_risk_geometry_isolated_between_engines_and_production_module():
    from src.core import risk_manager as production
    bars = make_bars()
    constants = (production.TP_ATR_MULTIPLIER, production.TRAIL_ACTIVATION_ATR,
                 production.TRAIL_DISTANCE_ATR)
    custom = BacktestEngine(bars, SCENARIOS["observed"],
                           EngineConfig(tp_atr_mult=11., trail_activation_atr=7.,
                                        trail_distance_atr=2.))
    custom_rm, _ = custom._make_risk_manager()
    plain_rm, _ = BacktestEngine(bars, SCENARIOS["observed"], EngineConfig())._make_risk_manager()
    assert (production.TP_ATR_MULTIPLIER, production.TRAIL_ACTIVATION_ATR,
            production.TRAIL_DISTANCE_ATR) == constants
    # Control ATR to test executed production formula, not just copied metadata.
    custom_rm.get_latest_atr = lambda *args: 1.
    plain_rm.get_latest_atr = lambda *args: 1.
    a = custom_rm.calculate_atr_stops(4000., True, None, 1.)
    b = plain_rm.calculate_atr_stops(4000., True, None, 1.)
    assert a.tp == pytest.approx(4011.)
    assert b.tp == pytest.approx(4000. + constants[0])
    assert custom_rm.calculate_atr_stops(4000., True, None, 1.).tp == a.tp
