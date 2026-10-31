"""Daily-loss Atlas stops resume at the next UTC day; Atlas state survives restarts (owner 2026-10-30)."""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from scripts import watchdog
from src.atlas.rules import AtlasState
from src.core import alerts, atlas_bridge, main_loop, ops

UTC = timezone.utc
IST = timezone(timedelta(hours=5, minutes=30))


def test_expired_latch_clears_itself_and_is_archived():
    ops.set_halt("Atlas FLATTEN: daily", "atlas_rule_engine", notify=False,
                 expires_utc=datetime.now(UTC) - timedelta(seconds=1))
    assert ops.halt_status() is None
    folder = os.path.dirname(ops.HALT_FILE)
    assert any(f.startswith("HALT_LATCH.cleared_") for f in os.listdir(folder))


def test_future_expiry_stays_halted_and_no_expiry_needs_a_human():
    ops.set_halt("daily", "atlas_rule_engine", notify=False, expires_utc=datetime.now(UTC) + timedelta(hours=1))
    assert ops.halt_status()["reason"] == "daily"
    ops.clear_halt("test")
    ops.set_halt("trailing", "atlas_rule_engine", notify=False)
    assert ops.halt_status()["reason"] == "trailing"


def test_unreadable_expiry_fails_closed():
    with open(ops.HALT_FILE, "w") as f:
        json.dump({"reason": "x", "expires_utc": "not-a-date"}, f)
    assert ops.halt_status() is not None


@pytest.mark.parametrize("reasons, daily", [
    (["daily_loss_hard:0.97>=0.8"], True),
    (["daily_loss_hard:0.97>=0.8", "protector_soft:51.00>=50.00"], True),     # soft extras don't count
    (["daily_loss_hard:0.97>=0.8", "trailing_dd_hard:0.81>=0.8"], False),
    (["protector_hard:80.00>=75.00"], False),
    (["fail_closed:ValueError:x"], False),
    ([], False),
])
def test_only_a_pure_daily_loss_stop_expires(reasons, daily):
    assert main_loop._daily_only(reasons) is daily


def test_atlas_state_round_trip_and_resume():
    st = AtlasState.new(initial_balance=5000.0, now_utc=datetime(2026, 11, 2, 9, tzinfo=UTC), equity=5000.0)
    st.peak_equity, st.day_ref_equity, st.day_high_equity = 5320.5, 5290.0, 5301.0
    st.cycle_day_profits[datetime(2026, 11, 2).date()] = 1.25
    main_loop._save_atlas_state(st)
    back = main_loop._load_atlas_state("evaluation")
    assert back == st
    assert main_loop._load_atlas_state("funded") is None          # other phase: start fresh


def test_corrupt_or_missing_state_starts_fresh():
    assert main_loop._load_atlas_state("evaluation") is None
    with open(atlas_bridge.ATLAS_STATE_FILE, "w") as f:
        f.write("{broken")
    assert main_loop._load_atlas_state("evaluation") is None


def test_pulse_says_paused_with_resume_time():
    halt = {"reason": "Atlas FLATTEN: daily", "expires_utc": "2026-11-03T00:00:00+00:00"}
    a = watchdog.build_pulse(None, None, halt, datetime(2026, 11, 2, 22, 0, tzinfo=IST))
    assert a.headline == "Bot paused · 22:00" and a.severity == alerts.INFO
    assert a.lines[1] == "Resumes by itself at Tue 05:30 IST"


class _Stop(Exception):
    pass


def test_watchdog_paused_halt_is_one_silent_message():
    passes = iter(range(2))

    def _sleep(sec):
        if sec == watchdog.CHECK_EVERY:
            try:
                next(passes)
            except StopIteration:
                raise _Stop

    halt = {"reason": "Atlas FLATTEN: daily", "set_at_utc": "2026-01-01T00:00:00+00:00",
            "expires_utc": "2099-01-01T00:00:00+00:00"}
    with patch.object(watchdog.ops, "halt_status", return_value=halt), \
         patch.object(watchdog, "_loop_alive", return_value=False), \
         patch.object(watchdog, "_start_loop") as start, \
         patch.object(watchdog, "_alert") as alert, \
         patch.object(watchdog, "PROTECT_PROFIT_ON", False), \
         patch.object(watchdog, "_protect_profit_alive", return_value=False), \
         patch.object(watchdog, "PULSE_EVERY_H", 0), \
         patch.object(watchdog.os.path, "exists", return_value=False), \
         patch.object(watchdog.time, "sleep", side_effect=_sleep):
        with pytest.raises(_Stop):
            watchdog.main()
    start.assert_not_called()
    msgs = [c for c in alert.call_args_list if "paused" in c.args[0] or "halted" in c.args[0]]
    assert len(msgs) == 1 and "paused until" in msgs[0].args[0] and msgs[0].args[1] == alerts.INFO
