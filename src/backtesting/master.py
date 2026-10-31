"""The one place that says where bars come from.

Before this module there were three cached data roots (`research/data`,
`research/data_2026-10-30`, `research/data_live_parity`) plus a 22-year Kaggle
archive, and every research script merged them itself -- `merged_bars()` in one
study, a different `bars()` in the audit runner. Two scripts could silently test
two different histories and nobody would see it.

A master series is built here, once, from declared sources in priority order:

    kaggle  research/data/kaggle_22yr   third-party archive, Eastern European
                                        clock, shifted to the broker's UTC;
                                        trusted only up to KAGGLE_END, after
                                        which it diverges from the broker feed
    broker  research/data               the bot's own terminal (Exness), M15 back
                                        to 2022, M1 only as deep as the
                                        terminal's 100k-bar cap allows
    topup   research/data_2026-10-30    a later pull of the same terminal, used
                                        for whatever is newer than `broker`
    broker_ research/data/              every weekly pull, accumulated and never
    archive broker_archive              truncated (scripts/data_refresh.py); it
                                        wins wherever it has bars and grows a
                                        week at a time, until the third-party
                                        archive is no longer needed at all

Later sources win on overlapping timestamps, because they are closer to what the
bot actually trades. Only the archive carries a validity cut-off (KAGGLE_END);
the broker sources are simply used wherever they have bars. One consequence is
visible and deliberate: before mid-2026 the M15 candles are the broker's own
while the minute bars underneath them come from the archive, and the accumulating
broker archive is what removes that split, a week at a time. `load_master()` is the only loader research code should
call; `scripts/data_refresh.py` adds new broker bars, and
`scripts/validation/data_check.py` reports coverage, holes and how well the
archive agrees with the broker.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import numpy as np

from src.backtesting.data import TIMEFRAME_SECONDS, BarSet, SymbolSpec, load_bars

SYMBOL = "XAUUSDm"
DATA_ROOT = os.path.join("research", "data")
KAGGLE_ROOT = os.path.join(DATA_ROOT, "kaggle_22yr")
TOPUP_ROOT = os.path.join("research", "data_2026-10-30")
ARCHIVE_ROOT = os.path.join(DATA_ROOT, "broker_archive")


def _utc(*a: int) -> int:
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())


# How far the archive may be trusted. Measured against the broker's own M15
# candles over the 81,232 candles both cover (scripts/validation/data_check.py,
# 2026-11-01): 2022-2025 the two agree to a median 5 cents, 95th 20 cents, and
# differ by more than $1 on 0.0-0.15% of candles. From January 2026 the archive
# breaks away -- median 53 cents, 29% of candles more than $1 apart, worst $11 in
# January and $53 in February. The earlier boundary of 2026-02-18 therefore put
# ~7 weeks of disagreeing prices inside the TEST window. Cut at New Year 2026.
KAGGLE_END = _utc(2026, 1, 1)
KAGGLE_END_PREVIOUS = _utc(2026, 2, 18)   # what studies before 2026-11-01 used

# The broker's M1 cache has a hole here (terminal history was never downloaded
# for that stretch); trades inside it are excluded from every study.
M1_HOLE = (_utc(2025, 9, 14), _utc(2025, 10, 15))

# Research windows. DEV is where settings may be chosen, TEST confirms them,
# RECENT is the most recent fully-covered span. Data from HOLDOUT_FROM onward
# only ever judges a decision -- see research/DECISIONS.md.
WINDOWS: List[Tuple[str, int, int]] = [
    ("DEV", _utc(2022, 8, 1), _utc(2024, 6, 1)),
    ("TEST", _utc(2024, 6, 1), KAGGLE_END),
    ("RECENT", _utc(2026, 7, 6), _utc(2026, 10, 30)),
]
HOLDOUT_FROM = _utc(2026, 11, 1)


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Source:
    name: str
    root: str
    timeframes: Tuple[str, ...]
    valid_from: int
    valid_to: int
    clock: str = "utc"          # "utc" or "athens" (Eastern European, DST-aware)
    note: str = ""

    def span_for(self, a: int, b: int) -> Optional[Tuple[int, int]]:
        """The part of [a, b) this source is allowed to supply, or None."""
        lo, hi = max(a, self.valid_from), min(b, self.valid_to)
        return (lo, hi) if hi > lo else None


MASTER_SOURCES: Tuple[Source, ...] = (
    Source("kaggle", KAGGLE_ROOT, ("M1", "M15", "D1"), _utc(2004, 1, 1), KAGGLE_END,
           clock="athens",
           note="22-year third-party archive; diverges from the broker after Feb 2026"),
    # The broker's own feed is what the bot trades, so it wins wherever it has
    # bars -- which for M15 is 2022 onward and for M1 only the last few months,
    # because the terminal hands out at most 100,000 bars per timeframe. The
    # archive fills in behind it, nothing more.
    Source("broker", DATA_ROOT, ("M1", "M5", "M15", "H1", "H4", "D1"),
           _utc(2004, 1, 1), _utc(2100, 1, 1),
           note="the bot's own Exness terminal"),
    Source("topup", TOPUP_ROOT, ("M1", "M15", "D1"), _utc(2004, 1, 1), _utc(2100, 1, 1),
           note="later pull of the same terminal"),
    # Grown one weekly pull at a time by scripts/data_refresh.py, so it reaches
    # further back than the terminal's own 100k-bar window and, in time, replaces
    # the archive entirely. Listed last, so it wins wherever it has bars.
    Source("broker_archive", ARCHIVE_ROOT, ("M1", "M5", "M15", "H1", "H4", "D1"),
           _utc(2004, 1, 1), _utc(2100, 1, 1),
           note="accumulating broker pulls (scripts/data_refresh.py)"),
)


def _athens_to_utc(arr: np.ndarray) -> np.ndarray:
    """Shift Eastern European bar stamps onto the broker's UTC clock, DST-aware."""
    days = arr["time"].astype(np.int64) // 86400
    athens = ZoneInfo("Europe/Athens")
    off = {}
    for d in np.unique(days):
        noon = dt.datetime.fromtimestamp(int(d) * 86400 + 43200, dt.timezone.utc)
        off[int(d)] = int(noon.astimezone(athens).utcoffset().total_seconds())
    out = arr.copy()
    out["time"] = arr["time"] - np.array([off[int(d)] for d in days], dtype=arr["time"].dtype)
    return out


