"""The full-report suite, and the flattering-bias trap it must refuse.

src/backtesting/report.full_report exists so every backtest emits the whole
robustness family (Calmar, Omega, Sortino, recovery factor, Monte Carlo,
ablation, deflated Sharpe) instead of a script nobody remembers to run.

The important test here is the K_eff refusal. K_eff is the entropy of a
correlation matrix built from the supplied series, so it cannot exceed the number
of series. Supplying a handful while claiming dozens of trials understates N,
which SHRINKS the DSR threshold and INFLATES the DSR. That is bias in the
direction that gets a dead strategy funded, so it must be refused, not warned
about.
"""
import numpy as np
import pytest

from src.backtesting.report import format_report, full_report, sharpe_variance_across


class T:
    __slots__ = ("net_pl", "r_multiple", "entry_time", "exit_time", "strategy",
                 "session", "exit_reason", "lots", "is_buy", "minutes_open",
                 "minutes_to_mfe", "mae_r", "mfe_r", "is_pyramid",
                 "duplicate_of", "intrabar_ambiguous", "commission", "swap",
                 "nights_held", "gross_pl", "balance_after", "sl", "tp",
                 "initial_sl", "atr_at_entry", "entry_price", "exit_price",
                 "mae_price", "mfe_price", "ticket")

    def __init__(self, net, i):
        self.net_pl = float(net)
        self.r_multiple = float(net) / 10.0
        self.entry_time = 1_600_000_000 + i * 86400
        self.exit_time = self.entry_time + 3600
        self.strategy = "S"
        self.session = "LONDON"
        self.exit_reason = "TP" if net > 0 else "SL"
        self.lots = 0.02
        self.is_buy = bool(i % 2)
        self.minutes_open = 60
        self.minutes_to_mfe = 30
        self.mae_r = -0.5
        self.mfe_r = 1.0
        self.is_pyramid = False
        self.duplicate_of = None
        self.intrabar_ambiguous = False
        self.commission = 0.0
        self.swap = 0.0
        self.nights_held = 0
        self.gross_pl = float(net)
        self.balance_after = 5000.0
        self.sl = 1990.0
        self.tp = 2020.0
        self.initial_sl = 1990.0
        self.atr_at_entry = 5.0
        self.entry_price = 2000.0
        self.exit_price = 2010.0
        self.mae_price = 1995.0
        self.mfe_price = 2015.0
        self.ticket = i


def _trades(n=120, seed=3):
    rng = np.random.default_rng(seed)
    pls = np.where(rng.random(n) < 0.42, 16.0, -9.0)
    return [T(p, i) for i, p in enumerate(pls)]


def _equity(trades, start=5000.0):
    eq, bal = [], start
    for t in trades:
        bal += t.net_pl
        eq.append((t.exit_time, bal))
    return eq


def test_report_emits_the_whole_family():
    tr = _trades()
    rep = full_report(tr, _equity(tr), 5000.0, num_trials=1)
    for k in ("sortino_ratio", "omega_ratio", "calmar_ratio", "recovery_factor",
              "sharpe_per_trade", "skew", "kurtosis"):
        assert k in rep["ratios"], k
    assert "prob_final_below_start" in rep["monte_carlo"]
    assert "drop_best_3" in rep["ablation"]
    assert "raw_trials" in rep["deflated_sharpe"]
    assert rep["stats"]["trades"] == len(tr)


def test_num_trials_one_is_flagged_as_a_claim():
    tr = _trades()
    rep = full_report(tr, _equity(tr), 5000.0, num_trials=1)
    assert "warning_trials" in rep["deflated_sharpe"], (
        "num_trials=1 asserts nothing else was ever tested; it must be flagged")


def test_missing_sr_variance_is_flagged():
    tr = _trades()
    rep = full_report(tr, _equity(tr), 5000.0, num_trials=10)
    assert rep["sr_variance"] is None
    assert "warning" in rep["deflated_sharpe"]


def test_keff_is_refused_when_series_are_fewer_than_trials():
    """The flattering-bias trap: 3 series cannot estimate independence of 48."""
    tr = _trades()
    series = [[t.net_pl for t in _trades(60, seed=s)] for s in (1, 2, 3)]
    rep = full_report(tr, _equity(tr), 5000.0, num_trials=48,
                      variant_series=series)
    assert rep["k_eff"]["refused"] is True
    assert rep["k_eff"]["k_eff"] is None
    assert "effective_trials" not in rep["deflated_sharpe"], (
        "an effective-N DSR from too few series inflates the result")
    assert "48" in rep["k_eff"]["note"] and "3" in rep["k_eff"]["note"]


def test_keff_is_computed_when_every_trial_has_a_series():
    tr = _trades()
    series = [[t.net_pl for t in _trades(60, seed=s)] for s in range(1, 9)]
    rep = full_report(tr, _equity(tr), 5000.0, num_trials=8,
                      variant_series=series)
    assert rep["k_eff"].get("refused") is None
    assert rep["k_eff"]["k_eff"] is not None
    assert 1.0 <= rep["k_eff"]["k_eff"] <= 8.0
    assert "effective_trials" in rep["deflated_sharpe"]


def test_sr_variance_is_measured_from_the_series():
    series = [[t.net_pl for t in _trades(60, seed=s)] for s in range(1, 9)]
    v = sharpe_variance_across(series)
    assert v is not None and v > 0
    assert sharpe_variance_across([[1.0] * 5]) is None, "too few series"


def test_more_trials_never_raises_the_dsr():
    """Monotonicity: additional trials can only make a result less significant."""
    tr = _trades()
    eq = _equity(tr)
    prev = None
    for n in (1, 5, 20, 100):
        d = full_report(tr, eq, 5000.0, num_trials=n,
                        sr_variance=0.02)["deflated_sharpe"]["raw_trials"]["dsr"]
        if prev is not None:
            assert d <= prev + 1e-9, "DSR rose with more trials at N=%d" % n
        prev = d


def test_format_report_is_printable():
    tr = _trades()
    txt = format_report(full_report(tr, _equity(tr), 5000.0, num_trials=1))
    assert "deflated sharpe" in txt
    assert "monte carlo" in txt
    assert isinstance(txt, str) and len(txt.splitlines()) > 10
