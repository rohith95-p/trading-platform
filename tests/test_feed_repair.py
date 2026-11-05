"""A stalled candle feed must repair itself, and be impossible to miss.

The failure these cover happened on 2026-11-03. The MT5 terminal served a live
tick stream while its bar history sat hours behind; `copy_rates_from_pos` only
returns what is already cached, so the bot read stale candles, failed its own
liveness check, and skipped every signal evaluation. A tradeable Asian Range
Filtered sell was never placed, and nothing said so -- the process, the
heartbeat, the MT5 connection and `vps_check.ps1` all reported healthy.
"""
import datetime as dt
from types import SimpleNamespace

import numpy as np
import pytest

from src.core import data_fetcher as df

RATE_DTYPE = np.dtype([("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"),
                       ("close", "<f8"), ("tick_volume", "<u8"), ("spread", "<i4"),
                       ("real_volume", "<u8")])


def bars(newest_age_sec, count=250, step=900):
    """`count` bars ending `newest_age_sec` seconds ago."""
    now = int(dt.datetime.now(dt.timezone.utc).timestamp())
    end = now - int(newest_age_sec)
    arr = np.zeros(count, dtype=RATE_DTYPE)
    arr["time"] = [end - step * (count - 1 - i) for i in range(count)]
    for k in ("open", "high", "low", "close"):
        arr[k] = 4000.0
    arr["tick_volume"] = 1
    return arr


class FakeMt5:
    """from_pos serves a cached window; range triggers a download, as the real one does."""

    TIMEFRAME_M1, TIMEFRAME_M5, TIMEFRAME_M15 = 60, 300, 900
    TIMEFRAME_H1, TIMEFRAME_D1 = 3600, 86400

    def __init__(self, cached_age, server_age=30.0, range_works=True, count=250):
        self.cached = bars(cached_age, count=count)
        self.fresh = bars(server_age, count=count + 60)
        self.range_works = range_works
        self.from_pos_calls = 0
        self.range_calls = 0

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        self.from_pos_calls += 1
        return self.cached[-count:]

    def copy_rates_range(self, symbol, timeframe, a, b):
        self.range_calls += 1
        return self.fresh if self.range_works else None


@pytest.fixture
def fetcher(monkeypatch):
    monkeypatch.setattr(df.DataFetcher, "__init__",
                        lambda self, symbol="XAUUSDm", own_magics=None: (
                            setattr(self, "symbol", symbol),
                            setattr(self, "own_magics", frozenset()),
                            setattr(self, "feed_repairs", 0))[0] and None)
    return df.DataFetcher("XAUUSDm")


# ---------------------------------------------------------------------------


def test_fresh_bars_are_returned_without_a_second_call(fetcher, monkeypatch):
    fake = FakeMt5(cached_age=60)
    monkeypatch.setattr(df, "mt5", fake)
    got = fetcher.get_m15_rates(250)
    assert got is not None and len(got) == 250
    assert fake.range_calls == 0          # nothing to repair
    assert fetcher.feed_repairs == 0


def test_stale_bars_trigger_a_range_request_that_returns_current_ones(fetcher, monkeypatch):
    # 50 hours behind: exactly what the terminal served on 2026-11-04
    fake = FakeMt5(cached_age=50 * 3600)
    monkeypatch.setattr(df, "mt5", fake)
    got = fetcher.get_m15_rates(250)
    assert fake.range_calls == 1
    assert got is not None and len(got) == 250
    age = dt.datetime.now(dt.timezone.utc).timestamp() - float(got[-1]["time"])
    assert age < df.DataFetcher.STALE_AFTER_SEC
    assert fetcher.feed_repairs == 1


def test_a_feed_that_cannot_be_repaired_still_returns_what_there_is(fetcher, monkeypatch):
    """The liveness check is what refuses to trade; this must not crash first."""
    fake = FakeMt5(cached_age=50 * 3600, range_works=False)
    monkeypatch.setattr(df, "mt5", fake)
    got = fetcher.get_m15_rates(250)
    assert fake.range_calls == 1
    assert got is not None               # the stale bars, for the liveness check to reject
    assert fetcher.feed_repairs == 0


def test_no_bars_at_all_is_a_repair_attempt_then_none(fetcher, monkeypatch):
    class Empty(FakeMt5):
        def copy_rates_from_pos(self, *a):
            return None

    fake = Empty(cached_age=0, range_works=False)
    monkeypatch.setattr(df, "mt5", fake)
    assert fetcher.get_m15_rates(250) is None
    assert fake.range_calls == 1


@pytest.mark.parametrize("age,repaired", [(0, False), (24 * 60, False), (26 * 60, True)])
def test_the_staleness_threshold_is_one_candle_plus_slack(fetcher, monkeypatch, age, repaired):
    fake = FakeMt5(cached_age=age)
    monkeypatch.setattr(df, "mt5", fake)
    fetcher.get_m15_rates(250)
    assert (fake.range_calls == 1) is repaired


def test_every_timeframe_the_bot_uses_can_be_repaired():
    for tf in (60, 300, 900, 86400):
        assert tf in df.DataFetcher._REFETCH_DAYS


def test_a_timeframe_with_no_refetch_window_is_left_alone(fetcher, monkeypatch):
    fake = FakeMt5(cached_age=50 * 3600)
    monkeypatch.setattr(df, "mt5", fake)
    assert fetcher._refetch(12345, 250) is None


# ---------------------------------------------------------------------------
# the symptom alarm: an allowed signal that produced no order
# ---------------------------------------------------------------------------


def test_a_signal_that_places_no_order_raises_a_critical_alert(monkeypatch):
    from src.core import order_flow

    sent = []
    monkeypatch.setattr(order_flow, "_SILENT_MISSES", set())
    monkeypatch.setattr("src.core.alerts.send",
                        lambda m, severity=None, **k: sent.append((m, severity)))
    strat = SimpleNamespace(name="ASIAN_RANGE_FILTERED_V6")
    sig = SimpleNamespace(direction_str="SELL", is_buy=False)
    order_flow._report_silent_miss(strat, sig, 1762153200, "ASIA")
    assert len(sent) == 1
    msg, sev = sent[0]
    assert "missed" in msg.lower() and "ASIAN_RANGE_FILTERED_V6" in msg
    assert sev == "CRITICAL"


def test_the_same_candle_only_alerts_once(monkeypatch):
    from src.core import order_flow

    sent = []
    monkeypatch.setattr(order_flow, "_SILENT_MISSES", set())
    monkeypatch.setattr("src.core.alerts.send",
                        lambda m, severity=None, **k: sent.append(m))
    strat = SimpleNamespace(name="LONDON_MOMENTUM_TIGHT_V6")
    sig = SimpleNamespace(direction_str="BUY", is_buy=True)
    for _ in range(5):
        order_flow._report_silent_miss(strat, sig, 1762153200, "LONDON")
    assert len(sent) == 1


def test_old_candles_are_forgotten_so_the_set_cannot_grow_forever(monkeypatch):
    from src.core import order_flow

    monkeypatch.setattr(order_flow, "_SILENT_MISSES", set())
    monkeypatch.setattr("src.core.alerts.send", lambda *a, **k: None)
    strat = SimpleNamespace(name="NY_SESSION_REVERSAL_V6")
    sig = SimpleNamespace(direction_str="SELL", is_buy=False)
    base = 1762153200
    order_flow._report_silent_miss(strat, sig, base, "NY")
    order_flow._report_silent_miss(strat, sig, base + 2 * 86400, "NY")
    assert all(k[1] > base for k in order_flow._SILENT_MISSES)