def read_source(src: Source, timeframe: str) -> Optional[np.ndarray]:
    """Raw bars from one source, on the broker's clock. None if not cached."""
    if timeframe not in src.timeframes:
        return None
    stem = os.path.join(src.root, f"{SYMBOL}_{timeframe}")
    if not os.path.exists(stem + ".npy"):
        return None
    arr = np.asarray(np.load(stem + ".npy", mmap_mode="r"))
    if src.clock == "athens":
        arr = _athens_to_utc(arr)
    return arr


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


def _merge(timeframe: str, start: Optional[int] = None,
           end: Optional[int] = None) -> Tuple[np.ndarray, List[Dict[str, object]]]:
    """One series per timeframe, later sources winning on shared timestamps.

    `start`/`end` keep only the bars a run needs. The minute archive is 6.8
    million bars and four backtest workers cannot each hold all of it, so a
    windowed load is the difference between running and an out-of-memory crash.
    """
    pieces: List[np.ndarray] = []
    provenance: List[Dict[str, object]] = []
    dtype = None
    for src in MASTER_SOURCES:
        arr = read_source(src, timeframe)
        if arr is None or not len(arr):
            continue
        t = arr["time"].astype(np.int64)
        lo = max(src.valid_from, start) if start is not None else src.valid_from
        hi = min(src.valid_to, end) if end is not None else src.valid_to
        sel = arr[(t >= lo) & (t < hi)]
        if not len(sel):
            continue
        if dtype is None:
            dtype = sel.dtype
        pieces.append(sel.astype(dtype))
        provenance.append(dict(source=src.name, timeframe=timeframe, bars=int(len(sel)),
                               first=int(sel["time"][0]), last=int(sel["time"][-1]),
                               clock=src.clock, note=src.note))
    if not pieces:
        raise FileNotFoundError(
            f"no cached {timeframe} bars for {SYMBOL} in any declared source. "
            f"Run: python -I scripts/data_refresh.py"
        )
    joined = np.concatenate(pieces)
    # stable sort keeps source order inside one timestamp; keeping the LAST of
    # each run then means the later (more trusted) source wins
    joined = joined[np.argsort(joined["time"], kind="stable")]
    t = joined["time"].astype(np.int64)
    keep = np.r_[t[1:] != t[:-1], True]
    return joined[keep], provenance


