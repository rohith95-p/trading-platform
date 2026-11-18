"""Broker-native market data acquisition and provenance.

Every prior backtest in this project used Yahoo `GC=F` (COMEX futures) capped at
60 days. The bot trades the Exness `XAUUSDm` spot CFD. This module pulls bars
from the same MT5 terminal the bot trades through, so the research data and the
production data are the same series.

Two things are non-negotiable here:

1. Every cached dataset carries a manifest with a content hash, so a backtest
   result can always be traced to the exact bytes it was computed from.
2. Nothing silently pads, interpolates, or forward-fills. Missing bars stay
   missing and are reported, because a gap the simulator cannot see is a gap it
   will happily trade through.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

# MT5 refuses counts at or above ~100k in a single call, so pages stay well under.
_MAX_BARS_PER_CALL = 90_000

DATA_ROOT = os.path.join("research", "data")

TIMEFRAME_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}


def _mt5():
    import MetaTrader5 as mt5  # imported lazily so tests need no terminal

    return mt5


def _tf_const(timeframe: str) -> int:
    mt5 = _mt5()
    try:
        return getattr(mt5, f"TIMEFRAME_{timeframe}")
    except AttributeError as exc:  # pragma: no cover - guarded by callers
        raise ValueError(f"Unknown timeframe {timeframe!r}") from exc


# ---------------------------------------------------------------------------
# Symbol specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolSpec:
    """Broker contract terms. These drive sizing and cost, so they are pinned
    into every manifest rather than hardcoded anywhere in the engine."""

    symbol: str
    digits: int
    point: float
    trade_tick_size: float
    trade_tick_value: float
    volume_min: float
    volume_max: float
    volume_step: float
    contract_size: float

    @property
    def value_per_price_unit_per_lot(self) -> float:
        """Account currency gained per 1.0 price unit per 1.0 lot."""
        return self.trade_tick_value / self.trade_tick_size

    @classmethod
    def from_terminal(cls, symbol: str) -> "SymbolSpec":
        mt5 = _mt5()
        info = mt5.symbol_info(symbol)
        if info is None:
            mt5.symbol_select(symbol, True)
            info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"symbol_info({symbol!r}) returned None")
        return cls(
            symbol=symbol,
            digits=int(info.digits),
            point=float(info.point),
            trade_tick_size=float(info.trade_tick_size),
            trade_tick_value=float(info.trade_tick_value),
            volume_min=float(info.volume_min),
            volume_max=float(info.volume_max),
            volume_step=float(info.volume_step),
            contract_size=float(info.trade_contract_size),
        )


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@dataclass
class DataManifest:
    """Provenance record for one cached bar series."""

    symbol: str
    timeframe: str
    bars: int
    first_time: str
    last_time: str
    sha256: str
    server: str
    downloaded_utc: str
    spec: Dict[str, Any]
    gaps: List[Dict[str, Any]] = field(default_factory=list)
    zero_volume_bars: int = 0
    notes: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def _hash_rates(rates: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(rates).tobytes()).hexdigest()


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def _paged_fetch(symbol: str, timeframe: str, start: datetime, end: datetime) -> np.ndarray:
    """Page backwards through history until the terminal stops giving new bars.

    `copy_rates_range` fails on wide intraday windows, so the range is walked in
    chunks sized to stay under the per-call bar limit.
    """
    mt5 = _mt5()
    tf = _tf_const(timeframe)
    step_sec = TIMEFRAME_SECONDS[timeframe]
    # Chunk span chosen so a fully-populated chunk stays under the call limit.
    chunk = timedelta(seconds=step_sec * (_MAX_BARS_PER_CALL // 2))

    frames: List[np.ndarray] = []
    cursor = end
    while cursor > start:
        window_start = max(start, cursor - chunk)
        got = mt5.copy_rates_range(symbol, tf, window_start, cursor)
        if got is None or len(got) == 0:
            # No data in this window. Keep walking back; older history may exist
            # after a market-closed stretch, but stop once we run past `start`.
            log.debug("no bars for %s %s in %s..%s", symbol, timeframe, window_start, cursor)
            if window_start <= start:
                break
            cursor = window_start
            continue
        frames.append(got)
        oldest = int(got[0]["time"])
        new_cursor = datetime.fromtimestamp(oldest, tz=timezone.utc) - timedelta(seconds=step_sec)
        if new_cursor >= cursor:  # no forward progress; terminal is exhausted
            break
        cursor = new_cursor

    if not frames:
        raise RuntimeError(
            f"No {timeframe} history for {symbol}. Is the symbol selected in Market Watch "
            f"and the history downloaded in the terminal?"
        )

    rates = np.concatenate(frames)
    # Pages overlap at boundaries; dedupe on bar open time.
    _, keep = np.unique(rates["time"], return_index=True)
    rates = rates[np.sort(keep)]
    rates = rates[np.argsort(rates["time"])]
    return rates


def _find_gaps(rates: np.ndarray, timeframe: str) -> List[Dict[str, Any]]:
    """Report inter-bar gaps larger than one bar.

    Weekend closes are expected and dominate the list, so they are labelled
    rather than filtered -- the engine needs to know a gap is a weekend so it can
    decline to trade across it.
    """
    step = TIMEFRAME_SECONDS[timeframe]
    t = rates["time"].astype(np.int64)
    if len(t) < 2:
        return []
    deltas = np.diff(t)
    idx = np.nonzero(deltas > step)[0]
    gaps: List[Dict[str, Any]] = []
    for i in idx:
        start_dt = datetime.fromtimestamp(int(t[i]), tz=timezone.utc)
        missing = int(deltas[i] // step) - 1
        gaps.append(
            {
                "after_utc": start_dt.strftime("%Y-%m-%d %H:%M"),
                "missing_bars": missing,
                "seconds": int(deltas[i]),
                "weekend": bool(start_dt.weekday() >= 4 and deltas[i] > 12 * 3600),
            }
        )
    return gaps


def fetch_and_cache(
    symbol: str,
    timeframe: str,
    start: datetime,
    end: Optional[datetime] = None,
    data_root: str = DATA_ROOT,
) -> Tuple[np.ndarray, DataManifest]:
    """Download `symbol`/`timeframe` bars and write them to the cache with a manifest."""
    mt5 = _mt5()
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize() failed: {mt5.last_error()}")
    try:
        mt5.symbol_select(symbol, True)
        spec = SymbolSpec.from_terminal(symbol)
        account = mt5.account_info()
        server = getattr(account, "server", "unknown") if account else "unknown"

        end = end or datetime.now(timezone.utc)
        rates = _paged_fetch(symbol, timeframe, start, end)

        manifest = DataManifest(
            symbol=symbol,
            timeframe=timeframe,
            bars=int(len(rates)),
            first_time=datetime.fromtimestamp(int(rates[0]["time"]), tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            last_time=datetime.fromtimestamp(int(rates[-1]["time"]), tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            sha256=_hash_rates(rates),
            server=server,
            downloaded_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            spec=asdict(spec),
            gaps=_find_gaps(rates, timeframe),
            zero_volume_bars=int((rates["tick_volume"] == 0).sum()),
            notes="Bar timestamps are broker server time as delivered by MT5.",
        )
    finally:
        mt5.shutdown()

    os.makedirs(data_root, exist_ok=True)
    stem = os.path.join(data_root, f"{symbol}_{timeframe}")
    np.save(stem + ".npy", rates)
    with open(stem + ".manifest.json", "w", encoding="utf-8") as fh:
        fh.write(manifest.to_json())

    log.info(
        "cached %s %s: %d bars %s..%s sha=%s",
        symbol,
        timeframe,
        manifest.bars,
        manifest.first_time,
        manifest.last_time,
        manifest.sha256[:12],
    )
    return rates, manifest


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


@dataclass
class BarSet:
    """Aligned multi-timeframe bars for one symbol, with provenance attached."""

    symbol: str
    m15: np.ndarray
    m5: Optional[np.ndarray]
    m1: Optional[np.ndarray]
    d1: Optional[np.ndarray]
    spec: SymbolSpec
    manifests: Dict[str, DataManifest]
    h4: Optional[np.ndarray] = None

    def hash_key(self) -> str:
        """Combined hash of every series backing this set."""
        digest = hashlib.sha256(json.dumps(asdict(self.spec), sort_keys=True).encode())
        for name in ("m1", "m5", "m15", "h4", "d1"):
            series = getattr(self, name)
            if series is not None:
                digest.update(repr((name, series.shape, series.dtype.descr)).encode())
                digest.update(np.ascontiguousarray(series).view(np.uint8))
        return digest.hexdigest()[:16]


def load_bars(
    symbol: str,
    timeframes: Tuple[str, ...] = ("M15", "M5", "M1", "D1"),
    data_root: str = DATA_ROOT,
) -> BarSet:
    """Load cached bars. Raises if the cache is missing -- never silently refetches,
    because a silent refetch would change results without changing the manifest."""
    series: Dict[str, np.ndarray] = {}
    manifests: Dict[str, DataManifest] = {}
    spec: Optional[SymbolSpec] = None

    for tf in timeframes:
        stem = os.path.join(data_root, f"{symbol}_{tf}")
        npy, mfj = stem + ".npy", stem + ".manifest.json"
        if not (os.path.exists(npy) and os.path.exists(mfj)):
            if tf == "M15":
                raise FileNotFoundError(
                    f"No cached M15 data for {symbol}. Run: python -m scripts.fetch_history"
                )
            log.warning("no cached %s for %s; continuing without it", tf, symbol)
            continue
        arr = np.load(npy)
        with open(mfj, encoding="utf-8") as fh:
            mf = DataManifest(**json.load(fh))
        actual = _hash_rates(arr)
        if actual != mf.sha256:
            raise RuntimeError(
                f"{symbol} {tf}: cache hash mismatch (manifest {mf.sha256[:12]}, "
                f"file {actual[:12]}). The cache was modified outside this pipeline."
            )
        series[tf] = arr
        manifests[tf] = mf
        if spec is None:
            spec = SymbolSpec(**mf.spec)

    assert spec is not None
    return BarSet(
        symbol=symbol,
        m15=series["M15"],
        m5=series.get("M5"),
        m1=series.get("M1"),
        d1=series.get("D1"),
        h4=series.get("H4"),
        spec=spec,
        manifests=manifests,
    )
