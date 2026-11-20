"""Compute whole-window robustness from MT5 HTML deal tables in one test family."""
import argparse
import json
from pathlib import Path
import re
from types import SimpleNamespace

import numpy as np
import pandas as pd
from scipy import stats

from scripts.research.luna_six_month_audit import read_report
from src.backtesting.metrics import closed_balance_metrics, drop_best_worst, monte_carlo_paths, pnl_ratios
from src.research.metrics import bonferroni_correction, deflated_sharpe_ratio, expected_max_sr


def calculate(path):
    header, deals = read_report(path)
    dates = re.findall(r"\d{4}\.\d{2}\.\d{2}", header["Period"])
    start, end = (pd.Timestamp(s.replace(".", "-"), tz="UTC") for s in dates)
    if any(d["fee"] or d["swap"] or d["profit"] for d in deals if d["action"] == "in"):
        raise ValueError(f"Entry-side charges need allocation by position in {path}")
    closes = [d for d in deals if d["action"] == "out"]
    if not closes:
        return None
    pnl = np.array([d["profit"] + d["fee"] + d["swap"] for d in closes])
    reported = float(header["Total Net Profit"].replace(" ", ""))
    if abs(pnl.sum() - reported) > .011:
        raise ValueError(f"Deal totals disagree in {path}")
    # Closed-balance metrics only use the realization timestamps.
    trades = [SimpleNamespace(net_pl=x, entry_time=d["ts"], exit_time=d["ts"]) for x, d in zip(pnl, closes)]
    index = pd.to_datetime([d["ts"] for d in closes], unit="s", utc=True)
    daily = pd.Series(pnl, index=index).resample("D").sum().reindex(
        pd.date_range(start, end, inclusive="left"), fill_value=0.)
    if not np.isclose(daily.sum(), reported, atol=.011):
        raise ValueError(f"Dates omit realized profits in {path}")
    week = daily.resample("W-SUN").sum().to_numpy() / 5000
    weekly_p = float(stats.ttest_1samp(week, 0., alternative="greater").pvalue) if np.std(week) else None
    risk = closed_balance_metrics(trades, [], 5000, start_ts=start.timestamp(), end_ts=end.timestamp())
    ratios = pnl_ratios(pnl)
    return (week, dict(report=path.name, period=header["Period"], close_count=len(pnl),
        wins=int((pnl > 0).sum()), expectancy_usd=float(pnl.mean()), net_usd=reported,
        pf=ratios["profit_factor"], omega_per_close_zero_target=ratios["profit_factor"],
        sortino_per_close_zero_target=ratios["sortino_ratio"], realized_calmar=risk["calmar_ratio"],
        realized_recovery_factor=risk["recovery_factor"], native_equity_dd=header["Equity Drawdown Relative"],
        drop_extremes=drop_best_worst(trades), monte_carlo_closed_trade_order=monte_carlo_paths(trades, 5000),
        weekly_positive_mean_p=weekly_p))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("reports", type=Path, nargs="+")
    args = p.parse_args()
    results = [row for path in args.reports if (row := calculate(path)) is not None]
    sharpes = [w.mean()/w.std() for w, _ in results if w.std()]
    k = len(results)
    variance = float(np.var(sharpes, ddof=1)) if len(sharpes) > 1 else None
    for weekly, row in results:
        row["bonferroni_family_p"] = bonferroni_correction(row["weekly_positive_mean_p"], k) if row["weekly_positive_mean_p"] is not None else None
        row["dsr_family_sensitivity"] = deflated_sharpe_ratio(weekly, k, variance) if variance is not None else None
    payload = dict(reports=[r for _, r in results], family_size=k,
        expected_max_weekly_sharpe=expected_max_sr(k, variance) if variance is not None else None,
        scope="Within supplied family and period only. Strategy variants overlap and years were previously explored. Study-wide trial Sharpe distribution unavailable. Closed-deal permutations do not simulate Atlas rules. Grid legs can be dependent. Native deal charges only.")
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
