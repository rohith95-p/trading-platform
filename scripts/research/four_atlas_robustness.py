"""Independent audit of the five staged January–October 2026 trade ledgers."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.backtesting.metrics import bootstrap_ci_metrics, closed_balance_metrics, drop_best_worst, monte_carlo_paths, pnl_ratios
from src.research.metrics import bonferroni_correction




def audit(path):
    trades = pd.read_csv(path/"trades.csv").sort_values(["exit_time_ms","exit_quote_index"])
    summary = json.loads((path/"summary.json").read_text())
    side = np.where(trades.is_buy,1.,-1.)
    realized = (trades.exit_price-trades.entry_price)*side*trades.lots*100+trades.swap-trades.commission
    np.testing.assert_allclose(realized,trades.net_pl,atol=1e-8)
    assert abs(realized.sum()-summary["net"])<1e-7
    assert (trades.entry_time_ms<=trades.exit_time_ms).all()
    records=list(trades.itertuples(index=False))
    ratios=pnl_ratios(trades.net_pl)
    balance=closed_balance_metrics(records,[],5000.,start_ts=summary["start"],end_ts=summary["end_exclusive"])
    points=pd.Series(trades.net_pl.to_numpy(),index=pd.to_datetime(trades.exit_time_ms.to_numpy(),unit="ms",utc=True))
    calendar=pd.date_range(pd.Timestamp(summary["start"],unit="s",tz="UTC"),pd.Timestamp(summary["end_exclusive"]-1,unit="s",tz="UTC").normalize())
    daily=points.resample("D").sum().reindex(calendar,fill_value=0.)
    weekly=daily.resample("W-SUN").sum().to_numpy()
    # One-sided weekly mean test; dropped or idle weeks are included.
    p=stats.ttest_1samp(weekly,0.,alternative="greater").pvalue
    return dict(net=summary["net"],wins=summary["wins"],trades=summary["trades"],ratio_metrics=ratios,
                closed_balance=balance,omega_zero=ratios["profit_factor"],expectancy=float(realized.mean()),
                monte_carlo_trade_order=monte_carlo_paths(records,5000.),ablation=drop_best_worst(records),
                bootstrap=bootstrap_ci_metrics(records),weekly_one_sided_p=float(p),
                note="Historical strategy selection involved more than these five outputs. A research-wide deflated Sharpe requires the original trial Sharpe distribution.")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("year", type=int, choices=[2025,2026])
    args=parser.parse_args()
    base=Path(f"research/results/four_strategies_{args.year}")
    groups=[p for p in sorted(base.iterdir()) if (p/"trades.csv").is_file() and (p/"summary.json").is_file()]
    result={folder.name:audit(folder) for folder in groups}
    for item in result.values():
        item["bonferroni_reported_series"]=bonferroni_correction(item["weekly_one_sided_p"],len(groups))
    (base/"robustness.json").write_text(json.dumps(result,indent=2,allow_nan=False))
