"""Write a reproducible result index for frozen native retained book experiments."""
import json
from pathlib import Path
import pandas as pd

BASE=Path("research/results/guarded_retained_mt5")
BOOKS = {3:"both Asians",5:"filtered + London",6:"breakout + London",7:"three-leg"}


def render():
    paths=sorted(BASE.glob("*_audit.json"))
    doc=["# Native MT5 retained-book test",
         "",
         "Each report uses the original Exness XAUUSDm bid/ask archive in the 100% real-tick native MT5 Strategy Tester, with hedging, fixed position size, visible server stops and targets. Each January starts a separate $5,000 simulated evaluation. A successful evaluation starts a fresh $5,000 funded account on the next weekday. 2026 ends at the October 31 cutoff. Quarterly starts and the continuous account are listed separately.",
         "",
         "The funded guard allows one 0.01-lot position, requires initial stop risk plus a $5 allowance to fit a $35 budget, and requests a market liquidation at $60 total floating loss. Signals, stops and targets come from the original retained strategy rules. The selector uses filtered Asian, breakout, then London priority. The book makes no filler trades for inactivity. 'uniform' applies the guard during both phases. 'phase_split' evaluates at the original native 0.02-lot settings and activates the same frozen guard for the funded phase.",
         "",
         "A native equity/deal reconciliation is followed by the Atlas rule replay, including eligible $100 modeled cash withdrawals. MT5 net profit is the native full-window trading profit at the tested leverage and before payout deductions. The simulated account stops at a rule failure. Subtract $5 evaluation and $78 activation per activated account from eligible receipts. Whole-window trading P&L and cash withdrawn measure different outcomes.",
         "",
         "| Window | Book | Policy | Stage | Native positions | Native net | PF | Outcome | Conditional cash |",
         "|---|---|---|---|---:|---:|---:|---|---:|"]
    decisions = ["## January phase-split attempts", "",
                 "| Book | Year | Funded trading P&L | PF | Result at cutoff | Conditional cash after fees |",
                 "|---|---:|---:|---:|---|---:|"]
    for path in paths:
        item = json.loads(path.read_text())
        if item.get("policy") != "phase_split" or item["phase"] != "funded" or item.get("attempt", "") not in (
            "", "m01d01x3", "m01d01x5", "m01d01x6"):
            continue
        atlas = item["native"]["atlas"]
        stats = item["trading"]
        label = BOOKS[item["mask"]] if item["roster"] == "portfolio" else item["roster"]
        decisions.append(f'| {label} | {item["year"]} | {stats["net"]:+.2f} | {stats["pf"]:.2f} | {atlas["status"].replace("_"," ")} | {atlas["modeled_cash_received"]-83:+.2f} |')
    decisions += ["", "## Full native results", ""]
    table_start = next(i for i, line in enumerate(doc) if line.startswith("| Window"))
    doc[table_start:table_start] = decisions
    for p in paths:
        d=json.loads(p.read_text())
        a=d["native"]["atlas"]
        t=d["trading"]
        window=d['start'][:10]+" to "+(pd.Timestamp(d["end_exclusive"])-pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        outcome=a["status"].replace("_"," ") + (" "+a["time"][:10] if a["time"] else " at cutoff")
        roster=BOOKS[d["mask"]] if d["roster"]=="portfolio" else d["roster"]
        pf=t["pf"]
        doc.append(f'| {window} | [{roster}]({d["name"]}.htm) | {d.get("policy","uniform")} | {d["phase"]} | {t["trades"]} | {t["net"]:+.2f} | {pf:.2f} | {outcome} | {a["modeled_cash_received"]:.2f} |' if pf is not None else
                   f'| {window} | [{roster}]({d["name"]}.htm) | {d.get("policy","uniform")} | {d["phase"]} | {t["trades"]} | {t["net"]:+.2f} | undefined | {outcome} | {a["modeled_cash_received"]:.2f} |')
    doc.extend(["", "JSON audits preserve chronological terminal equity extrema, Atlas events and payout timestamps, plus a modeled commission, swap and slippage sensitivity that holds native fills fixed. This research uses selected historical USD news events. The full Atlas all-currency calendar, Atlas-specific symbol trading sessions and complete cost history are unverified. No cash was received or paid. Earlier results informed the phase choice and guard settings.",
                "", "The robustness export reports trade-outcome bootstrap intervals, best/worst-trade removals, random reorderings, ratios, and within-batch multiple-testing estimates. The DSR calculation uses the cross-book variance of daily Sharpe across same-window uniformly guarded candidates. These trial counts exclude earlier strategy development. The funder compliance and payout decision do not use Monte Carlo or bootstrap paths.",
                "", "[Summary CSV](summary.csv) · [Robustness and metric inputs](robustness.json) · [Native original evaluation records](../retained_mt5/native_comparison.md)"])
    (BASE/"report.md").write_text("\n".join(doc)+"\n", encoding="utf-8")


if __name__=="__main__":
    render()
