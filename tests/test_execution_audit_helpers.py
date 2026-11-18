"""Independent auditor compatibility with archived and corrected engine policies."""
import numpy as np
import pytest

from scripts.validation.execution_audit_helpers import first_replayed_minute, protective_fill, swap_charge


def test_entry_minute_policy_is_explicit_and_legacy_default_is_preserved():
    times = np.array([120, 180, 240])
    assert first_replayed_minute(times, 120) == 1
    assert first_replayed_minute(times, 120, {"walk_entry_bar_m1": True}) == 0
    assert first_replayed_minute(times, 140, {"walk_entry_bar_m1": True, "entry_delay_sec": 20}) == 1


@pytest.mark.parametrize("buy,opened,expected", [(True, 1990., 1989.98), (False, 2010., 2010.22)])
def test_gap_aware_fill_vs_archived_exact_level(buy, opened, expected):
    trade = {"is_buy": buy, "sl": 2000., "tp": 2020. if buy else 1980., "exit_reason": "SL"}
    got, reason = protective_fill(trade, opened, .2, .02, {"gap_fill_stops": True})
    assert reason == "SL" and got == pytest.approx(expected)
    old, _ = protective_fill(trade, opened, .2, .02, {})
    assert old == pytest.approx(1999.98 if buy else 2000.02)


def test_ambiguity_policy_can_reproduce_stop_first_and_target_first():
    trade = {"is_buy": True, "sl": 2000., "tp": 2020., "exit_reason": "TP"}
    assert protective_fill(trade, 2010., .2, .02, {}, both=True) == (1999.98, "SL")
    assert protective_fill(trade, 2010., .2, .02, {"ambiguous_resolution": "tp_first"}, both=True) == (2020., "TP")


def test_swap_uses_recorded_cost_configuration_including_triple_day():
    # Epoch day 0 Thursday, first crossed rollover day1 Friday (weekday4).
    trade = {"entry_time": 23 * 3600, "exit_time": 25 * 3600, "lots": .02, "is_buy": True}
    costs = {"swap_long_points": -100., "triple_swap_weekday": 4}
    assert swap_charge(trade, costs, .001, 100.) == pytest.approx(-.6)
    assert swap_charge(trade, {**costs, "enable_swap": False}, .001, 100.) == 0.
