"""Descriptive data probe for the first pre-registered lifecycle coverage stop.

Created after the replay identified the stop, not a new trading hypothesis.
"""
from datetime import datetime, timezone
import json
import numpy as np

from scripts.validation.access_lifecycle_20261118 import START, END, OUT
from src.backtesting.master import load_master


def main():
    result = json.loads((OUT / "summary.json").read_text())
    phase = result["phases"][-1]
    if phase["reason"] != "missing_or_partial_M1_with_existing_exposure":
        raise ValueError("Probe only applies to the recorded incomplete-block stop")
    start = int(phase["finished_at"])
    bars = load_master(("M15", "M1", "D1"), start=START, end=END)
    observed = bars.m1[(bars.m1["time"] >= start) & (bars.m1["time"] < start + 900)]
    missing = np.setdiff1d(np.arange(start, start + 900, 60), observed["time"])
    payload = {
        "kind": "post_replay_data_diagnostic_no_rule_change", "stopped_block_start": start,
        "stopped_block_end": start + 900, "observed_minutes": len(observed),
        "missing_minutes": [{"time": int(ts), "utc": datetime.fromtimestamp(int(ts), timezone.utc).isoformat()} for ts in missing],
        "observed_rows": [{"time": int(row["time"]), **{field: float(row[field]) for field in ("open", "high", "low", "close")},
                           "spread": int(row["spread"])} for row in observed],
    }
    (OUT / "coverage_stop_forensics.json").write_text(json.dumps(payload, indent=2))
    print(json.dumps({key: value for key, value in payload.items() if key != "observed_rows"}))


if __name__ == "__main__":
    main()
