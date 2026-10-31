"""The master bar series: one loader, declared sources, no silent merges.

These tests build tiny .npy caches in a temp directory and point
`MASTER_SOURCES` at them, so nothing here touches the real 400 MB archive.
"""
import datetime as dt

from types import SimpleNamespace

import numpy as np
import pytest

from src.backtesting import master

RATE_DTYPE = np.dtype([("time", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"),
                       ("close", "<f8"), ("tick_volume", "<u8"), ("spread", "<i4"),
                       ("real_volume", "<u8")])


def utc(*a):
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())


def make(times, close=1.0):
    arr = np.zeros(len(times), dtype=RATE_DTYPE)
    arr["time"] = times
    arr["open"] = arr["high"] = arr["low"] = arr["close"] = close
    arr["tick_volume"] = 1
    return arr


def write(root, tf, arr):
    root.mkdir(parents=True, exist_ok=True)
    np.save(str(root / f"{master.SYMBOL}_{tf}.npy"), arr)


# ---------------------------------------------------------------------------


def test_later_sources_win_on_a_shared_timestamp(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    t = [utc(2026, 3, 2, 0, 0), utc(2026, 3, 2, 0, 15)]
    write(a, "M15", make(t, close=10.0))
    write(b, "M15", make(t, close=20.0))
    monkeypatch.setattr(master, "MASTER_SOURCES", (
        master.Source("old", str(a), ("M15",), 0, utc(2100, 1, 1)),
        master.Source("new", str(b), ("M15",), 0, utc(2100, 1, 1)),
    ))
    arr, prov = master._merge("M15")
    assert list(arr["time"]) == t              # deduplicated
    assert list(arr["close"]) == [20.0, 20.0]  # the later source's prices
    assert [p["source"] for p in prov] == ["old", "new"]


def test_a_source_only_contributes_inside_its_validity_window(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    cut = utc(2026, 1, 1)
    write(a, "M15", make([cut - 900, cut, cut + 900], close=10.0))
    write(b, "M15", make([cut - 900, cut, cut + 900], close=20.0))
    monkeypatch.setattr(master, "MASTER_SOURCES", (
        master.Source("archive", str(a), ("M15",), 0, cut),
        master.Source("broker", str(b), ("M15",), cut, utc(2100, 1, 1)),
    ))
    arr, _ = master._merge("M15")
    got = dict(zip(arr["time"].tolist(), arr["close"].tolist()))
    assert got[cut - 900] == 10.0              # before the cut: archive
    assert got[cut] == 20.0 and got[cut + 900] == 20.0


def test_an_eastern_european_source_is_shifted_onto_the_broker_clock(tmp_path, monkeypatch):
    root = tmp_path / "k"
    winter, summer = utc(2026, 1, 15, 12, 0), utc(2026, 7, 15, 12, 0)
    write(root, "M15", make([winter, summer]))
    monkeypatch.setattr(master, "MASTER_SOURCES", (
        master.Source("kaggle", str(root), ("M15",), 0, utc(2100, 1, 1), clock="athens"),
    ))
    arr, _ = master._merge("M15")
    # Athens is UTC+2 in winter and UTC+3 in summer, so the stamps move back by
    # different amounts -- a fixed offset would be wrong for half the year
    assert arr["time"][0] == winter - 2 * 3600
    assert arr["time"][1] == summer - 3 * 3600


def test_missing_cache_names_the_refresh_command(tmp_path, monkeypatch):
    monkeypatch.setattr(master, "MASTER_SOURCES", (
        master.Source("nowhere", str(tmp_path / "nope"), ("M15",), 0, utc(2100, 1, 1)),
    ))
    with pytest.raises(FileNotFoundError, match="data_refresh"):
        master._merge("M15")


def test_weekend_closes_are_not_counted_as_holes():
    # Friday 21:00 UTC to Sunday 22:00 UTC, then one real missing Monday candle
    fri = utc(2026, 3, 6, 21, 0)
    sun = utc(2026, 3, 8, 22, 0)
    mon = utc(2026, 3, 9, 10, 0)
    arr = make([fri, sun, mon, mon + 1800])
    gaps = master.non_weekend_gaps(arr, "M15")
    afters = [g["after"] for g in gaps]
    assert fri not in afters                   # the weekend is expected
    assert mon in afters                       # the missing Monday candle is not
    assert gaps[0]["missing_bars"] >= 1


def test_holes_are_reported_biggest_first():
    base = utc(2026, 3, 9)
    arr = make([base, base + 900, base + 900 * 10, base + 900 * 40])
    gaps = master.non_weekend_gaps(arr, "M15")
    assert [g["missing_bars"] for g in gaps] == sorted(
        [g["missing_bars"] for g in gaps], reverse=True)


def test_windows_are_declared_once_and_lookupable():
    names = [w[0] for w in master.WINDOWS]
    assert names == ["DEV", "TEST", "RECENT"]
    for name, a, b in master.WINDOWS:
        assert master.window(name) == (a, b)
        assert a < b
    with pytest.raises(KeyError):
        master.window("NOPE")


def test_the_archive_is_not_trusted_past_the_measured_divergence():
    # data_check.py 2026-11-01: from January 2026 the archive and the broker
    # disagree by more than $1 on 29% of candles, so the archive must stop before
    # it, and TEST must stop with it
    assert master.KAGGLE_END == utc(2026, 1, 1)
    assert master.window("TEST")[1] == master.KAGGLE_END
    kaggle = [s for s in master.MASTER_SOURCES if s.name == "kaggle"][0]
    assert kaggle.valid_to == master.KAGGLE_END


def test_the_holdout_starts_after_every_research_window():
    assert all(b <= master.HOLDOUT_FROM for _, _, b in master.WINDOWS)


# ---------------------------------------------------------------------------
# the holdout cannot be reached by accident
# ---------------------------------------------------------------------------


def _holdout_sources(tmp_path, monkeypatch):
    root = tmp_path / "b"
    before = master.HOLDOUT_FROM - 900
    after = master.HOLDOUT_FROM + 900
    write(root, "M15", make([before, master.HOLDOUT_FROM, after]))
    monkeypatch.setattr(master, "MASTER_SOURCES", (
        master.Source("broker", str(root), ("M15",), 0, utc(2100, 1, 1)),
    ))
    monkeypatch.setattr(master, "_CACHE", {})
    monkeypatch.setattr(master, "load_bars", lambda *a, **k: SimpleNamespace(spec="spec"))
    return before, after


def test_bars_after_the_freeze_are_cut_off_unless_asked_for(tmp_path, monkeypatch):
    before, after = _holdout_sources(tmp_path, monkeypatch)
    bars = master.load_master(("M15",))
    assert before in bars.m15["time"].tolist()
    assert master.HOLDOUT_FROM not in bars.m15["time"].tolist()
    assert after not in bars.m15["time"].tolist()
    assert bars.holdout_included is False


def test_the_holdout_is_there_when_a_study_says_it_is_judging(tmp_path, monkeypatch):
    before, after = _holdout_sources(tmp_path, monkeypatch)
    bars = master.load_master(("M15",), allow_holdout=True)
    assert after in bars.m15["time"].tolist()
    assert bars.holdout_included is True


def test_a_window_that_starts_in_the_holdout_is_refused(tmp_path, monkeypatch):
    _holdout_sources(tmp_path, monkeypatch)
    with pytest.raises(master.HoldoutError, match="judge a decision"):
        master.load_master(("M15",), start=master.HOLDOUT_FROM + 86400)


def test_asking_and_not_asking_are_cached_apart(tmp_path, monkeypatch):
    _, after = _holdout_sources(tmp_path, monkeypatch)
    plain = master.load_master(("M15",))
    judging = master.load_master(("M15",), allow_holdout=True)
    assert after not in plain.m15["time"].tolist()
    assert after in judging.m15["time"].tolist()
