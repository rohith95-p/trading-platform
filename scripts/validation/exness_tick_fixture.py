"""Replay the two frozen engineering orders on publicly archived XAUUSD quotes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

from scripts.validation.mt5_demo_tick_capture import TICK_DTYPE, validate_quotes
from scripts.validation.tick_fixture_reconciliation import START, END, compare


MEMBER = "Exness_XAUUSD_Raw_Spread_2025_01.csv"
SOURCE = "https://ticks.ex2archive.com/ticks/XAUUSD_Raw_Spread/2025/01/" + MEMBER[:-4] + ".zip"
ARCHIVE_SHA256 = "21f00528927569f18d6f0aae01e6726484e4a375e6be8a28de4e234846e45876"


def extract(archive):
    parts = []
    count = 0
    with zipfile.ZipFile(archive) as z, z.open(MEMBER) as stream:
        for frame in pd.read_csv(stream, chunksize=200_000):
            if not frame.Exness.eq("exness").all() or not frame.Symbol.eq("XAUUSD_Raw_Spread").all():
                raise ValueError("Unexpected quote feed")
            count += len(frame)
            selected = frame.loc[frame.Timestamp.str.startswith("2025-01-06 12:")]
            if selected.empty:
                continue
            times = pd.to_datetime(selected.Timestamp, utc=True).dt.as_unit("ms").astype("int64")
            quotes = np.empty(len(times), dtype=TICK_DTYPE)
            quotes["time_msc"], quotes["bid"], quotes["ask"] = times, selected.Bid, selected.Ask
            parts.append(quotes)
    if not parts:
        raise ValueError("The protocol hour has no quotes")
    ticks = np.concatenate(parts)
    validate_quotes(ticks, START * 1000, END * 1000)
    return ticks, count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    with args.archive.open("rb") as f:
        archive_sha = hashlib.file_digest(f, "sha256").hexdigest()
    if archive_sha != ARCHIVE_SHA256:
        raise ValueError("Archive differs from the frozen Exness January 2025 snapshot")
    ticks, count = extract(args.archive)
    os.environ["ULTRA_TRADE_24H"] = "1"
    os.environ["ULTRA_DISABLE_ALERTS"] = "1"
    result = compare(ticks, "Exness public XAUUSD Raw Spread historical quotes")
    result.update(source=SOURCE, archive_sha256=archive_sha, member=MEMBER, month_rows=count,
                  ticks_sha256=hashlib.sha256(ticks.tobytes()).hexdigest(),
                  repeated_milliseconds=int(np.count_nonzero(np.diff(ticks["time_msc"]) == 0)),
                  max_interquote_ms=int(np.diff(ticks["time_msc"]).max()),
                  median_spread_usd_oz=float(np.median(ticks["ask"] - ticks["bid"])),
                  verification_scope="Two order fixtures reconciled against observed broker quotes. Actual account fills and Atlas feed equivalence are unverified.")
    args.result.parent.mkdir(parents=True, exist_ok=True)
    with args.result.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(count, len(ticks), [f["comparison"] for f in result["fixtures"]])


if __name__ == "__main__":
    main()
