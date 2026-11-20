"""Audit Aurion's native MT5 deal report against the archived quote path."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

import pandas as pd

from research.results.luna_payout_candidate.check_l2 import check
from research.results.luna_payout_candidate.trade_durations import classify, classify_stops


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", type=Path)
    p.add_argument("cache", type=Path)
    p.add_argument("phase", choices=["evaluation", "funded"])
    p.add_argument("start")
    p.add_argument("end")
    args = p.parse_args()
    start, end = (pd.Timestamp(value, tz="UTC") for value in (args.start, args.end))
    audit = check(args.report, args.cache, start, end, allowed_tick_count_delta=1, phase=args.phase)
    audit["native_tick_count"] = int(audit["metrics"]["Ticks"].replace(" ", ""))
    deals = audit.pop("deals")
    audit["phase"] = args.phase
    for breach in ("daily", "trailing", "protector"):
        if breach in audit["events"]:
            timestamp = pd.Timestamp(audit["events"][breach]).timestamp()
            last_fill = max((d["ts"] for d in deals if d["ts"] <= timestamp), default=start.timestamp())
            audit[f"{breach}_first_crossing_seconds_since_fill"] = round(timestamp - last_fill, 3)
    try:
        durations = classify(deals)
    except ValueError as error:
        durations = {start.year: Counter()}
        audit["holding_time_audit"] = str(error)
    audit["trading_rule_diagnostics"] = classify_stops(args.report, deals, durations)
    if args.phase == "funded":
        audit["first_funded_event_on_unchanged_fills"] = audit.pop("evaluation_first_event")
        audit["funded_assumption"] = (
            "Quote reconstruction uses unmodified EA fills. The first Protector event calls for "
            "liquidation. Native positions after that event cannot establish subsequent account status or payouts."
        )
    with args.report.with_suffix(".csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(deals[0]))
        writer.writeheader()
        writer.writerows(deals)
    audit_path = args.report.with_name(args.report.stem + "_audit.json")
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(audit_path, audit.get("evaluation_first_event", audit.get("first_funded_event_on_unchanged_fills")),
          audit["trading_rule_diagnostics"])


if __name__ == "__main__":
    main()
