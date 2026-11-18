from decimal import Decimal
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.validation.access_lifecycle_20261118 import LifecyclePolicy, LifecycleEngine, IndeterminatePath
from src.backtesting.costs import SCENARIOS
from src.backtesting.engine import EngineConfig
from src.research.access_rules_20261118 import DAY
from tests.test_engine_live_parity import make_bars, SPEC, DAY as TEST_DAY

MONDAY = 1704067200


def fake_engine(balance=5000., positions=None, trades=None, phase="open", ts=MONDAY):
    return SimpleNamespace(
        balance=balance, positions=[] if positions is None else positions,
        trades=[] if trades is None else trades, stub=SimpleNamespace(balance=balance),
        cost=SCENARIOS["frictionless"], spec=SPEC,
        floating_pl=lambda: 0., equity_samples=[{"time": ts, "phase": phase,
             "net_liquidation_equity": balance, "balance": balance, "positions": []}],
    )


def test_flat_weekend_resets_each_day_with_cash_not_first_quote():
    policy = LifecyclePolicy("evaluation", MONDAY)
    engine = fake_engine(ts=MONDAY+3*DAY)
    policy.observe(engine, MONDAY+3*DAY)
    assert policy.resets["proven_flat_cash"] == 3
    assert policy.ledger.daily_floor == Decimal("4750.00")


def test_open_reset_requires_exact_midnight_and_preserves_actual_peak():
    policy = LifecyclePolicy("evaluation", MONDAY)
    policy._advance(MONDAY+DAY, flat=False, reset_equity=5200)
    assert policy.ledger.daily_floor == Decimal("4940.00")
    assert policy.ledger.peak_equity == Decimal("5200")
    with pytest.raises(IndeterminatePath, match="midnight"):
        policy._advance(MONDAY+2*DAY+60, flat=False)


def test_flat_evaluation_pass_is_realized_cash_not_floating_gain():
    policy = LifecyclePolicy("evaluation", MONDAY)
    trade = SimpleNamespace(exit_time=MONDAY, net_pl=150., strategy="TEST", exit_reason="TP")
    engine = fake_engine(5150., trades=[trade], ts=MONDAY+60, phase="interval_end")
    assert policy.observe(engine, MONDAY+60)
    assert policy.status == "passed"
    assert policy.cash_reconciliation_max_error == 0
    assert not policy.conditional_settlements


def test_exposure_over_unobserved_quote_gap_halts_before_inventing_fills():
    policy = LifecyclePolicy("funded", MONDAY)
    policy.last_positions = 1
    engine = fake_engine(ts=MONDAY+120)
    with pytest.raises(IndeterminatePath, match="quote_gap"):
        policy.observe(engine, MONDAY+120)
    assert not policy.conditional_settlements
    assert policy.ledger.balance == 5000


def test_midnight_interval_end_with_exposure_defers_until_exact_open():
    policy = LifecyclePolicy("evaluation", MONDAY+DAY-60)
    position = SimpleNamespace(lots=.02, is_buy=True, entry_time=MONDAY+DAY-60)
    engine = fake_engine(positions=[position], phase="interval_end", ts=MONDAY+DAY)
    assert policy.observe(engine, MONDAY+DAY) is False
    assert policy.ledger.utc_day == MONDAY//DAY
    assert policy.pending_midnight == MONDAY+DAY
    engine.equity_samples[-1]["phase"] = "open"
    policy.observe(engine, MONDAY+DAY)
    assert policy.ledger.utc_day == (MONDAY+DAY)//DAY
    assert policy.pending_midnight is None


