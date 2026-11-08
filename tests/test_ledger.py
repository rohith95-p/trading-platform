"""The trial ledger and the holdout ledger.

Both exist because of a specific failure on 2026-11-09: the deflated Sharpe
needed N and the per-variant return series, and this project could supply
neither. These tests pin the properties that make the ledgers trustworthy --
idempotence, race-safety, and refusal to flatter.
"""
import json
import os

import pytest

from src.research import ledger as L


@pytest.fixture
def ledger_dirs(tmp_path, monkeypatch):
    """Point both ledgers at a temp dir and re-enable recording."""
    monkeypatch.setattr(L, "TRIAL_DIR", str(tmp_path / "trials"))
    monkeypatch.setattr(L, "SPEND_DIR", str(tmp_path / "spends"))
    monkeypatch.delenv(L.DISABLE_ENV, raising=False)
    monkeypatch.delenv("ULTRA_TRIAL_PURPOSE", raising=False)
    monkeypatch.delenv("ULTRA_TRIAL_NOTE", raising=False)
    return tmp_path


W = (1_000_000_000, 1_100_000_000)


def _pls(n=50, seed=0):
    import numpy as np
    rng = np.random.default_rng(seed)
    return list(np.where(rng.random(n) < 0.4, 16.0, -9.0))


# ---------------------------------------------------------------- trial ledger

def test_records_and_counts(ledger_dirs):
    assert L.count_trials() == 0
    L.record_trial(["A"], W, _pls(), cost="c1", purpose="select")
    L.record_trial(["B"], W, _pls(seed=1), cost="c1", purpose="select")
    assert L.count_trials() == 2
    assert L.count_trials(purpose="select") == 2
    assert L.count_trials(purpose="judge") == 0


def test_identical_trial_is_not_counted_twice(ledger_dirs):
    """Re-running the same configuration must not inflate N."""
    a = L.record_trial(["A"], W, _pls(), cost="c1", purpose="select")
    b = L.record_trial(["A"], W, _pls(), cost="c1", purpose="select")
    assert a == b
    assert L.count_trials() == 1


def test_a_different_cost_model_is_a_different_trial(ledger_dirs):
    L.record_trial(["A"], W, _pls(), cost="realistic_ecn")
    L.record_trial(["A"], W, _pls(), cost="frictionless")
    assert L.count_trials() == 2


def test_a_different_window_is_a_different_trial(ledger_dirs):
    L.record_trial(["A"], W, _pls(), cost="c")
    L.record_trial(["A"], (W[0], W[1] + 86400), _pls(), cost="c")
    assert L.count_trials() == 2


def test_series_is_saved_because_keff_needs_it(ledger_dirs):
    L.record_trial(["A"], W, [1.0, -2.0, 3.5], cost="c")
    rec = L.trials()[0]
    assert rec["series"] == [1.0, -2.0, 3.5]
    assert rec["trades"] == 3
    assert rec["commit"]


def test_summary_stats_are_computed(ledger_dirs):
    L.record_trial(["A"], W, [10.0, 10.0, -5.0], cost="c")
    r = L.trials()[0]
    assert r["net"] == pytest.approx(15.0)
    assert r["profit_factor"] == pytest.approx(4.0)
    assert r["win_rate"] == pytest.approx(66.667, abs=0.01)


def test_disabled_by_env(ledger_dirs, monkeypatch):
    monkeypatch.setenv(L.DISABLE_ENV, "1")
    assert L.record_trial(["A"], W, _pls(), cost="c") is None
    assert L.count_trials() == 0


def test_purpose_defaults_to_env(ledger_dirs, monkeypatch):
    monkeypatch.setenv("ULTRA_TRIAL_PURPOSE", "confirm")
    L.record_trial(["A"], W, _pls(), cost="c")
    assert L.trials()[0]["purpose"] == "confirm"


def test_record_never_raises_on_bad_input(ledger_dirs):
    assert L.record_trial(["A"], W, ["not a number"], cost="c") is None
    assert L.count_trials() == 0


def test_effective_trials_refuses_when_series_are_missing(ledger_dirs):
    L.record_trial(["A"], W, _pls(), cost="c")
    out = L.effective_trials()
    assert out["refused"] is True and out["k_eff"] is None


