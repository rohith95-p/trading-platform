from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from scripts.validation.mt5_demo_tick_capture import capture, validate_quotes, validate_window, TICK_DTYPE, require_running_terminal
from scripts.validation.tick_fixture_reconciliation import START, END, offline_quotes, compare, tick_replay


def test_known_tick_target_precedes_later_stop_even_when_m1_touches_both():
    quotes = offline_quotes()
    report = compare(quotes, "synthetic_offline_fixture")
    buy, sell = report["fixtures"]
    assert report["historical_verification"] is False
    assert buy["tick"]["trade"]["exit_reason"] == "TP"
    assert buy["minute"]["trade"]["exit_reason"] == "SL"
    assert buy["tick"]["trade"]["net_pl"] == pytest.approx(2.93)
    assert buy["minute"]["trade"]["net_pl"] == pytest.approx(-2.11)
    assert buy["tick"]["trade"]["exit_time_ms"] == (START+900)*1000+200
    # Ask-only widening stops the true short but escapes opening-spread M1 reconstruction.
    assert sell["tick"]["trade"]["exit_reason"] == "SL"
    assert sell["minute"]["trade"]["exit_reason"] == "TP"
    assert sell["tick"]["trade"]["exit_price"] == pytest.approx(2001.52)
    assert sell["tick"]["trade"]["net_pl"] == pytest.approx(-3.15)
    assert sell["minute"]["trade"]["net_pl"] == pytest.approx(2.93)
    assert sell["tick"]["observed_quote_net_liquidation_max_drawdown_usd"] == pytest.approx(3.15)


def test_tick_stop_gaps_fill_at_actual_quote_plus_adverse_slip():
    ticks = np.array([(START*1000, 2000., 2000.2), (START*1000+1, 1990., 1990.2)], dtype=TICK_DTYPE)
    trade = tick_replay(ticks, signal_ms=START*1000, is_buy=True)["trade"]
    assert trade["exit_price"] == pytest.approx(1989.98)
    assert trade["exit_reason"] == "SL"


def test_duplicate_tick_timestamps_preserve_source_order():
    ticks = np.array([(START*1000, 2000., 2000.2), (START*1000+1, 2002., 2002.2),
                      (START*1000+1, 1990., 1990.2)], dtype=TICK_DTYPE)
    validate_quotes(ticks, START*1000, END*1000)
    assert tick_replay(ticks, signal_ms=START*1000, is_buy=True)["trade"]["exit_reason"] == "TP"


@pytest.mark.parametrize("bad", ["crossed", "nan", "unordered", "out_of_range", "empty"])
def test_bad_quote_history_is_rejected(bad):
    quotes = offline_quotes().copy()
    if bad == "crossed":
        quotes["ask"][0] = quotes["bid"][0]-1
    elif bad == "nan":
        quotes["bid"][0] = np.nan
    elif bad == "unordered":
        quotes[[0, 1]] = quotes[[1, 0]]
    elif bad == "out_of_range":
        quotes["time_msc"][0] = (START-1)*1000
    else:
        quotes = quotes[:0]
    with pytest.raises(ValueError):
        validate_quotes(quotes, START*1000, END*1000)


class FakeTerminal:
    ACCOUNT_TRADE_MODE_DEMO = 0
    COPY_TICKS_ALL = 123
    def __init__(self, mode=0, change=False):
        self.mode, self.change, self.account_calls, self.calls = mode, change, 0, []
    def account_info(self):
        self.account_calls += 1
        self.calls.append("account_info")
        return SimpleNamespace(login=456 if self.change and self.account_calls > 1 else 123,
                               server="Fixture-Demo", trade_mode=self.mode)
    def symbol_info(self, symbol):
        self.calls.append("symbol_info")
        return SimpleNamespace(point=.001, digits=3)
    def copy_ticks_range(self, symbol, start, end, flags):
        self.calls.append("copy_ticks_range")
        assert start.tzinfo == end.tzinfo == timezone.utc
        return offline_quotes()
    # There is intentionally no login, order_send, order_check or settings API.


def capture_args():
    return dict(expected_login=123, expected_server="Fixture-Demo", symbol="XAUUSDm",
                start=datetime.fromtimestamp(START, timezone.utc),
                end=datetime.fromtimestamp(END, timezone.utc))


def test_demo_capture_reads_only_pinned_demo_and_records_provenance():
    terminal = FakeTerminal()
    quotes, manifest = capture(terminal, **capture_args())
    assert len(quotes) == 66
    assert manifest["identity_verified_demo"] is True
    assert manifest["holdout_accessed"] is False
    assert manifest["orders_sent"] == 0
    assert terminal.calls == ["account_info", "symbol_info", "copy_ticks_range", "account_info"]


@pytest.mark.parametrize("mode", [1, 2])
def test_real_and_contest_accounts_fail_before_historical_read(mode):
    terminal = FakeTerminal(mode)
    with pytest.raises(RuntimeError, match="pinned demo"):
        capture(terminal, **capture_args())
    assert "copy_ticks_range" not in terminal.calls


def test_identity_switch_during_capture_is_rejected():
    with pytest.raises(RuntimeError, match="pinned demo"):
        capture(FakeTerminal(change=True), **capture_args())


def test_holdout_and_unbounded_window_fail_without_any_terminal_calls():
    terminal = FakeTerminal()
    args = capture_args()
    args.update(start=datetime(2026, 11, 1, tzinfo=timezone.utc),
                end=datetime(2026, 11, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="holdout"):
        capture(terminal, **args)
    assert not terminal.calls
    with pytest.raises(ValueError, match="timezone"):
        validate_window(datetime(2025, 1, 6), datetime(2025, 1, 7))


def test_capture_cannot_auto_launch_a_terminal_or_attach_a_different_path():
    with pytest.raises(RuntimeError, match="manually"):
        require_running_terminal("C:/demo/terminal64.exe", [])
    with pytest.raises(RuntimeError, match="manually"):
        require_running_terminal("C:/demo/terminal64.exe", [{"exe": "C:/other/terminal64.exe"}])
    require_running_terminal("C:/demo/terminal64.exe", [{"exe": "C:/demo/terminal64.exe"}])