def test_conditional_100_settlement_requires_full_eligibility_and_reconciles_cash():
    policy = LifecyclePolicy("funded", MONDAY)
    ledger = policy.ledger
    for day in range(29):
        policy._advance(MONDAY+day*DAY, flat=True)
        if day < 5:
            ledger.record_closed_profit(MONDAY+day*DAY, 25)
        ledger.observe(MONDAY+day*DAY, ledger.balance)
    engine = fake_engine(5125., ts=MONDAY+28*DAY)
    # Already booked synthetic ledger cash; no new engine closed events.
    policy.last_seen = MONDAY+28*DAY
    policy.observe(engine, MONDAY+28*DAY)
    assert len(policy.conditional_settlements) == 1
    assert policy.conditional_settlements[0]["cash"] == Decimal("100")
    assert engine.balance == pytest.approx(5013.89)
    assert ledger.balance == Decimal("5013.89")
    assert ledger.lifetime_best_day == Decimal("25")


def test_111_profit_is_not_enough_when_20pct_consistency_fails():
    policy = LifecyclePolicy("funded", MONDAY)
    for day in range(29):
        policy._advance(MONDAY+day*DAY, flat=True)
        if day < 3:
            policy.ledger.record_closed_profit(MONDAY+day*DAY, (25,25,61.11)[day])
        policy.ledger.observe(MONDAY+day*DAY, policy.ledger.balance)
    engine = fake_engine(5111.11, ts=MONDAY+28*DAY)
    policy.last_seen = MONDAY+28*DAY
    policy.observe(engine, MONDAY+28*DAY)
    assert not policy.conditional_settlements
    assert policy.blocked_eligibility["consistency"] == 1


def test_real_engine_refuses_incomplete_exposed_block_but_records_flat_exclusion():
    bars = make_bars(days=2)
    cfg = EngineConfig(sizing_mode="fixed", fixed_lots=.02, record_equity_samples=True,
                       entry_delay_sec=0, m1_policy="skip")
    policy = LifecyclePolicy("evaluation", TEST_DAY)
    engine = LifecycleEngine(bars, SCENARIOS["frictionless"], cfg, lifecycle_policy=policy)
    first = int(bars.m1["time"][0])
    engine.m1 = bars.m1[1:]
    engine._m1_t = engine.m1["time"]
    engine._m1_slice(first, first+900)
    assert len(engine.flat_coverage_exclusions) == 1
    engine.positions = [object()]
    with pytest.raises(IndeterminatePath, match="M1"):
        engine._m1_slice(first, first+900)


def test_cash_mismatch_fails_closed_instead_of_passing_account():
    policy = LifecyclePolicy("evaluation", MONDAY)
    with pytest.raises(IndeterminatePath, match="reconcile"):
        policy.observe(fake_engine(5200., ts=MONDAY+60), MONDAY+60)
    assert policy.status == "indeterminate"


@pytest.mark.parametrize("phase,low,margin,reason", [
    ("evaluation", 3840., 10., "daily_or_trailing"),
    ("funded", 3950., 10., "protector"),
    ("funded", 4000., 4500., "margin"),
])
def test_intraminute_rule_intervention_is_indeterminate_without_fake_closes(phase, low, margin, reason):
    policy = LifecyclePolicy(phase, MONDAY)
    engine = fake_engine(phase="interval_end", ts=MONDAY+60)
    row = np.zeros(1, dtype=[("time", "i8"), ("low", "f8"), ("high", "f8"), ("spread", "i8")])
    row["time"], row["low"], row["high"] = MONDAY, low, 4000.
    engine.m1 = row
    engine.margin_required = lambda *args: margin
    engine.equity_samples.insert(0, {"time": MONDAY, "phase": "open_after_orders", "balance": 5000.,
        "positions": [{"is_buy": True, "lots": .02, "entry_price": 4000., "accrued_swap": 0., "pending_commission": 0.}]})
    with pytest.raises(IndeterminatePath, match=reason):
        policy.observe(engine, MONDAY+60)
    assert policy.ledger.balance == 5000
    assert policy.ledger.status == "active"
    assert policy.status == "indeterminate"
    assert not policy.conditional_settlements
    assert engine.trades == []
