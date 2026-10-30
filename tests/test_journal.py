"""23:59 IST trade journal: what gets recorded, dedupe, the summary layout, once per day (2026-10-30)."""
import csv
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

from src.core import alerts, journal

IST = timezone(timedelta(hours=5, minutes=30))
DAY = datetime(2026, 10, 30, tzinfo=IST)
T0 = int(DAY.timestamp())


def deal(pid, t, entry, typ, price, magic=7320, profit=0.0, reason=3, comment="ASIAN_RANGE_FILTERED_V6"):
    return NS(position_id=pid, time=T0 + t, entry=entry, type=typ, price=price, volume=0.02, magic=magic,
              profit=profit, commission=0.0, swap=0.0, reason=reason, symbol="XAUUSDm", comment=comment)


class FakeMT5:
    def __init__(self):
        self.deals = [
            deal(1, 7 * 3600 + 900, 0, 1, 3987.06),                                   # own, closed today: TP
            deal(1, 12 * 3600 + 900, 1, 0, 3960.39, profit=53.33, reason=5, comment="[tp]"),
            deal(2, 8 * 3600, 0, 0, 4000.0, magic=999, comment="foreign"),            # foreign magic: ignored
            deal(2, 9 * 3600, 1, 1, 4001.0, magic=999, profit=2.0),
            deal(3, 20 * 3600, 0, 1, 3950.0, comment="NY_SESSION_REVERSAL_V6"),       # still open: ignored
        ]

    def history_deals_get(self, a, b):
        assert isinstance(a, int) and isinstance(b, int)          # epoch seconds, never aware datetimes
        return self.deals

    def history_orders_get(self, position):
        return [NS(sl=4002.29, tp=3960.39)] if position == 1 else []

    def account_info(self):
        return NS(balance=5053.33)


def test_only_own_closed_trades_are_recorded():
    tr = journal.closed_trades(FakeMT5(), T0, T0 + 86400)
    assert [t.ticket for t in tr] == [1]
    t = tr[0]
    assert (t.side, t.entry_price, t.exit_price, t.stop_loss, t.target, t.exit_reason, t.net) == \
           ("SELL", 3987.06, 3960.39, 4002.29, 3960.39, "take profit", 53.33)
    assert t.entry_time_ist == "2026-10-30 07:15:00"


def test_append_dedupes_by_ticket(tmp_path):
    p = str(tmp_path / "j.csv")
    tr = journal.closed_trades(FakeMT5(), T0, T0 + 86400)
    assert journal.append(tr, p) == 1
    assert journal.append(tr, p) == 0
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["net"] == "53.33"


def test_summary_puts_each_item_on_its_own_line():
    a = journal.day_summary(DAY.date(), journal.closed_trades(FakeMT5(), T0, T0 + 86400), 5053.33)
    assert a.headline == "Day summary · Fri 30 Oct" and a.severity == alerts.INFO
    assert "   Entry price: 3987.06 (07:15)" in a.lines and "   Exit price: 3960.39 (12:15, take profit)" in a.lines
    assert "Day net: +$53.33" in a.lines and "Balance: $5,053.33" in a.lines


def test_runs_once_after_2359(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(journal, "JOURNAL_FILE", str(tmp_path / "j.csv"))
    monkeypatch.setattr(journal, "_done", set())
    monkeypatch.setattr(journal.alerts, "notify", lambda a: sent.append(a))
    mt5 = FakeMT5()
    journal.maybe_run(mt5, DAY.replace(hour=23, minute=58))
    assert sent == []
    journal.maybe_run(mt5, DAY.replace(hour=23, minute=59))
    journal.maybe_run(mt5, DAY.replace(hour=23, minute=59, second=30))
    assert len(sent) == 1
    assert len(list(csv.DictReader(open(tmp_path / "j.csv", encoding="utf-8")))) == 1
