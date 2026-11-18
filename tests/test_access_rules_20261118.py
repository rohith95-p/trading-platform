"""Synthetic accounting paths only: no market data or production imports."""
from dataclasses import FrozenInstanceError
from decimal import Decimal as D

import pytest

from src.research.access_rules_20261118 import DAY, PROFILE, ExperimentalAccessLedger


MONDAY = 1704067200  # 2024-01-01 00:00 UTC


def advance(ledger, day):
    for number in range(ledger.utc_day - MONDAY // DAY + 1, day + 1):
        ledger.observe(MONDAY + number * DAY, ledger.balance, midnight_equity=ledger.balance)


def profits(ledger, values, start_day=0):
    for day, value in enumerate(values, start_day):
        advance(ledger, day)
        stamp = MONDAY + day * DAY + 3600
        ledger.record_closed_profit(stamp, value)
        ledger.observe(stamp, ledger.balance)


def ready():
    ledger = ExperimentalAccessLedger("funded", MONDAY)
    profits(ledger, [25] * 5)
    advance(ledger, 28)
    return ledger


def test_profile_is_frozen_and_sources_are_dated():
    assert PROFILE.source_date == "2026-11-18"
    assert len(PROFILE.source_urls) >= 6
    with pytest.raises(FrozenInstanceError):
        PROFILE.consistency = D("0.4")


def test_lifetime_equity_peak_uses_percentage_and_floating_profit():
    ledger = ExperimentalAccessLedger("funded", MONDAY)
    ledger.observe(MONDAY + 1, 5200)
    assert ledger.trailing_floor == D("4888")
    ledger.observe(MONDAY + 2, 5000)
    assert ledger.trailing_floor == D("4888")


def test_daily_floor_uses_exact_reset_equity_not_day_high():
    ledger = ExperimentalAccessLedger("evaluation", MONDAY)
    ledger.observe(MONDAY + 1, 5200)
    ledger.observe(MONDAY + DAY, 5050, midnight_equity=5050)
    assert ledger.daily_floor == D("4797.50")
    ledger.observe(MONDAY + DAY + 1, 5300)
    assert ledger.daily_floor == D("4797.50")


def test_missing_midnight_and_multiple_days_are_rejected():
    ledger = ExperimentalAccessLedger("funded", MONDAY)
    with pytest.raises(ValueError, match="midnight"):
        ledger.observe(MONDAY + DAY + 60, 5000)
    with pytest.raises(ValueError, match="each UTC reset"):
        ledger.observe(MONDAY + 2 * DAY, 5000, midnight_equity=5000)
    assert ledger.utc_day == MONDAY // DAY


def test_floor_equality_safe_and_below_breaches_evaluation():
    ledger = ExperimentalAccessLedger("evaluation", MONDAY)
    ledger.observe(MONDAY + 1, 4750)
    assert ledger.status == "active"
    ledger.observe(MONDAY + 2, "4749.99")
    assert ledger.status == "breached"
    ledger.observe(MONDAY + 3, 6000)
    assert ledger.status == "breached"


def test_evaluation_has_target_but_no_payout():
    ledger = ExperimentalAccessLedger("evaluation", MONDAY)
    ledger.record_closed_profit(MONDAY + 1, 150)
    ledger.observe(MONDAY + 1, ledger.balance)
    assert ledger.evaluation_passed(open_positions=0)
    assert not ledger.evaluation_passed(open_positions=1)
    check = ledger.eligibility(MONDAY + 2, kyc_verified=True, open_positions=0)
    assert "not_funded" in check.reasons


def test_100_cash_gross_is_not_automatically_eligible():
    ledger = ExperimentalAccessLedger("funded", MONDAY)
    profits(ledger, [25, 25, D("61.11")])
    advance(ledger, 28)
    check = ledger.eligibility(MONDAY + 28 * DAY, kyc_verified=True, open_positions=0)
    assert check.cycle_profit == D("111.11")
    assert check.qualifying_days == 3
    assert "consistency" in check.reasons
    assert check.required_consistency_profit == D("305.55")


def test_exact_20_percent_boundary_with_five_days_passes():
    ledger = ready()
    check = ledger.eligibility(MONDAY + 28 * DAY, kyc_verified=True, open_positions=0)
    assert check.eligible
    assert check.required_consistency_profit == D("125")
    assert check.qualifying_days == 5


def test_negative_days_reduce_denominator_without_erasing_qualifying_days():
    ledger = ExperimentalAccessLedger("funded", MONDAY)
    profits(ledger, [25] * 5 + [-1])
    advance(ledger, 28)
    check = ledger.eligibility(MONDAY + 28 * DAY, kyc_verified=True, open_positions=0)
    assert check.qualifying_days == 5
    assert check.cycle_profit == D("124")
    assert "consistency" in check.reasons


def test_same_utc_day_netting_cannot_manufacture_qualifying_days():
    ledger = ExperimentalAccessLedger("funded", MONDAY)
    ledger.record_closed_profit(MONDAY + 1, 50)
    ledger.record_closed_profit(MONDAY + 2, -30)
    check = ledger.eligibility(MONDAY + 3, kyc_verified=True, open_positions=0)
    assert check.qualifying_days == 0
    assert check.lifetime_best_day == D("20")


@pytest.mark.parametrize("kyc,positions,reason", [(None,0,"kyc_unverified"),
                                                (False,0,"kyc_unverified"),
                                                (True,1,"open_positions")])
def test_payout_fails_closed_for_unknown_identity_or_open_positions(kyc, positions, reason):
    ledger = ready()
    check = ledger.eligibility(MONDAY + 28 * DAY, kyc_verified=kyc, open_positions=positions)
    assert reason in check.reasons


def test_first_window_is_exact_28_days():
    ledger = ExperimentalAccessLedger("funded", MONDAY)
    profits(ledger, [25] * 5)
    advance(ledger, 27)
    check = ledger.eligibility(MONDAY + 28 * DAY - 1, kyc_verified=True, open_positions=0)
    assert "payout_window" in check.reasons
    advance(ledger, 28)
    assert ledger.eligibility(MONDAY + 28 * DAY, kyc_verified=True, open_positions=0).eligible


def test_request_is_pending_until_explicit_settlement_and_no_double_request():
    ledger = ready()
    ts = MONDAY + 28 * DAY
    pending = ledger.request_payout(ts, kyc_verified=True, open_positions=0)
    assert pending["gross"] == D("111.11")
    assert pending["cash"] == D("100.00")
    assert ledger.balance == D("5125")
    assert not ledger.payouts
    with pytest.raises(ValueError, match="pending_payout"):
        ledger.request_payout(ts, kyc_verified=True, open_positions=0)
    paid = ledger.settle_payout(ts + 1, approved=True, open_positions=0)
    assert paid["cash"] == D("100")
    assert ledger.balance == D("5013.89")
    assert ledger.trailing_floor == D("5013.89") * D(".94")
    assert ledger.daily_floor == D("5125") * D(".97") - D("111.11")


def test_midnight_observation_can_raise_peak_before_later_observation():
    ledger = ExperimentalAccessLedger("evaluation", MONDAY)
    ledger.observe(MONDAY + DAY + 60, 5000, midnight_equity=5300)
    assert ledger.peak_equity == D("5300")
    assert ledger.daily_floor == D("5035")
    assert ledger.status == "breached"


def test_permanent_reduced_split_applies_to_later_payout():
    ledger = ExperimentalAccessLedger("funded", MONDAY)
    ledger.observe(MONDAY + 1, 4900)
    ledger.record_closed_profit(MONDAY + 2, -100)
    ledger.observe(MONDAY + 2, 4900)
    profits(ledger, [50] * 8, start_day=1)
    advance(ledger, 28)
    pending = ledger.request_payout(MONDAY + 28 * DAY, kyc_verified=True, open_positions=0)
    assert pending["split"] == D(".5")
    assert pending["gross"] == D("200")


def test_lifetime_best_day_survives_settlement_and_cycle_resets():
    ledger = ready()
    ts = MONDAY + 28 * DAY
    ledger.request_payout(ts, kyc_verified=True, open_positions=0)
    ledger.settle_payout(ts, approved=True, open_positions=0)
    assert ledger.lifetime_best_day == D("25")
    assert ledger.cycle_profit == 0
    assert ledger.cycle_days == {}
    assert ledger.next_payout_at == MONDAY + 42 * DAY
    profits(ledger, [25] * 5, start_day=29)
    advance(ledger, 42)
    assert ledger.eligibility(MONDAY + 42 * DAY, kyc_verified=True, open_positions=0).eligible


def test_rejected_payment_preserves_profit_records_and_allows_new_request():
    ledger = ready()
    ts = MONDAY + 28 * DAY
    ledger.request_payout(ts, kyc_verified=True, open_positions=0)
    assert ledger.settle_payout(ts + 1, approved=False, open_positions=0) is None
    assert ledger.cycle_profit == 125
    assert ledger.last_paid_at is None
    assert ledger.request_payout(ts + 2, kyc_verified=True, open_positions=0)


def test_protector_hit_is_lifetime_and_needs_rearming_after_flatten():
    ledger = ExperimentalAccessLedger("funded", MONDAY)
    ledger.observe(MONDAY + 1, 4900)
    assert ledger.protector_hits == 1
    assert ledger.split == D(".5")
    ledger.observe(MONDAY + 2, 4900)
    assert ledger.protector_hits == 1
    ledger.record_closed_profit(MONDAY + 3, -100)
    ledger.observe(MONDAY + 3, 4900)
    advance(ledger, 1)
    assert ledger.split == D(".5")
    ledger.observe(MONDAY + DAY + 1, 4800)
    assert ledger.protector_hits == 2
    assert ledger.status == "breached"


def test_evaluation_does_not_apply_funded_protector():
    ledger = ExperimentalAccessLedger("evaluation", MONDAY)
    ledger.observe(MONDAY + 1, 4900)
    assert ledger.status == "active"
    assert ledger.protector_hits == 0


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "-Infinity"])
def test_nonfinite_cash_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        ExperimentalAccessLedger("funded", MONDAY, balance=value)


