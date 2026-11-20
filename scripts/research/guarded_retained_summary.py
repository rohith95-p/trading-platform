"""Summarize the guarded native runs and conditional cash at the $5k account tier."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp
from src.research.metrics import expected_max_sr, deflated_sharpe_ratio, bonferroni_correction
from src.backtesting.metrics import bootstrap_ci_metrics, closed_balance_metrics, drop_best_worst, monte_carlo_paths, pnl_ratios

BASE = Path("research/results/guarded_retained_mt5")


def run():
    rows = []
    robustness = {}
    days = {}
    for path in sorted(BASE.glob("*_audit.json")):
        audit = json.loads(path.read_text())
        stem = audit["name"]
        result = audit["native"]["atlas"]
        start = pd.Timestamp(audit["start"])
        end = pd.Timestamp(audit["end_exclusive"])
        raw = pd.read_csv(BASE / f"{stem}_trades.csv")
        records = list(raw.itertuples(index=False))
        values = raw.net_pl
        ratios = pnl_ratios(values)
        points = pd.Series(values.to_numpy(), index=pd.to_datetime(raw.exit_time_ms, unit="ms", utc=True))
        idx = pd.date_range(start, end, inclusive="left")
        daily = points.resample("D").sum().reindex(idx, fill_value=0.)
        weekly = daily.resample("W-SUN").sum()
        sr = daily.mean() / daily.std(ddof=0)
        group = (audit["year"], audit["phase"])
        if audit.get("policy", "uniform") == "uniform":
            days.setdefault(group, []).append((stem, daily, sr))
        robustness[stem] = dict(expectancy=float(values.mean()), omega_zero=ratios["profit_factor"],
                                ratios=ratios, closed_balance=closed_balance_metrics(records, [], 5000.,
                                start_ts=int(start.timestamp()), end_ts=int(end.timestamp())),
                                bootstrap=bootstrap_ci_metrics(records), ablation=drop_best_worst(records),
                                monte_carlo_trade_order=monte_carlo_paths(records, 5000.),
                                weekly_one_sided_p=float(ttest_1samp(weekly, 0., alternative="greater").pvalue))
        pay = result["modeled_payouts"]
        if audit["phase"] == "funded" and audit["native"]["unrestricted"]["max_floating_loss"] >= 100:
            raise ValueError(f"{stem} has an unreconciled native Protector trigger")
        rows.append(dict(name=stem, year=audit["year"], phase=audit["phase"], roster=audit["roster"],
                        mask=audit["mask"], policy=audit.get("policy","uniform"), attempt=audit.get("attempt",""), **audit["trading"], ecn_net=audit["standardized_ecn"]["net"],
                        ecn_pf=audit["standardized_ecn"]["pf"], status=result["status"], time=result["time"],
                        max_account_dd=result["max_equity_drawdown_pct"], cash=result["modeled_cash_received"],
                        fees_if_activated=83 if audit["phase"]=="funded" else 5,
                        first_payout=pay[0]["time"] if pay else None, ecn_status=audit["ecn"]["atlas"]["status"],
                        ecn_cash=audit["ecn"]["atlas"]["modeled_cash_received"]))
    for (year, phase), observations in days.items():
        # Only evaluation records have common calendar windows across every candidate.
        if phase != "evaluation":
            continue
        variance = np.var([sr for _, _, sr in observations], ddof=1) if len(observations)>1 else 0.
        for stem, returns, _ in observations:
            detail = robustness[stem]
            detail.update(within_batch_trial_count=len(observations), within_batch_daily_SR_variance=variance,
                          within_batch_expected_max_sr=expected_max_sr(len(observations), variance),
                          within_batch_daily_dsr=deflated_sharpe_ratio(returns.to_numpy(), len(observations), variance),
                          within_batch_bonferroni=bonferroni_correction(detail["weekly_one_sided_p"], len(observations)))
    pd.DataFrame(rows).to_csv(BASE/"summary.csv", index=False)
    (BASE/"robustness.json").write_text(json.dumps(robustness, indent=2, allow_nan=False))


if __name__ == "__main__":
    run()
