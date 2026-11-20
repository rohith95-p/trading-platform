"""Run an Atlas attempt from an explicit date in the fresh native MT5 tester."""
import argparse
import pandas as pd
from scripts.research.guarded_retained_native import test


def staged(start, mask):
    start = pd.Timestamp(start, tz="UTC")
    tag = start.strftime("m%md%d") + "x" + str(mask)
    result = test("portfolio", mask, start.year, start, "evaluation", "phase_split", tag, guard=False)
    stage = result["native"]["atlas"]
    if stage["status"] == "passed":
        funded = pd.Timestamp(stage["time"]).normalize() + pd.offsets.BDay(1)
        result = test("portfolio", mask, start.year, funded, "funded", "phase_split", tag)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("starts", nargs="+")
    parser.add_argument("--mask", type=int, default=7)
    args = parser.parse_args()
    for date in args.starts:
        staged(date, args.mask)