def test_backward_event_rejected():
    ledger = ExperimentalAccessLedger("funded", MONDAY)
    ledger.observe(MONDAY + 10, 5000)
    with pytest.raises(ValueError, match="chronological"):
        ledger.record_closed_profit(MONDAY + 9, 20)


@pytest.mark.parametrize("count", [None, False, -1, "0"])
def test_unknown_position_count_never_passes(count):
    ledger = ExperimentalAccessLedger("evaluation", MONDAY)
    with pytest.raises(ValueError, match="known nonnegative"):
        ledger.evaluation_passed(open_positions=count)


def test_profit_request_cannot_withdraw_principal():
    ledger = ready()
    with pytest.raises(ValueError, match="exceeds"):
        ledger.request_payout(MONDAY + 28 * DAY, target_cash=1000, kyc_verified=True, open_positions=0)


def test_pending_flat_account_cannot_collect_trades_during_review():
    ledger = ready()
    ts = MONDAY + 28 * DAY
    ledger.request_payout(ts, kyc_verified=True, open_positions=0)
    with pytest.raises(ValueError, match="pauses"):
        ledger.record_closed_profit(ts + 1, 30)
    with pytest.raises(ValueError, match="pauses"):
        ledger.observe(ts + 1, ledger.balance - 20)
    assert ledger.last_at == ts
    ledger.observe(ts + DAY, ledger.balance, midnight_equity=ledger.balance)
    ledger.settle_payout(ts + DAY, approved=False, open_positions=0)
    ledger.record_closed_profit(ts + DAY + 1, 30)
    assert ledger.balance == D("5155")
