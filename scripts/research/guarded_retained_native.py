"""Run guarded retained candidates in the native tester and trace separate Atlas accounts."""
import argparse
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess

import pandas as pd

from scripts.research.four_atlas_lifecycle import audit_trade_ledger
from scripts.research.retained_native_account import NativeAccount, comparable, metrics, normalize, read_export
from scripts.research.luna_six_month_audit import read_report

OUT = Path("research/results/guarded_retained_mt5")
TERMINAL = Path(os.environ.get("GUARDED_TERMINAL", Path(os.environ["TEMP"]) / "UltraEAReview20261120/Velora"))
BOOKS = [("portfolio", 7), ("filtered", 7), ("breakout", 7), ("london", 7),
         ("portfolio", 5), ("portfolio", 6), ("portfolio", 3)]


def test(roster, mask, year, start, phase, policy="uniform", attempt="", guard=True, until=None):
    stem = f"{year}_{roster}" + ("_funded" if phase == "funded" else "") + (f"_mask{mask}" if mask != 7 else "")
    if policy == "phase_split":
        stem += "_phase_split"
    if attempt:
        stem += "_" + attempt
    html = OUT / f"{stem}.htm"
    deals = OUT / f"{stem}_deals.csv"
    output = OUT / f"{stem}_audit.json"
    if output.exists():
        existing = json.loads(output.read_text())
        if existing["start"] != start.isoformat():
            raise ValueError("Prior audit has a different activation date")
        return existing
    if not (html.exists() and deals.exists()):
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               "research/mt5_retained/run_tester.ps1", "-Terminal", str(TERMINAL), "-Roster", roster,
               "-Year", str(year), "-Mask", str(mask), "-Phase", phase,
               "-FromDate", start.strftime("%Y.%m.%d"), "-Policy", policy]
        if until:
            cmd.extend(["-ToDate", pd.Timestamp(until).strftime("%Y.%m.%d")])
        if guard:
            cmd.append("-PayoutGuard")
        if attempt:
            cmd.extend(["-Attempt", attempt])
        subprocess.run(cmd, check=True)
    props, booked = read_report(html)
    exports = read_export(deals)
    assert len(booked) == len(exports)
    for fill, deal in zip(exports.itertuples(), booked):
        assert fill.order == deal["order"] and abs(fill.price - deal["price"]) < .00051
    raw = normalize(exports)
    if raw.empty:
        raise ValueError(f"No trades in {stem}")
    raw.to_csv(OUT / f"{stem}_trades.csv", index=False)
    net = raw.net_pl.sum()
    assert abs(net - float(props["Total Net Profit"].replace(" ", ""))) < .011
    end = pd.Timestamp(until or ("2026-11-01" if year == 2026 else f"{year+1}-01-01"), tz="UTC")
    cfg = dict(name=stem, phase=phase, net=net, start=int(start.timestamp()), end_exclusive=int(end.timestamp()))
    native = audit_trade_ledger(cfg, raw, NativeAccount, False)
    if phase == "funded" and native["unrestricted"]["max_floating_loss"] >= 100:
        raise ValueError(f"{stem} hit Protector; reconcile trigger and fills before accepting")
    stress = comparable(raw)
    cfg["net"] = stress.net_pl.sum()
    ecn = audit_trade_ledger(cfg, stress)
    result = dict(name=stem, attempt=attempt, guard=guard, policy=policy, year=year, roster=roster, mask=mask, phase=phase, start=start.isoformat(),
                  end_exclusive=end.isoformat(), terminal=props, trading=metrics(raw), standardized_ecn=metrics(stress),
                  native=native, ecn=ecn)
    output.write_text(json.dumps(result, indent=2))
    print(stem, native["atlas"]["status"], native["atlas"]["time"], net, flush=True)
    return result


def run(year):
    for roster, mask in BOOKS:
        start = pd.Timestamp(f"{year}-01-01", tz="UTC")
        result = test(roster, mask, year, start, "evaluation")
        atlas = result["native"]["atlas"]
        if atlas["status"] == "passed":
            funded = pd.Timestamp(atlas["time"]).normalize() + timedelta(days=1)
            while funded.weekday() >= 5:
                funded += timedelta(days=1)
            test(roster, mask, year, funded, "funded")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("year", type=int, nargs="+")
    parser.add_argument("--phase-split", action="store_true")
    args = parser.parse_args()
    for year in args.year:
        if args.phase_split:
            for roster, mask in BOOKS[:4]:
                baseline_path = Path("research/results/retained_mt5") / f"{year}_{roster}_audit.json"
                baseline = json.loads(baseline_path.read_text())["native"]["atlas"]
                if baseline["status"] == "passed":
                    funded = pd.Timestamp(baseline["time"]).normalize() + timedelta(days=1)
                    while funded.weekday() >= 5:
                        funded += timedelta(days=1)
                    test(roster, mask, year, funded, "funded", "phase_split")
        else:
            run(year)
