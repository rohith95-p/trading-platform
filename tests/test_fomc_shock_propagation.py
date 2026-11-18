"""Synthetic causal checks before the FOMC empirical experiment."""
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.research.fomc_shock_propagation import (
    signal_features, FOMCShockStrategy, OpeningClockAndTimeExit, ClosedATRResearchEngine,
    replay_one,
)
from src.backtesting.costs import SCENARIOS
from src.backtesting.engine import EngineConfig
from tests.test_engine_live_parity import make_bars, DAY


def test_features_use_only_completed_pre_and_shock_minutes():
    release = 1704121200
    dtype = [("time", "i8"), ("open", "f8"), ("close", "f8")]
    w = np.zeros(90, dtype=dtype)
    w["time"] = release - 3600 + np.arange(90) * 60
    w["open"] = 2000
    w["close"] = 2000.1
    w["close"][-1] = 2010
    f = signal_features(w, release)
    assert f["candidate"] and f["direction"] == 1
    assert f["latest_feature_close_time"] == release + 1800
    altered = w.copy()
    altered["close"][60:] = 1900
    g = signal_features(altered, release)
    assert g["pre_risk_30m"] == f["pre_risk_30m"]
    assert g["direction"] == -1
    with pytest.raises(ValueError, match="incomplete"):
        signal_features(w[:-1], release)


def test_strategy_never_uses_post_freeze_before_entry_and_fires_exact_clock():
    f = dict(direction=1, latest_feature_close_time=100)
    s = FOMCShockStrategy(120, f)
    assert s.evaluate(None) is None
    s.now = 119
    assert s.evaluate(None) is None
    s.now = 120
    assert s.evaluate(None).is_buy
    s.feature["latest_feature_close_time"] = 121
    with pytest.raises(ValueError, match="available"):
        s.evaluate(None)


def test_time_exit_ignores_end_callback_and_uses_new_open_not_prior_close():
    s = FOMCShockStrategy(100, dict(direction=1, latest_feature_close_time=90))
    p = SimpleNamespace(is_buy=True)
    calls = []
    engine = SimpleNamespace(equity_samples=[dict(time=200, phase="interval_end", bid=2000., ask=2000.2)],
                             positions=[p], cost=SCENARIOS["realistic_ecn"], spec=SimpleNamespace(point=.001))
    engine._close = lambda *args: calls.append(args)
    policy = OpeningClockAndTimeExit(s, 200)
    assert not policy.observe(engine, 200)
    assert not calls
    engine.equity_samples.append(dict(time=200, phase="open", bid=1990., ask=1990.2))
    assert policy.observe(engine, 200)
    assert calls[0][1] == pytest.approx(1990. - engine.cost.slip(.001))
    assert s.now == 200


def test_closed_atr_adapter_is_independent_of_forming_bar_future_range():
    bars = make_bars(days=4)
    cfg = EngineConfig(enable_d1_bias_gate=False)
    engine = ClosedATRResearchEngine(bars, SCENARIOS["observed"], cfg)
    rm, _ = engine._make_risk_manager()
    view = bars.m15[-100:].copy()
    before = rm.calculate_atr_stops(4000., True, view, 2., 4.)
    view["high"][-1] += 500
    view["low"][-1] -= 500
    after = rm.calculate_atr_stops(4000., True, view, 2., 4.)
    assert before.sl == after.sl and before.tp == after.tp


def test_actual_engine_fills_only_at_delayed_open_and_exits_by_fixed_horizon(monkeypatch):
    from src.backtesting import engine as engine_module
    monkeypatch.setattr(engine_module.market_hours, "ENFORCE_TRADING_WINDOW", False)
    bars = make_bars(price_fn=lambda t: 4000. + .1 * np.sin(t / 2000.), spread=20)
    release = DAY + 12 * 3600
    feature = dict(direction=1, latest_feature_close_time=release + 1800)
    result, balance = replay_one(bars, release, feature, SCENARIOS["observed"], 5000., "candidate", delay=60)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_time == release + 46 * 60
    assert trade.exit_time <= release + 105 * 60
    assert balance == pytest.approx(5000. + trade.net_pl)
    assert result.diagnostics["exits_unchecked_no_m1"] == 0


def test_night_window_requires_explicit_research_process_configuration(monkeypatch):
    from src.backtesting import engine as engine_module
    bars = make_bars(price_fn=lambda t: 4000. + .1 * np.sin(t / 2000.), spread=20)
    release = DAY + 18 * 3600
    feature = dict(direction=1, latest_feature_close_time=release + 1800)
    monkeypatch.setattr(engine_module.market_hours, "ENFORCE_TRADING_WINDOW", True)
    blocked, _ = replay_one(bars, release, feature, SCENARIOS["observed"], 5000., "candidate")
    assert not blocked.trades
    monkeypatch.setattr(engine_module.market_hours, "ENFORCE_TRADING_WINDOW", False)
    allowed, _ = replay_one(bars, release, feature, SCENARIOS["observed"], 5000., "candidate")
    assert len(allowed.trades) == 1
    assert allowed.trades[0].entry_time == release + 45 * 60
