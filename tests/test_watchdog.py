"""
Tests for watchdog crash recovery and alerting (P0-4).
"""

import sys
import pytest
from unittest.mock import Mock, patch

from scripts import watchdog
from src.core import alerts


class TestWatchdogCrashRecovery:
    """Tests for watchdog auto-restart, alerting, and fatal exit logic."""

    @patch('scripts.watchdog._start_loop')
    @patch('scripts.watchdog._alert')
    @patch('src.core.trade_log.lifecycle')
    def test_watchdog_restarts_main_loop_and_alerts_on_crash(self, mock_lifecycle, mock_alert, mock_start):
        """
        P0-4 Action 6: On crash, watchdog must alert, log traceback/lifecycle event,
        wait, and restart main_loop.
        """
        restarts = watchdog.handle_main_loop_crash(consecutive_restarts=0, wait_seconds=0)

        assert restarts == 1
        assert mock_alert.call_count == 1
        args, kwargs = mock_alert.call_args
        assert "restarting it (attempt 1/3)" in args[0]
        assert kwargs.get("severity") == alerts.INFO      # a first, self-healed restart is routine

        assert mock_lifecycle.call_count == 1
        l_args, l_kwargs = mock_lifecycle.call_args
        assert l_args[0] == "watchdog_restart"
        assert l_kwargs.get("attempt") == 1

        assert mock_start.call_count == 1

    @patch('scripts.watchdog._start_loop')
    @patch('scripts.watchdog._alert')
    @patch('src.core.trade_log.lifecycle')
    def test_watchdog_fatal_exit_on_3_consecutive_restarts(self, mock_lifecycle, mock_alert, mock_start):
        """
        P0-4 Action 3: On 3rd consecutive restart failure, fire CRITICAL alert
        and exit non-zero (sys.exit(1)).
        """
        with pytest.raises(SystemExit) as exc_info:
            watchdog.handle_main_loop_crash(consecutive_restarts=2, wait_seconds=0)

        assert exc_info.value.code == 1

        assert mock_alert.call_count == 1
        args, kwargs = mock_alert.call_args
        assert "gave up" in args[0]
        assert kwargs.get("severity") == alerts.CRITICAL

        assert mock_lifecycle.call_count == 1
        l_args, l_kwargs = mock_lifecycle.call_args
        assert l_args[0] == "watchdog_fatal_exit"
        assert l_kwargs.get("attempts") == 3

        mock_start.assert_not_called()


class _Stop(Exception):
    pass


@pytest.mark.parametrize("on, alive, stops, starts", [
    (False, True, 1, 0),   # switched off, still running -> killed, never restarted
    (False, False, 0, 0),  # switched off, not running -> left alone
    (True, False, 0, 1),   # on, not running -> restarted (unchanged behaviour)
])
def test_protect_profit_switch(on, alive, stops, starts):
    def _sleep(sec):  # end after the first full pass (its CHECK_EVERY wait)
        if sec == watchdog.CHECK_EVERY:
            raise _Stop
    with patch.object(watchdog, "PROTECT_PROFIT_ON", on), \
         patch.object(watchdog, "_protect_profit_alive", return_value=alive), \
         patch.object(watchdog, "_stop_protect_profit") as stop, \
         patch.object(watchdog, "_loop_alive", return_value=True), \
         patch.object(watchdog, "_alert"), \
         patch.object(watchdog.ops, "halt_status", return_value=None), \
         patch.object(watchdog, "PULSE_EVERY_H", 0), \
         patch.object(watchdog.os.path, "exists", return_value=False), \
         patch.object(watchdog.subprocess, "Popen") as popen, \
         patch("builtins.open"), \
         patch.object(watchdog.time, "sleep", side_effect=_sleep):
        with pytest.raises(_Stop):
            watchdog.main()
    assert stop.call_count == stops
    assert popen.call_count == starts
