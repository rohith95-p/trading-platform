"""Weekly price-data refresh: pull the terminal's bars and grow one archive.

The MT5 terminal only ever hands out its newest ~100,000 bars per timeframe.
At M1 that is about fourteen weeks, which is why the broker-native minute history
stops in July 2026 and the DEV/TEST windows have to lean on a third-party
archive. A single pull can never fix that; an accumulating one can.

Every run appends whatever the terminal currently has into

    research/data/broker_archive/XAUUSDm_<TF>.npy   (+ .manifest.json)

keeping the newest version of each bar and never truncating. Run it once a week
and the broker-native M1 history grows a week at a time, so in time every window
is the bot's own feed rather than someone else's file.

    python -I scripts/data_refresh.py                    # M1, M15, D1
    python -I scripts/data_refresh.py --timeframes M1 M5 M15 H1 H4 D1
    python -I scripts/data_refresh.py --dry-run          # report, write nothing

Safe to run while the bot trades: it only reads history. It needs a terminal on
this machine, so on the VPS run it there, or run it on the PC against the same
broker.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from src.backtesting.data import TIMEFRAME_SECONDS, SymbolSpec  # noqa: E402
from src.backtesting.master import non_weekend_gaps  # noqa: E402

SYMBOL = os.environ.get("ULTRA_SYMBOL", "XAUUSDm")
ARCHIVE = os.path.join("research", "data", "broker_archive")
MAX_PER_CALL = 90_000


def _utc(ts) -> str:
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def _hash(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def pull(mt5, symbol: str, timeframe: str) -> np.ndarray:
    """Everything the terminal will give us for this timeframe, newest first."""
    tf = getattr(mt5, f"TIMEFRAME_{timeframe}")
    frames, pos = [], 0
    while True:
        got = mt5.copy_rates_from_pos(symbol, tf, pos, MAX_PER_CALL)
        if got is None or len(got) == 0:
            break
        frames.append(got)
        pos += len(got)
        if len(got) < MAX_PER_CALL:
            break
    if not frames:
        raise RuntimeError(
            f"the terminal returned no {timeframe} bars for {symbol}. Select the symbol in "
            f"Market Watch and let it download history (Tools > Options > Charts > "
            f"'Max bars in chart: Unlimited')."
        )
    out = np.concatenate(frames)
    return out[np.argsort(out["time"], kind="stable")]


def merge_into_archive(timeframe: str, fresh: np.ndarray, spec: SymbolSpec,
                       server: str, dry_run: bool = False) -> dict:
    """Append `fresh` to the archive, newest version of each bar winning."""
    os.makedirs(ARCHIVE, exist_ok=True)
    stem = os.path.join(ARCHIVE, f"{SYMBOL}_{timeframe}")
    before = 0
    if os.path.exists(stem + ".npy"):
        existing = np.load(stem + ".npy")
        before = len(existing)
        joined = np.concatenate([existing, fresh.astype(existing.dtype)])
    else:
        joined = fresh.copy()
    # stable sort then keep the LAST of each timestamp run: `fresh` is appended
    # second, so a bar the broker has since revised replaces the stored one
    joined = joined[np.argsort(joined["time"], kind="stable")]
    t = joined["time"].astype(np.int64)
    joined = joined[np.r_[t[1:] != t[:-1], True]]

    gaps = non_weekend_gaps(joined, timeframe)
    info = dict(
        timeframe=timeframe, bars_before=before, bars_after=int(len(joined)),
        added=int(len(joined) - before),
        first=_utc(joined["time"][0]), last=_utc(joined["time"][-1]),
        non_weekend_gaps=len(gaps),
        missing_bars=int(sum(g["missing_bars"] for g in gaps)),
        worst_gap=(dict(after=_utc(gaps[0]["after"]), missing_bars=gaps[0]["missing_bars"])
                   if gaps else None),
    )
    if dry_run:
        return info

    manifest = dict(
        symbol=SYMBOL, timeframe=timeframe, bars=int(len(joined)),
        first_time=_utc(joined["time"][0]), last_time=_utc(joined["time"][-1]),
        sha256=_hash(joined), server=server,
        downloaded_utc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        spec=spec.__dict__ if hasattr(spec, "__dict__") else dict(spec._asdict()),
        gaps=gaps[:200], zero_volume_bars=int((joined["tick_volume"] == 0).sum()),
        notes=("Accumulating broker archive: grown by scripts/data_refresh.py, one terminal "
               "pull at a time. Never truncated, so it reaches further back than the "
               "terminal's own 100k-bar window."),
    )
    np.save(stem + ".npy", joined)
    with open(stem + ".manifest.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    info["sha256"] = manifest["sha256"][:12]
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timeframes", nargs="+", default=["M1", "M15", "D1"],
                    choices=sorted(TIMEFRAME_SECONDS))
    ap.add_argument("--symbol", default=SYMBOL)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import MetaTrader5 as mt5

    if not mt5.initialize():
        print(f"MT5 initialize() failed: {mt5.last_error()}", file=sys.stderr)
        print("Open the MetaTrader 5 terminal on this machine and try again.", file=sys.stderr)
        return 1
    try:
        mt5.symbol_select(args.symbol, True)
        spec = SymbolSpec.from_terminal(args.symbol)
        acct = mt5.account_info()
        server = getattr(acct, "server", "unknown") if acct else "unknown"
        print(f"terminal: {server}  symbol: {args.symbol}  digits: {spec.digits}")
        rows = []
        for tf in args.timeframes:
            fresh = pull(mt5, args.symbol, tf)
            print(f"  {tf:4s} terminal has {len(fresh):>9,d} bars "
                  f"{_utc(fresh['time'][0])} -> {_utc(fresh['time'][-1])}")
            rows.append(merge_into_archive(tf, fresh, spec, server, args.dry_run))
    finally:
        mt5.shutdown()

    print(f"\narchive: {ARCHIVE}{'  (dry run, nothing written)' if args.dry_run else ''}")
    for r in rows:
        print(f"  {r['timeframe']:4s} {r['bars_before']:>9,d} -> {r['bars_after']:>9,d} bars "
              f"(+{r['added']:,d})  {r['first']} -> {r['last']}  "
              f"holes {r['non_weekend_gaps']} ({r['missing_bars']:,d} bars)")
    print("\nNext: python -I scripts/validation/data_check.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