_CACHE: Dict[Tuple[Any, ...], BarSet] = {}

# Bars a run needs before its first trading candle: the engine hands strategies
# up to 7,500 M15 bars of history, and the daily gate wants 50 daily bars.
WARMUP_SEC = 200 * 86400


class HoldoutError(RuntimeError):
    """Something asked for bars from the holdout without saying so."""


def load_master(timeframes: Sequence[str] = ("M15", "M1", "D1"),
                start: Optional[int] = None, end: Optional[int] = None,
                use_cache: bool = True, allow_holdout: bool = False) -> BarSet:
    """The merged master series, optionally narrowed to one run's window.

    Pass `start`/`end` whenever the whole history is not needed: the minute
    archive alone is 390 MB, and loading it four times over in parallel workers
    runs the machine out of memory. `start` is padded by WARMUP_SEC so the engine
    still has its history and daily bars.

    Bars from HOLDOUT_FROM onward are cut off unless `allow_holdout=True`. That
    is the rule in research/DECISIONS.md made mechanical: data after the freeze
    may judge a decision, never choose one, and a script cannot reach it by
    accident -- it has to ask.
    """
    key = (tuple(timeframes), start, end, bool(allow_holdout))
    if use_cache and key in _CACHE:
        return _CACHE[key]
    lo = start - WARMUP_SEC if start is not None else None
    hi = end
    if not allow_holdout:
        if start is not None and start >= HOLDOUT_FROM:
            raise HoldoutError(
                f"window starts inside the holdout "
                f"({dt.datetime.fromtimestamp(HOLDOUT_FROM, dt.timezone.utc):%Y-%m-%d} onward). "
                f"Data from then on may judge a decision, never choose one: pass "
                f"allow_holdout=True and say so in research/DECISIONS.md.")
        hi = HOLDOUT_FROM if end is None else min(end, HOLDOUT_FROM)
    series: Dict[str, np.ndarray] = {}
    prov: List[Dict[str, object]] = []
    for tf in timeframes:
        arr, p = _merge(tf, lo, hi)
        series[tf] = arr
        prov.extend(p)
    out = BarSet(symbol=SYMBOL, m15=series.get("M15"), m5=series.get("M5"),
                 m1=series.get("M1"), d1=series.get("D1"), h4=series.get("H4"),
                 spec=master_spec(), manifests={})
    setattr(out, "provenance", prov)
    setattr(out, "holdout_included", bool(allow_holdout))
    if use_cache:
        _CACHE[key] = out
    return out


def master_spec() -> SymbolSpec:
    """Contract terms come from the broker cache -- the archive has no spec."""
    return load_bars(SYMBOL, ("M15",), data_root=DATA_ROOT).spec


# ---------------------------------------------------------------------------
# reporting helpers
# ---------------------------------------------------------------------------


def non_weekend_gaps(arr: np.ndarray, timeframe: str) -> List[Dict[str, int]]:
    """Holes bigger than one bar that are not a weekend close, biggest first."""
    step = TIMEFRAME_SECONDS[timeframe]
    t = arr["time"].astype(np.int64)
    if len(t) < 2:
        return []
    d = np.diff(t)
    out = []
    for i in np.nonzero(d > step)[0]:
        after = int(t[i])
        wd = dt.datetime.fromtimestamp(after, dt.timezone.utc).weekday()
        if wd >= 4 and d[i] > 12 * 3600:          # Friday close into Sunday open
            continue
        out.append(dict(after=after, missing_bars=int(d[i] // step) - 1, seconds=int(d[i])))
    return sorted(out, key=lambda g: -g["missing_bars"])


def window(name: str) -> Tuple[int, int]:
    for n, a, b in WINDOWS:
        if n == name:
            return a, b
    raise KeyError(name)
