from datetime import datetime, timezone
import json
from types import SimpleNamespace

from scripts.december_observer import START
from scripts.december_telegram import EA_STATUS, fill_messages, report, snapshot


def deal(ticket, position, entry, magic, profit=0, symbol="XAUUSDm"):
    return SimpleNamespace(ticket=ticket, position_id=position, symbol=symbol, entry=entry,
                           magic=magic, time_msc=(START + ticket) * 1000, volume=.02,
                           price=2500., type=0 if entry == 0 else 1, profit=profit,
                           fee=-.05, commission=-.10, swap=0)


def test_only_december_fills_including_manual_close():
    opening, closing = deal(1, 100, 0, 7320), deal(3, 100, 1, 0, profit=10)
    foreign = deal(2, 200, 0, 7311)
    messages = list(fill_messages([closing, foreign, opening]))
    assert [key for key, _ in messages] == ["1", "3"]
    assert "Entry filled" in messages[0][1].headline
    assert "Exit filled" in messages[1][1].headline
    assert "Cash impact of this fill +9.85 USD" in messages[1][1].lines


def test_reports_only_confirmed_sends_and_does_not_repost(tmp_path):
    path = tmp_path / "ledger.json"
    now = datetime.fromtimestamp(START + 10, tz=timezone.utc)
    fills = [deal(1, 100, 0, 7324)]
    ledger = {"state": None, "fills": []}
    assert not report("active", None, fills, now, ledger, path, send=lambda _: False)
    assert not path.exists()
    sent = []

    def send(message):
        sent.append(message)
        return True

    assert report("active", None, fills, now, ledger, path, send)
    assert report("active", None, fills, now, json.loads(path.read_text()), path, send)
    assert len(sent) == 2


def test_pass_remains_visible_when_order_permission_is_off(tmp_path):
    files = tmp_path / "Files"
    files.mkdir()
    (files / EA_STATUS).write_text("2026.12.01 00:00:05,evaluation_passed,5150.00,5150.00,5000.00,0")
    terminal = SimpleNamespace(connected=True, commondata_path=tmp_path, trade_allowed=False)
    account = SimpleNamespace(trade_mode=0, login=123, server="Demo")
    api = SimpleNamespace(terminal_info=lambda: terminal, account_info=lambda: account,
                          history_deals_get=lambda *args: [])
    now = datetime.fromtimestamp(START + 10, tz=timezone.utc)
    assert snapshot(api, now, 123, "Demo")[0] == "evaluation_passed"
    assert snapshot(api, now, 124, "Demo") == ("account_identity_refused", None, [])
