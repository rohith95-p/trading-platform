"""Run the frozen Luna-free portfolios and standalone legs in 2022–2024."""
import argparse
from pathlib import Path
import subprocess
import time

import pandas as pd

from scripts.research import guarded_retained_native as native
from scripts.research.four_atlas_archive import coverage, ticks_for_month

OUT = Path("research/results/retained_early_years")
BOOKS = [("portfolio", 5), ("portfolio", 7), ("filtered", 7),
         ("breakout", 7), ("london", 7)]


def count_ticks(start, end):
    count = 0
    for month in pd.period_range(start.strftime("%Y-%m"), (end - pd.Timedelta(seconds=1)).strftime("%Y-%m"), freq="M"):
        if month.strftime("%Y-%m") == start.strftime("%Y-%m") and start.day != 1:
            q = ticks_for_month(month.year, month.month)
            count += len(q) - int(q["ms"].searchsorted(start.value // 1_000_000))
        else:
            count += coverage()[str(month)]["ticks"]
    return count


def run_phase(*args, **kwargs):
    try:
        return native.test(*args, **kwargs)
    except subprocess.CalledProcessError:
        # MT5 can briefly return an invalid tester-agent session on restart.
        time.sleep(2)
        return native.test(*args, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int, choices=[2022, 2023, 2024])
    parser.add_argument("--terminal", required=True, type=Path)
    args = parser.parse_args()
    native.OUT = OUT
    native.TERMINAL = args.terminal
    OUT.mkdir(parents=True, exist_ok=True)
    start = pd.Timestamp(f"{args.year}-01-01", tz="UTC")
    end = start + pd.offsets.YearBegin(1)
    evaluation_ticks = count_ticks(start, end)
    for roster, mask in BOOKS:
        result = run_phase(roster, mask, args.year, start, "evaluation",
                           "phase_split", "early", guard=False, expected_ticks=evaluation_ticks)
        lifecycle = result["native"]["atlas"]
        if lifecycle["status"] == "passed":
            funded = pd.Timestamp(lifecycle["time"]).normalize() + pd.offsets.BDay()
            if funded < end:
                run_phase(roster, mask, args.year, funded, "funded", "phase_split", "early",
                          expected_ticks=count_ticks(funded, end))


if __name__ == "__main__":
    main()
