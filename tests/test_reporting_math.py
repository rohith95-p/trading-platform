"""Hand calculations through the public report entry point, not a strategy test."""
import json
import math

import pytest

from src.backtesting.metrics import bootstrap_ci_metrics
from src.backtesting.report import full_report
from tests.test_report_suite import T

BASE = 1_600_000_000
DAY = 86400
YEAR = 365.25*DAY


def hand_trades(pnls, days=None, start=100.):
    output, balance = [], start
    for i, pnl in enumerate(pnls):
        trade = T(pnl, i)
        trade.exit_time = BASE+int((days[i] if days else i+1)*DAY)
        trade.entry_time = trade.exit_time-60
        balance += pnl
        trade.balance_after = balance
        output.append(trade)
    return output


def report(pnls, days=None, equity=None, end=YEAR):
    trades = hand_trades(pnls, days)
    if equity is None:
        equity = [(BASE, 100.)]+[(t.exit_time, t.balance_after) for t in trades]
    return full_report(trades, equity, 100., start_ts=BASE, end_ts=BASE+int(end))


def test_sparse_calendar_year_calmar_is_one_not_holding_time_extrapolation():
    trades = hand_trades([-10., 20.])
    equity = [(BASE, 100.)]+[(t.exit_time, t.balance_after) for t in trades]
    first = full_report(trades, equity, 100., start_ts=BASE, end_ts=BASE+int(YEAR))
    for trade in trades:
        trade.minutes_open = 1_000_000
    second = full_report(trades, equity, 100., start_ts=BASE, end_ts=BASE+int(YEAR))
    assert first["stats"]["annualised_return_pct"] == 10.
    assert first["stats"]["max_drawdown_pct"] == 10.
    assert first["stats"]["calmar_ratio"] == first["ratios"]["calmar_ratio"] == 1.
    assert second["ratios"]["calmar_ratio"] == 1.
    assert first["stats"]["max_drawdown_duration_days"] == 2.


def test_drawdown_duration_equal_high_recovery_flat_peak_and_unrecovered_tail():
    equity = [(BASE+day*DAY, value) for day, value in
              [(0, 100.), (1, 90.), (2, 100.), (5, 100.), (6, 90.)]]
    result = report([-10., 10., -10.], [1, 2, 6], equity, end=10*DAY)
    assert result["stats"]["max_drawdown_duration_days"] == 5.
    assert result["stats"]["max_drawdown"] == 10.


def test_flat_high_water_mark_never_counts_as_drawdown_duration():
    result = report([], equity=[(BASE, 100.), (BASE+10*DAY, 100.)], end=10*DAY)
    assert result["stats"]["max_drawdown_duration_days"] == 0.
    assert result["ratios"]["calmar_ratio"] is None
    assert result["stats"]["profit_factor"] is None


def test_unrecovered_tail_is_extended_through_explicit_observation_end():
    result = report([-10.], end=10*DAY)
    assert result["stats"]["max_drawdown_duration_days"] == 10.


def test_largest_percentage_drawdown_need_not_coincide_with_largest_dollar_drawdown():
    result = report([-50., 950., -100.])
    assert result["stats"]["max_drawdown"] == 100.
    assert result["stats"]["max_drawdown_pct"] == 50.
    assert result["ratios"]["annualised_return_pct"] == 800.
    assert result["ratios"]["calmar_ratio"] == 16.


def test_profit_factor_uses_unrounded_after_cost_trade_sums():
    result = report([.004, -.001])
    assert result["stats"]["profit_factor"] == 4.
    assert result["stats"]["omega_ratio"] == 4.
    assert result["stats"]["gross_loss"] == .001
    assert result["stats"]["profit_factor_status"] == "finite"


def test_sortino_is_per_trade_zero_target_rms_over_all_observations():
    expected = 1/math.sqrt(3.)  # mean(4,-2,0)=2/3; downside RMS=sqrt(4/3)
    first = report([4., -2., 0.])
    scaled = report([40., -20., 0.])
    assert first["stats"]["sortino_ratio"] == pytest.approx(expected, abs=1e-6)
    assert first["ratios"]["sortino_ratio"] == scaled["ratios"]["sortino_ratio"]
    assert "unannualized" in first["metric_definitions"]["sortino_ratio"]


@pytest.mark.parametrize("pnls,pf,sortino", [([1.]*5, None, None), ([-1.]*5, 0., -1.), ([0.]*5, None, None), ([], None, None)])
def test_ratio_edge_cases_and_whole_report_json_are_explicit_and_finite(pnls, pf, sortino):
    result = report(pnls)
    assert result["stats"]["profit_factor"] == pf
    assert result["ratios"]["sortino_ratio"] == sortino
    json.dumps(result, allow_nan=False)


def test_bankruptcy_then_cash_recovery_does_not_create_a_valid_cagr():
    result = report([-110., 210.])
    assert result["stats"]["closed_balance_nonpositive"]
    assert result["ratios"]["annualised_return_pct"] is None
    assert result["ratios"]["calmar_ratio"] is None


def test_sparse_equity_points_do_not_erase_known_trade_cash_exhaustion():
    result = report([-110., 120.], equity=[(BASE, 100.), (BASE+2*DAY, 110.)])
    assert result["stats"]["closed_balance_nonpositive"]
    assert result["ratios"]["annualised_return_pct"] is None


def test_cashflow_or_inconsistent_equity_does_not_create_performance_cagr():
    result = report([10.], equity=[(BASE, 100.), (BASE+DAY, 200.)])
    assert result["ratios"]["annualised_return_pct"] is None
    assert any("cashflows_or_inconsistent" in note for note in result["stats"]["metric_notes"])


@pytest.mark.parametrize("value,expected_status", [(1., "unbounded"), (0., "undefined")])
def test_bootstrap_nonfinite_mass_is_retained_without_nan_interpolation(value, expected_status):
    result = bootstrap_ci_metrics([value]*5, n_resamples=100)
    for key in ("profit_factor", "sortino_ratio"):
        assert result[key]["ci_lower"] is None
        assert result[key]["ci_upper"] is None
        assert result[key]["ci_upper_status"] == expected_status
        assert result[key][expected_status+"_fraction"] == 1.
    json.dumps(result, allow_nan=False)


def test_bootstrap_mixed_samples_can_have_unbounded_upper_ratio():
    result = bootstrap_ci_metrics([1., 1., 1., 1., -1.], n_resamples=1000)
    assert result["profit_factor"]["observed"] == 4.
    assert result["profit_factor"]["ci_upper_status"] == "unbounded"
    assert result["profit_factor"]["unbounded_fraction"] > .025
    json.dumps(result, allow_nan=False)


def test_nonfinite_source_pnl_is_rejected_at_normal_entry_point():
    with pytest.raises(ValueError, match="finite"):
        report([float("nan")])
