"""Telegram message layout, priorities, the watchdog's hourly pulse and halt stand-down (2026-10-30)."""
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from scripts import watchdog
from src.core import alerts, main_loop
from src.core.alerts import send as real_send   # captured before conftest's autouse patch of alerts.send

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def telegram(monkeypatch):
    """Capture what would go to Telegram (alerts are normally off under pytest)."""
    sent = []
    monkeypatch.setattr(alerts, "send", real_send)
    monkeypatch.setattr(alerts, "_alerts_disabled", lambda: False)
    monkeypatch.setattr(alerts, "_record", lambda line: None)
    monkeypatch.setattr(alerts, "_webhook", lambda text, sev: False)
    monkeypatch.setattr(alerts, "_telegram", lambda text, parse_html=False, silent=False:
                        sent.append((text, silent)) or True)
    return sent


def test_alert_layout_has_headline_lines_and_action():
    a = alerts.Alert("Bot halted <now>", ("Why: x & y",), alerts.CRITICAL, action="Clear it")
    assert a.html() == "🚨 <b>Bot halted &lt;now&gt;</b>\nWhy: x &amp; y\n\n👉 Clear it"


@pytest.mark.parametrize("sev, silent", [(alerts.INFO, True), (alerts.TRADE, False),
                                         (alerts.WARN, False), (alerts.CRITICAL, False)])
def test_only_info_is_silent(telegram, sev, silent):
    alerts.send("something", sev)
    assert telegram[-1][1] is silent


def test_send_strips_hand_made_markers_and_source(telegram):
    alerts.send("⚠️ KILL SWITCH ⚠️\nline two", alerts.WARN, context={"source": "watchdog", "why": "test"})
    text = telegram[-1][0]
    assert text.startswith("⚠️ <b>KILL SWITCH</b>")
    assert "line two" in text and "Why: test" in text and "watchdog" not in text


def test_explain_atlas_reasons_in_plain_words():
    out = main_loop._explain_atlas(["daily_loss_hard:0.9697>=0.8", "protector_hard:78.20>=75.00"])
    assert out == "today's loss at 97% of the Atlas limit; open-trade loss $78.20 (limit $75.00)"


def _status(**kw):
    s = dict(balance=5000.0, equity=4990.0, open=1, floating=-10.0, today=12.5,
             trailing_floor=4500.0, daily_floor=4750.0, ts=time.time())
    s.update(kw)
    return s


def test_pulse_all_good():
    a = watchdog.build_pulse(_status(), 20, None, datetime(2026, 11, 2, 14, 0, tzinfo=IST))
    assert a.severity == alerts.INFO and a.headline == "All good · 14:00"
    assert a.lines == ("Balance: $5,000.00", "Equity: $4,990.00", "Today closed: +$12.50",
                       "Open trades: 1 (−$10.00)",
                       "Daily limit: $240.00 left (stops at $4,750.00)",
                       "Max-loss limit: $490.00 left (stops at $4,500.00)")


def test_pulse_stale_and_halted():
    now = datetime(2026, 11, 2, 14, 0, tzinfo=IST)
    assert watchdog.build_pulse(_status(ts=time.time() - 3600), 20, None, now).severity == alerts.WARN
    assert watchdog.build_pulse(_status(), 900, None, now).headline.startswith("Bot not responding")
    h = watchdog.build_pulse(_status(), 20, {"reason": "Atlas FLATTEN"}, now)
    assert h.headline.startswith("Bot halted") and "Atlas FLATTEN" in h.lines[0]


def test_pulse_schedule_hourly_weekdays_once():
    sent = set()
    mon = datetime(2026, 11, 2, 9, 0, tzinfo=IST)
    assert watchdog._pulse_due(mon, sent)
    assert not watchdog._pulse_due(mon.replace(minute=5), sent)          # same hour
    assert not watchdog._pulse_due(mon.replace(hour=10, minute=30), sent)  # not the top of the hour
    assert watchdog._pulse_due(mon.replace(hour=10, minute=1), sent)
    assert not watchdog._pulse_due(datetime(2026, 11, 7, 9, 0, tzinfo=IST), sent)  # Saturday


class _Stop(Exception):
    pass


def test_watchdog_stands_down_on_halt_with_one_message():
    """A latched halt: no restart loop, one message, no FATAL exit."""
    passes = iter(range(3))

    def _sleep(sec):
        if sec == watchdog.CHECK_EVERY:
            try:
                next(passes)
            except StopIteration:
                raise _Stop

    halt = {"reason": "Atlas FLATTEN", "set_at_utc": "2026-01-01T00:00:00+00:00"}
    with patch.object(watchdog.ops, "halt_status", return_value=halt), \
         patch.object(watchdog, "_loop_alive", return_value=False), \
         patch.object(watchdog, "_start_loop") as start, \
         patch.object(watchdog, "handle_main_loop_crash") as crash, \
         patch.object(watchdog, "_alert") as alert, \
         patch.object(watchdog, "PROTECT_PROFIT_ON", False), \
         patch.object(watchdog, "_protect_profit_alive", return_value=False), \
         patch.object(watchdog, "PULSE_EVERY_H", 0), \
         patch.object(watchdog.os.path, "exists", return_value=False), \
         patch.object(watchdog.time, "sleep", side_effect=_sleep):
        with pytest.raises(_Stop):
            watchdog.main()
    start.assert_not_called()
    crash.assert_not_called()
    halted = [c for c in alert.call_args_list if "halted" in c.args[0]]
    sev = halted[0].kwargs.get("severity", halted[0].args[1] if len(halted[0].args) > 1 else None)
    assert len(halted) == 1 and sev == alerts.CRITICAL   # an old latch -> loud
