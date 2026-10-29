"""Scheduled Telegram status report: fires once per slot, weekdays only, no replay after restart."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest import mock

from src.core import trade_alerts as ta

IST = timezone(timedelta(hours=5, minutes=30))


def test_status_report_schedule():
    sent = []
    acct = NS(login=1, server="S", balance=5000.0, equity=5004.0)
    with mock.patch.object(ta, "_status_sent", set()), \
            mock.patch.object(ta.alerts, "send_html", lambda t, *a, **k: sent.append(t)), \
            mock.patch.object(ta.mt5, "account_info", lambda: acct):
        ta.maybe_status_report(datetime(2026, 11, 2, 7, 0, tzinfo=IST), [], 0.0)    # after start: seed only
        ta.maybe_status_report(datetime(2026, 11, 2, 17, 59, tzinfo=IST), [], 0.0)  # not due
        ta.maybe_status_report(datetime(2026, 11, 2, 18, 0, tzinfo=IST), [NS(profit=5.0, swap=-1.0)], 12.5,
                               {"trailing_floor": 4520.0, "daily_floor": 4950.0})
        ta.maybe_status_report(datetime(2026, 11, 2, 18, 5, tzinfo=IST), [], 0.0)   # same slot
        ta.maybe_status_report(datetime(2026, 11, 3, 6, 0, tzinfo=IST), [], 0.0)    # next morning
        ta.maybe_status_report(datetime(2026, 11, 7, 6, 0, tzinfo=IST), [], 0.0)    # Saturday
    assert len(sent) == 2
    assert "STATUS" in sent[0] and "+$4.00" in sent[0] and "DD floor" in sent[0]
