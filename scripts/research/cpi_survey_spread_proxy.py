"""Reproduce the preregistered cross-venue spread sensitivity."""
import csv
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import zipfile

import numpy as np

if __name__ == "__main__":
    # Freeze research-only process settings before loading the execution engine.
    os.environ.update(ULTRA_TRADE_24H="1", ULTRA_DISABLE_ALERTS="1", ULTRA_NO_TRIAL_LEDGER="1")

from scripts.research import cpi_survey_continuation as study


def read_spreads(requested):
    """Scan consecutive source minutes in order, preserving the first valid quote."""
    months = defaultdict(list)
    for stamp in sorted(requested):
        t = datetime.fromtimestamp(stamp, timezone.utc)
        months[t.strftime("%Y_%m")].append((stamp, t.strftime("%Y-%m-%d %H:%M").encode()))
    spreads = {}
    for month, minutes in months.items():
        path = Path("research/xauusd_archive/payload/exness/XAUUSDm") / f"Exness_XAUUSDm_{month}.zip"
        with zipfile.ZipFile(path) as archive:
            data = archive.read(archive.namelist()[0])
        cursor = 0
        for stamp, prefix in minutes:
            token = b'"XAUUSDm","' + prefix + b":"
            pos = data.find(token, cursor)
            while pos >= 0:
                end = data.index(b"\n", pos)
                row = next(csv.reader([data[pos:end].decode()]))
                bid, ask = float(row[2]), float(row[3])
                if np.isfinite([bid, ask]).all() and ask > bid > 0:
                    spreads[stamp] = ask - bid
                    cursor = end
                    break
                pos = data.find(token, end)
    return spreads


def main():
    primary = json.loads(study.OUTPUT.read_text())
    master = study.load_master(("M15", "M1"), start=1543622400, end=1793491200, use_cache=False)
    assert master.hash_key() == primary["master_hash"]
    times = master.m1["time"]
    base = study.SCENARIOS["realistic_ecn"]
    models = {"base": base, "stress": study.replace(base, spread_multiplier=2., slippage_points=60.)}
    sessions = []
    needed = set()
    for row in primary["records"]:
        if row["status"] != "directional":
            continue
        for arm, key in (("event", "date"), ("control", "control_date")):
            if key not in row:
                continue
            release = datetime.fromisoformat(row[key]).replace(hour=8, minute=30, tzinfo=study.NY)
            stamp = int(release.timestamp())
            window = np.arange(stamp - 1800, stamp + 107 * 60, 60)
            if np.array_equal(times[times.searchsorted(window[0]):times.searchsorted(window[-1], side="right")], window):
                sessions.append((row, arm, release, window))
                needed.update(window.tolist())
    spreads = read_spreads(needed)
    for row, arm, release, window in sessions:
        if any(t not in spreads for t in window):
            row[arm] = {"status": "missing quote window"}
            continue
        start = times.searchsorted(window[0])
        master.m1["spread"][start:start + len(window)] = np.rint([spreads[t] / master.spec.point for t in window])
        row[arm] = study.observe(master, release, row["side"], models)
    primary["spread_scenario"] = "Exness Standard opening quote spreads on master bid OHLC"
    primary["requested_minutes"] = len(needed)
    primary["observed_minutes"] = len(spreads)
    study.OUTPUT.with_name("cpi_survey_spread_proxy.json").write_text(json.dumps(primary, indent=2))


if __name__ == "__main__":
    main()
