"""The broker is measured, not assumed.

A fake terminal stands in for MT5 here. The cases that matter are the ones that
would otherwise be silent on a new account: a different gold symbol, different
price decimals (which rescale the spread gate), and a server clock that is not
UTC (which every session gate in src/strategies assumes).
"""
import datetime as dt
import json
from types import SimpleNamespace

import pytest

from src.core import broker_probe as bp

NOW = dt.datetime.now(dt.timezone.utc).timestamp()


class FakeTerminal:
    """Enough of the MetaTrader5 module surface for the probe."""

    def __init__(self, symbols=("XAUUSDm", "EURUSD"), digits=3, offset_hours=0.0,
                 tick_age_sec=1.0, swap_long=-51.55, leverage=200, currency="USD",
                 margin_mode=0, tick=True):
        self._symbols = symbols
        self._digits = digits
        self._offset = offset_hours
        self._tick_age = tick_age_sec
        self._swap_long = swap_long
        self._leverage = leverage
        self._currency = currency
        self._margin_mode = margin_mode
        self._has_tick = tick
        self.selected = []

    def account_info(self):
        return SimpleNamespace(server="Exness-MT5Trial11", login=198874999,
                               currency=self._currency, leverage=self._leverage,
                               trade_allowed=True, margin_mode=self._margin_mode)

    def symbols_get(self):
        return [SimpleNamespace(name=n) for n in self._symbols]

    def symbol_select(self, name, on):
        self.selected.append(name)
        return True

    def symbol_info(self, name):
        if name not in self._symbols:
            return None
        point = 10.0 ** -self._digits
        return SimpleNamespace(
            digits=self._digits, point=point, trade_contract_size=100.0,
            trade_tick_size=point, trade_tick_value=0.1 * (10.0 ** (3 - self._digits)),
            volume_min=0.01, volume_max=200.0, volume_step=0.01, trade_stops_level=0,
            spread=260, swap_long=self._swap_long, swap_short=23.1, swap_mode=0,
            swap_rollover3days=3, filling_mode=3)

    def symbol_info_tick(self, name):
        if not self._has_tick:
            return None
        return SimpleNamespace(time=NOW + self._offset * 3600 - self._tick_age)


# ---------------------------------------------------------------------------
# probing
# ---------------------------------------------------------------------------


def test_probe_reads_the_account_and_contract_terms():
    p = bp.probe(FakeTerminal(), "XAUUSDm")
    assert p.symbol == "XAUUSDm"
    assert p.login == 198874999
    assert p.digits == 3 and p.point == pytest.approx(0.001)
    assert p.contract_size == 100.0
    assert p.margin_mode == "netting"
    assert p.filling_modes == ["FOK", "IOC"]


def test_the_spread_gate_keeps_its_dollar_meaning_across_decimals():
    three = bp.probe(FakeTerminal(digits=3), "XAUUSDm")
    two = bp.probe(FakeTerminal(digits=2), "XAUUSDm")
    assert three.max_spread_points_for_this_broker == 350      # $0.35 at 3 decimals
    assert two.max_spread_points_for_this_broker == 35         # $0.35 at 2 decimals
    # the live constant is a 3-decimal number; on a 2-decimal broker it would
    # mean $3.50, ten times too loose, so the gate has to be rescaled
    assert bp.spread_gate_points(two, 350) == 35


def test_gold_symbols_are_found_and_dollar_pairs_come_first():
    t = FakeTerminal(symbols=("EURUSD", "GOLD", "XAUUSD.a", "XAUUSD", "XAUEUR"))
    assert bp.find_gold_symbols(t)[0] == "XAUUSD"
    assert "GOLD" in bp.find_gold_symbols(t)
    assert "EURUSD" not in bp.find_gold_symbols(t)


def test_a_configured_symbol_the_broker_does_not_have_is_flagged():
    p = bp.probe(FakeTerminal(symbols=("XAUUSD", "GOLD")), "XAUUSDm")
    assert any("not among the broker" in n for n in p.notes)


def test_no_gold_symbol_at_all_is_reported_not_crashed():
    p = bp.probe(FakeTerminal(symbols=("EURUSD",)), None)
    assert "no gold symbol found" in " ".join(p.notes)


# ---------------------------------------------------------------------------
# the server clock
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("offset", [0.0, 2.0, 3.0, -5.0, 5.5])
def test_the_server_clock_offset_is_measured_from_a_fresh_tick(offset, monkeypatch):
    monkeypatch.setattr(bp, "market_probably_open", lambda now=None: True)
    p = bp.probe(FakeTerminal(offset_hours=offset), "XAUUSDm")
    assert p.clock_offset_hours == offset


def test_a_half_stale_tick_reports_an_unknown_clock_rather_than_a_wrong_one(monkeypatch):
    monkeypatch.setattr(bp, "market_probably_open", lambda now=None: True)
    p = bp.probe(FakeTerminal(offset_hours=3.0, tick_age_sec=40 * 60), "XAUUSDm")
    assert p.clock_offset_hours is None
    assert "stale" in p.clock_source


