"""Reproduce PREREG_EquityShockGold from the project root."""
import numpy as np
import pandas as pd
import json
from pathlib import Path
from types import SimpleNamespace
from src.research.metrics import expected_max_sr, deflated_sharpe_ratio, bonferroni_correction
from src.backtesting.metrics import monte_carlo_paths, drop_best_worst


def main():
    frame = pd.read_csv('research/data/d1_study/master.csv', index_col='Date',
                        parse_dates=True)[['spx','vix','gold']].dropna().sort_index()
    rng = np.random.default_rng(714)
    report = []
    block_rng = np.random.default_rng(715)
    for start, end in [('2000','2011'), ('2012','2018'), ('2019','2025')]:
        data = frame.loc[start:end]
        trigger = (data.spx.pct_change() <= -.01) & (data.vix.diff() > 0)
        ret = data.gold.pct_change().shift(-1).iloc[2:-1]
        selected = ret[trigger.shift(1, fill_value=False).reindex(ret.index)]
        for side in [1,-1]:
            net = selected.to_numpy()*side - .0004
            controls = [rng.choice(ret.to_numpy(),len(net),replace=False).mean()*side-.0004
                        for _ in range(2000)]
            daily = pd.Series(0., index=ret.index)
            daily.loc[selected.index] = net
            equity = (1+daily).cumprod()
            drawdown = 1-equity/equity.cummax().clip(lower=1.)
            years = (daily.index[-1]-daily.index[0]).days/365.25
            annual = equity.iloc[-1]**(1/years)-1
            months = pd.DataFrame({'pnl':daily,'count':daily.index.isin(selected.index).astype(int)},
                                  index=daily.index).resample('ME').sum().to_numpy()
            draws = months[block_rng.integers(len(months),size=(5000,len(months)))].sum(axis=1)
            ci = np.quantile(draws[:,0]/draws[:,1],[.025,.975])
            # Two related candidate directions: report raw-N sensitivity only.
            opposite = daily.copy()
            opposite.loc[selected.index] = -side*selected-.0004
            variance = float(np.var([daily.mean()/daily.std(),opposite.mean()/opposite.std()],ddof=1))
            records = [SimpleNamespace(net_pl=float(x)*5000) for x in net]
            cash_path = np.r_[5000.,5000.+np.cumsum(net*5000)]
            dd_cash = (np.maximum.accumulate(cash_path)-cash_path).max()
            p = (1+np.count_nonzero(np.asarray(controls)>=net.mean()))/(1+len(controls))
            report.append(dict(era=f'{start}-{end}',side=side,trades=len(net),
                expected_max_daily_sr_n2=expected_max_sr(2,variance),
                dsr_raw_n2_sensitivity=deflated_sharpe_ratio(daily.to_numpy(),2,variance),
                random_timing_p=p,bonferroni_six_direction_era_comparisons=bonferroni_correction(p,6),
                omega_zero=float(net[net>0].sum()/-net[net<0].sum()),
                recovery_fixed_notional=float(net.sum()*5000/dd_cash),
                permutation_fixed_5000_notional=monte_carlo_paths(records,5000.),
                ablation_fixed_5000_notional=drop_best_worst(records),
                win_rate=float((net>0).mean()),pf=float(net[net>0].sum()/-net[net<0].sum()),
                expectancy_bp=float(net.mean()*10000),control_p975_bp=float(np.quantile(controls,.975)*10000),
                monthly_bootstrap_expectancy_ci_bp=(ci*10000).tolist(),
                annualized_daily_sharpe=float(np.sqrt(252)*daily.mean()/daily.std()),
                annualized_daily_sortino=float(np.sqrt(252)*daily.mean()/np.sqrt(np.minimum(daily,0).pow(2).mean())),
                compounded_return=float(equity.iloc[-1]-1),max_close_drawdown=float(drawdown.max()),
                calmar=float(annual/drawdown.max()),worst_trade=float(net.min()),
                mean_bp_at_double_cost=float(net.mean()*10000-4),
                expectancy_without_best_trade_bp=float(np.sort(net)[:-1].mean()*10000)))
            print(start,end,'long' if side==1 else 'short',len(net),
                  'mean_bp',round(net.mean()*10000,2),'control_p975_bp',
                  round(np.quantile(controls,.975)*10000,2),'PF',
                  round(net[net>0].sum()/-net[net<0].sum(),3),
                  'wins',sum(net>0),'worst_pct',round(net.min()*100,2))
    Path('research/registry/equity_shock_gold_metrics.json').write_text(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