def test_effective_trials_computes_with_enough_series(ledger_dirs):
    for i in range(6):
        L.record_trial(["S%d" % i], W, _pls(60, seed=i), cost="c")
    out = L.effective_trials()
    assert out.get("refused") is None
    assert 1.0 <= out["k_eff"] <= 6.0
    assert out["k_raw"] == 6


# -------------------------------------------------------------- holdout ledger

def test_first_decision_on_a_window_is_allowed(ledger_dirs):
    rec = L.spend_window("2016-2022", W[0], W[1], "confirm")
    assert rec["is_decision"] is True
    assert rec["prior_decisions"] == 0
    assert len(L.window_history("2016-2022")) == 1


def test_second_decision_on_the_same_window_raises(ledger_dirs):
    L.spend_window("2016-2022", W[0], W[1], "confirm")
    with pytest.raises(L.WindowAlreadySpent) as exc:
        L.spend_window("2016-2022", W[0], W[1], "judge")
    assert "already been spent" in str(exc.value)


def test_diagnostic_use_is_recorded_but_never_refused(ledger_dirs):
    for _ in range(4):
        L.spend_window("2016-2022", W[0], W[1], "diagnostic")
    assert len(L.window_history("2016-2022")) == 4
    # and a decision is still allowed afterwards: looking is not deciding
    rec = L.spend_window("2016-2022", W[0], W[1], "confirm")
    assert rec["prior_decisions"] == 0


def test_respend_requires_an_explicit_flag_and_is_recorded(ledger_dirs):
    L.spend_window("2016-2022", W[0], W[1], "confirm")
    rec = L.spend_window("2016-2022", W[0], W[1], "judge",
                         allow_respend=True, reason="owner asked, 2026-11-09")
    assert rec["respend"] is True
    assert rec["reason"] == "owner asked, 2026-11-09"
    assert rec["prior_decisions"] == 1


def test_separate_windows_do_not_collide(ledger_dirs):
    L.spend_window("2004-2016", W[0], W[1], "select")
    L.spend_window("2016-2022", W[0], W[1], "confirm")  # must not raise
    assert len(L.window_history("2004-2016")) == 1
    assert len(L.window_history("2016-2022")) == 1


def test_slug_handles_awkward_names(ledger_dirs):
    L.spend_window("2022-08-01 .. 2026/11/01", W[0], W[1], "judge")
    hist = L.window_history("2022-08-01 .. 2026/11/01")
    assert len(hist) == 1


def test_spend_report_lists_windows(ledger_dirs):
    assert "no window" in L.spend_report()
    L.spend_window("2004-2016", W[0], W[1], "select")
    rep = L.spend_report()
    assert "2004-2016" in rep and "select" in rep


# ------------------------------------------------------------ engine integration

def test_engine_records_a_trial(ledger_dirs, monkeypatch):
    """The whole point: nobody has to remember to call record_trial."""
    import numpy as np

    from src.backtesting.costs import SCENARIOS
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.data import BarSet, SymbolSpec

    spec = SymbolSpec(symbol="XAUUSDm", digits=3, point=0.001,
                      trade_tick_size=0.001, trade_tick_value=0.1,
                      volume_min=0.01, volume_max=200.0, volume_step=0.01,
                      contract_size=100.0)
    dtype = np.dtype([("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
                      ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<u8"),
                      ("spread", "<i4"), ("real_volume", "<u8")])
    n = 4000
    t0 = 1_600_000_000
    m15 = np.zeros(n, dtype=dtype)
    px = 2000.0 + np.cumsum(np.full(n, 0.01))
    m15["time"] = t0 + np.arange(n) * 900
    m15["open"] = px
    m15["close"] = px
    m15["high"] = px + 1.0
    m15["low"] = px - 1.0
    m15["spread"] = 200
    m15["tick_volume"] = 100

    bars = BarSet(symbol="XAUUSDm", m15=m15, m5=None, m1=None, d1=None,
                  spec=spec, manifests={})
    cfg = EngineConfig(m1_policy="coarse", warmup_bars=300, history_bars=250)
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg)
    eng.run([])          # no strategies: zero trades, but still a recorded trial

    assert L.count_trials() == 1, "the engine must record without being asked"
    rec = L.trials()[0]
    assert rec["cost"].startswith("spread=")
    assert rec["window_start"] and rec["window_end"]