def test_the_clock_is_not_guessed_while_the_market_is_shut(monkeypatch):
    monkeypatch.setattr(bp, "market_probably_open", lambda now=None: False)
    p = bp.probe(FakeTerminal(offset_hours=3.0), "XAUUSDm")
    assert p.clock_offset_hours is None
    assert "market closed" in p.clock_source


@pytest.mark.parametrize("when,is_open", [
    ((2026, 11, 4, 12, 0), True),     # Wednesday midday
    ((2026, 11, 7, 12, 0), False),    # Saturday
    ((2026, 11, 8, 12, 0), False),    # Sunday before the open
    ((2026, 11, 8, 23, 0), True),     # Sunday evening open
    ((2026, 11, 6, 21, 30), False),   # Friday after the close
    ((2026, 11, 4, 21, 30), False),   # Wednesday rollover break
])
def test_market_open_window(when, is_open):
    assert bp.market_probably_open(dt.datetime(*when, tzinfo=dt.timezone.utc)) is is_open


def test_no_tick_reports_an_unknown_clock(monkeypatch):
    monkeypatch.setattr(bp, "market_probably_open", lambda now=None: True)
    p = bp.probe(FakeTerminal(tick=False), "XAUUSDm")
    assert p.clock_offset_hours is None


# ---------------------------------------------------------------------------
# comparing against the validated broker
# ---------------------------------------------------------------------------


def _expected(**over):
    p = bp.probe(FakeTerminal(), "XAUUSDm")
    exp = {k: v for k, v in bp.asdict(p).items()}
    exp.update(over)
    return exp


def test_an_identical_broker_shows_no_differences():
    assert bp.compare(bp.probe(FakeTerminal(), "XAUUSDm"), _expected()) == []


def test_a_changed_symbol_decimals_or_clock_is_reported(monkeypatch):
    monkeypatch.setattr(bp, "market_probably_open", lambda now=None: True)
    exp = _expected(clock_offset_hours=0.0)
    got = bp.probe(FakeTerminal(symbols=("XAUUSD",), digits=2, offset_hours=3.0), "XAUUSD")
    diffs = " | ".join(bp.compare(got, exp))
    assert "symbol" in diffs
    assert "digits" in diffs
    assert "clock_offset_hours" in diffs


def test_a_swap_that_flips_sign_is_called_out():
    exp = _expected()
    got = bp.probe(FakeTerminal(swap_long=+12.0), "XAUUSDm")
    assert any("swap_long changed sign" in d for d in bp.compare(got, exp))


def test_an_unmeasurable_clock_is_not_reported_as_a_change():
    exp = _expected(clock_offset_hours=0.0)
    got = bp.probe(FakeTerminal(tick=False), "XAUUSDm")
    diffs = bp.compare(got, exp)
    assert any("could not be measured" in d for d in diffs)
    assert not any("now None, expected" in d for d in diffs)


def test_no_expected_profile_yet_says_so_instead_of_passing_silently():
    assert bp.compare(bp.probe(FakeTerminal(), "XAUUSDm"), {}) != []


def test_leverage_and_currency_changes_are_reported():
    # Atlas funded accounts cap MT5 leverage at 1:50 and could settle in another
    # currency; both change what a lot risks
    exp = _expected()
    got = bp.probe(FakeTerminal(leverage=50, currency="EUR"), "XAUUSDm")
    diffs = " | ".join(bp.compare(got, exp))
    assert "leverage" in diffs and "currency" in diffs


# ---------------------------------------------------------------------------
# startup plumbing
# ---------------------------------------------------------------------------


def test_startup_check_writes_a_profile_and_never_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(bp, "PROFILE_PATH", str(tmp_path / "broker_profile.json"))
    monkeypatch.setattr(bp, "EXPECTED_PATH", str(tmp_path / "missing.json"))
    profile, diffs = bp.startup_check(FakeTerminal(), "XAUUSDm")
    assert profile.symbol == "XAUUSDm"
    written = json.loads((tmp_path / "broker_profile.json").read_text(encoding="utf-8"))
    assert written["login"] == 198874999
    assert diffs                                   # no expected profile recorded


def test_startup_check_survives_a_terminal_that_throws():
    class Broken:
        def account_info(self):
            raise RuntimeError("terminal gone")

        def symbols_get(self):
            raise RuntimeError("terminal gone")

    profile, diffs = bp.startup_check(Broken(), "XAUUSDm")
    assert profile is not None or diffs


def test_save_and_load_expected_round_trip(tmp_path):
    path = str(tmp_path / "broker_expected.json")
    p = bp.probe(FakeTerminal(), "XAUUSDm")
    bp.save_expected(p, path)
    exp = bp.load_expected(path)
    assert exp["symbol"] == "XAUUSDm"
    assert bp.compare(p, exp) == []


def test_summary_is_one_readable_line():
    s = bp.summary(bp.probe(FakeTerminal(), "XAUUSDm"))
    assert "XAUUSDm" in s and "Exness" in s and "\n" not in s
