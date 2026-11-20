"""Prepare the missing 2022 ticks and pre-2022 warmup for the MT5 custom symbol."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.four_atlas_archive import ticks_for_month


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    for month in pd.period_range("2021-09", "2022-10", freq="M"):
        q = ticks_for_month(month.year, month.month)
        minute = q["ms"] // 60000
        first = np.r_[0, np.flatnonzero(np.diff(minute)) + 1]
        last = np.r_[first[1:] - 1, len(q) - 1]
        rates = np.empty(len(first), dtype=[
            ("ts", "<i8"), ("open", "<f8"), ("high", "<f8"), ("low", "<f8"),
            ("close", "<f8"), ("volume", "<i8"), ("spread", "<i8"),
        ])
        rates["ts"] = minute[first] * 60
        rates["open"] = q["bid"][first]
        rates["high"] = np.maximum.reduceat(q["bid"], first)
        rates["low"] = np.minimum.reduceat(q["bid"], first)
        rates["close"] = q["bid"][last]
        rates["volume"] = last - first + 1
        rates["spread"] = np.rint(np.minimum.reduceat(q["ask"] - q["bid"], first) * 1000)
        rates.tofile(args.directory / f"{month}.rates")
        if month.year == 2022:
            q.tofile(args.directory / f"{month}.ticks")
        print(month, len(rates), len(q), flush=True)


if __name__ == "__main__":
    main()
