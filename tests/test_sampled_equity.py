"""Sampled account marks are separate from realized cash and continuous equity."""
from dataclasses import asdict

import pytest

from src.backtesting.costs import CostModel, SCENARIOS
from src.backtesting.engine import BacktestEngine, EngineConfig, Position
from scripts.validation.sampled_equity_check import verify_samples
from tests.test_engine_live_parity import C_NY, DAY, Fire, make_bars, run


def position(buy=True, entry_time=C_NY):
    return Position(ticket=1, strategy="synthetic", magic=1, is_buy=buy, lots=.02,
                    entry_price=4000., entry_time=entry_time, sl=3900. if buy else 4100.,
                    tp=4100. if buy else 3900., initial_sl=3900. if buy else 4100.,
                    atr_at_entry=1., session="synthetic")


@pytest.mark.parametrize("buy,expected", [(True, -20.), (False, 19.6)])
def test_mark_sides_and_pending_commission_do_not_change_cash(buy, expected):
    engine = BacktestEngine(make_bars(), SCENARIOS["realistic_ecn"],
                           EngineConfig(starting_balance=500., record_equity_samples=True))
    engine.positions.append(position(buy))
    engine._sample_equity(C_NY+60, 3990., 200., "open")
    sample = engine.equity_samples[0]
    assert sample["balance"] == engine.balance == 500.
    assert sample["floating_pl"] == pytest.approx(expected)
    assert sample["gross_equity"] == pytest.approx(500.+expected)
    assert sample["net_liquidation_equity"] == pytest.approx(500.+expected-.07)
    assert not engine.equity  # legacy closed-balance record is separate


def test_drawdown_can_exist_without_realized_loss_and_recover():
    engine = BacktestEngine(make_bars(), CostModel(enable_swap=False),
                           EngineConfig(starting_balance=500., record_equity_samples=True))
    engine.positions.append(position())
    engine._sample_equity(C_NY, 4000., 200., "open")
    engine._sample_equity(C_NY+60, 3980., 200., "interval_end")
    engine._sample_equity(C_NY+120, 4000., 200., "interval_end")
    assert engine.balance == 500. and not engine.trades
    assert engine._sample_drawdowns["gross_equity"]["maximum_usd"] == pytest.approx(40.)
    assert engine._sample_drawdowns["gross_equity"]["maximum_pct"] == pytest.approx(8.)
    assert engine.equity_samples[-1]["gross_equity"] == 500.


def test_rollover_accrues_swap_in_net_liquidation_without_mutating_cash():
    engine = BacktestEngine(make_bars(), SCENARIOS["realistic_ecn"],
                           EngineConfig(starting_balance=500., record_equity_samples=True))
    engine.positions.append(position(entry_time=DAY-3600))
    engine._sample_equity(DAY, 4000., 200., "open")
    sample = engine.equity_samples[-1]
    assert sample["accrued_swap"] == pytest.approx(-1.031)
    assert sample["net_liquidation_equity"] == pytest.approx(500.-1.031-.07)
    assert sample["gross_equity"] == engine.balance == 500.


def test_sampling_does_not_change_trades_and_independent_arithmetic_reconciles():
    bars = make_bars(price_fn=lambda t: 4000.)
    _, control = run(bars, [Fire(candles=[C_NY])])
    _, sampled = run(bars, [Fire(candles=[C_NY])], record_equity_samples=True)
    trades = [asdict(t) for t in sampled.trades]
    assert trades == [asdict(t) for t in control.trades]
    assert sampled.equity == control.equity
    assert sampled.equity_samples and not control.equity_samples
    assert {s["phase"] for s in sampled.equity_samples} == {
        "open", "open_after_orders", "interval_end", "final_settlement"}
    audit = verify_samples(sampled.equity_samples, trades, bars.m1,
                           asdict(SCENARIOS["observed"]), asdict(bars.spec), 500.,
                           sampled.diagnostics["sampled_drawdown"])
    assert audit["errors"] == 0, audit
    assert sampled.diagnostics["floating_drawdown_verified"] is False
    sampled.equity_samples[0]["gross_equity"] += 1.
    assert verify_samples(sampled.equity_samples, trades, bars.m1,
                          asdict(SCENARIOS["observed"]), asdict(bars.spec), 500.,
                          sampled.diagnostics["sampled_drawdown"])["errors"] > 0
