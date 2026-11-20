"""Conditional funded payout sensitivity given recorded native fills and activation date."""
import argparse
import json
from pathlib import Path

import pandas as pd

from scripts.research.four_atlas_lifecycle import audit_trade_ledger
from scripts.research.retained_native_account import NativeAccount


class FundedQuoteAudit(NativeAccount):
    verify_protector_from_quotes = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=Path)
    args = parser.parse_args()
    prefix = str(args.prefix)
    original = pd.read_csv(prefix + "_trades.csv")
    evidence = json.loads(Path(prefix + "_audit.json").read_text())
    rows = []
    # Sensitivity grid in dollars per 0.01-lot round trip, booked at entry.
    # Historical spreads, swaps and commissions in the report are retained.
    for extra in (0, .25, .50, 1., 2.):
        trades = original.copy()
        charge = extra * trades.lots / .01
        trades.entry_fee -= charge
        trades.net_pl -= charge
        cfg = dict(phase="funded", name=evidence["name"],
                   start=int(pd.Timestamp(evidence["start"]).timestamp()),
                   end_exclusive=int(pd.Timestamp(evidence["end_exclusive"]).timestamp()), net=trades.net_pl.sum())
        a = audit_trade_ledger(cfg, trades, FundedQuoteAudit, validate_project_cost=False)["atlas"]
        if extra == 0 and (a["status"] != evidence["native"]["atlas"]["status"] or
                           a["modeled_payouts"] != evidence["native"]["atlas"]["modeled_payouts"]):
            raise ValueError("Native baseline payout path failed reconciliation")
        rows.append(dict(extra_roundtrip_per_001_usd=extra, full_window_trading_net=round(cfg["net"], 2),
                         funded_outcome=a["status"], payouts=a["modeled_payouts"],
                         cash_after_attempt_fees=a["modeled_cash_received"] - 83 + (5 if len(a["modeled_payouts"]) >= 3 else 0)))
    Path(prefix + "_cost_sensitivity.json").write_text(json.dumps(dict(
        note="Hypothetical extra execution cost. Same native entries, exits and evaluation handoff. Native spread and charges already included. No broker quotation implied.",
        rows=rows), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
