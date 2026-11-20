"""Rebase frozen MT5 fills on each month start for a two-size Access policy."""
import argparse
import json
from pathlib import Path

import pandas as pd

from scripts.research.four_atlas_lifecycle import audit_trade_ledger
from scripts.research.retained_native_account import NativeAccount


def replay(ledger, start, end, phase):
    selected = ledger.loc[ledger.entry_time_ms >= int(start.timestamp() * 1000)]
    cfg = dict(name="phased_portfolio", phase=phase, start=int(start.timestamp()),
               end_exclusive=int(end.timestamp()), net=selected.net_pl.sum())
    return audit_trade_ledger(cfg, selected, NativeAccount, validate_project_cost=False)["atlas"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int, choices=[2025, 2026])
    parser.add_argument("output", type=Path)
    parser.add_argument("--mask", type=int, choices=[3,5,6,7], default=7)
    args = parser.parse_args()
    year = args.year
    base = Path("research/results")
    regular = pd.read_csv(base / "retained_mt5" / f"{year}_portfolio_trades.csv")
    guarded = pd.read_csv(base / "guarded_retained_mt5" / f"{year}_portfolio_trades.csv")
    if args.mask != 7:
        folder = base / "guarded_retained_mt5"
        regular = pd.read_csv(folder / f"{year}_portfolio_mask{args.mask}_phase_split_m01d01x{args.mask}_trades.csv")
        guarded = pd.read_csv(folder / f"{year}_portfolio_mask{args.mask}_trades.csv")
    start = pd.Timestamp(f"{year}-01-01", tz="UTC")
    end = pd.Timestamp("2026-11-01" if year == 2026 else "2026-01-01", tz="UTC")
    results = []
    for day in pd.date_range(start, end, freq="MS", inclusive="left"):
        evaluation = replay(regular, day, end, "evaluation")
        row = dict(start=day.date().isoformat(), evaluation=evaluation["status"], eval_event=evaluation["time"],
                   funded_start=None, funded=None, funded_event=None, payouts=[], fees=5, net_cash=-5)
        if row["evaluation"] == "passed":
            funded_start = pd.Timestamp(row["eval_event"]).normalize() + pd.offsets.BDay()
            row["fees"] = 83
            row["net_cash"] = -83
            row["funded_start"] = funded_start.date().isoformat()
            if funded_start < end:
                funded = replay(guarded, funded_start, end, "funded")
                row.update(funded=funded["status"], funded_event=funded["time"], payouts=funded["modeled_payouts"],
                           max_floating_loss=funded["max_floating_loss"])
                if row["max_floating_loss"] >= 100:
                    raise ValueError("Recorded fills cannot reproduce a fresh Protector liquidation")
                row["net_cash"] += funded["modeled_cash_received"] + (5 if len(row["payouts"]) >= 3 else 0)
        results.append(row)
    args.output.write_text(json.dumps(dict(
        method="Overlapping alternative starts on recorded native fills, with daily quote-by-quote Atlas audit; excludes trades open at each boundary. Assumes same later signals, leverage eligibility, fills and costs; no fresh EA state. Next weekday funding. Diagnostic only. Later starts have less time. Never sum the alternative accounts.",
        rows=results), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
