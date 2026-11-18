"""Replay the preregistered CPI consensus rule and calendar-matched controls."""
import csv
import json
import os
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from zoneinfo import ZoneInfo

if __name__ == "__main__":
    # Freeze research-only process settings before loading the execution engine.
    os.environ.update(ULTRA_TRADE_24H="1", ULTRA_DISABLE_ALERTS="1", ULTRA_NO_TRIAL_LEDGER="1")

from scripts.research.fomc_shock_propagation import event_bars, replay_one
from src.backtesting.costs import SCENARIOS
from src.backtesting.master import load_master

EVENTS = Path("research/events")
OUTPUT = Path("research/registry/cpi_survey_continuation.json")
NY = ZoneInfo("America/New_York")


def excluded_dates():
    from scripts.research.post_bls_reaction import release_from_url
    archive = json.loads((EVENTS / "bls_release_archive_links_2019_2025.json").read_text())
    links = [row["source_url"] for row in archive["records"]]
    links.extend(json.loads((EVENTS / "bls_december_2018_release_links.json").read_text()))
    dates = {release_from_url(link)["release_utc"][:10] for link in links}
    with (EVENTS / "usd_high_impact_2022_2026.csv").open() as stream:
        dates.update(row["local_time_et"][:10] for row in csv.DictReader(stream))
    return dates


def observe(master, release, side, models):
    stamp = int(release.timestamp())
    entry = stamp + 45 * 60
    times = master.m1["time"]
    start = times.searchsorted(stamp - 1800)
    window = master.m1[start:start + 137]
    if not np.array_equal(window["time"], stamp + np.arange(-30, 107) * 60):
        return {"status": "missing M1"}
    bars = event_bars(master, entry)
    if bars.m15["time"].searchsorted(entry) < 260:
        return {"status": "missing M15 warmup"}
    spreads = window["spread"][:30]
    valid = spreads[spreads > 0]
    latest = window["spread"][74]
    if len(valid) < 15 or latest <= 0:
        return {"status": "missing observed spread"}
    if latest > 1.5 * np.median(valid):
        return {"status": "spread filter", "base": 0., "stress": 0.}
    move = window["close"][74] - window["open"][30]
    if side * move <= 0:
        return {"status": "direction filter", "base": 0., "stress": 0.}
    feature = {"direction": side, "latest_feature_close_time": entry}
    result = {}
    for scenario, cost in models.items():
        replay, _ = replay_one(bars, stamp, feature, cost, 5000., "candidate")
        if len(replay.trades) != 1:
            return {"status": "engine did not fill"}
        trade = replay.trades[0]
        result[scenario] = trade.net_pl
        result[scenario + "_entry"] = trade.entry_time
        result[scenario + "_exit"] = trade.exit_time
    return {"status": "filled", **result}


def main():
    calendar = excluded_dates()
    master = load_master(("M15", "M1"), start=1543622400, end=1793491200, use_cache=False)
    base = SCENARIOS["realistic_ecn"]
    models = {"base": base, "stress": replace(base, spread_multiplier=2., slippage_points=60.)}
    records = []
    with (EVENTS / "us_headline_cpi_consensus_coverage.csv").open() as stream:
        for row in csv.DictReader(stream):
            date = row["release_date"]
            item = {"date": date}
            records.append(item)
            if not row["consensus_pct"]:
                item["status"] = "missing forecast"
                continue
            side = int(np.sign(float(row["consensus_pct"]) - float(row["first_print_pct"])))
            if not side:
                item["status"] = "tie"
                continue
            release = datetime.fromisoformat(row["scheduled_utc"]).astimezone(NY)
            item.update(status="directional", side=side, event=observe(master, release, side, models))
            for weeks in range(1, 5):
                control = release - timedelta(weeks=weeks)
                if control.date().isoformat() not in calendar:
                    item.update(control_date=str(control.date()), control=observe(master, control, side, models))
                    break
    OUTPUT.write_text(json.dumps({"costs": {k: v.descriptor() for k, v in models.items()},
                                  "master_hash": master.hash_key(), "records": records}, indent=2))


if __name__ == "__main__":
    main()
