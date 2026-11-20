"""All candidate outcomes, pooled trade distributions and dated search sensitivities."""
import json
import argparse
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from src.research.metrics import deflated_sharpe_ratio,expected_max_sr,bonferroni_correction
from src.backtesting.metrics import drop_best_worst,monte_carlo_paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--coverage-segments',action='store_true')
    args = parser.parse_args()
    root = Path('research/results/genesis_2026-11-11')
    cases = {}
    details = {}
    for year in (2013,2018,2025):
        for suffix in ('','.repair'):
            coverage = '.segments' if args.coverage_segments and year==2025 else ''
            r = json.loads((root/f'{year}.backtest{suffix}{coverage}.json').read_text())
            for name,case in r['results'].items():
                cases.setdefault(name,{})[year] = case
    index = pd.DatetimeIndex(np.concatenate([pd.date_range(str(y),f'{y}-12-31',tz='UTC').to_numpy() for y in (2013,2018,2025)]))
    matrix = pd.DataFrame(0.,index=index,columns=list(cases))
    rng = np.random.default_rng(7131825)
    for name,years in cases.items():
        p = np.array([t['pnl'] for c in years.values() for t in c['baskets']])
        gross_profit,gross_loss = p[p>0].sum(),-p[p<0].sum()
        for year,case in years.items():
            for t in case['baskets']:
                date = pd.Timestamp(t['exit_time'],unit='s',tz='UTC').normalize()
                if date.year!=year and t['reason']=='boundary':
                    date = pd.Timestamp(t['exit_time']-1,unit='s',tz='UTC').normalize()
                matrix.loc[date,name] += t['pnl']/5000.
        daily = matrix[name]*5000
        month = daily.groupby(daily.index.strftime('%Y-%m')).sum().to_numpy()
        boot = rng.choice(month,size=(5000,len(month)),replace=True).sum(axis=1)
        centered = month-month.mean()
        null = rng.choice(centered,size=(5000,len(month)),replace=True).sum(axis=1)
        tr = [SimpleNamespace(net_pl=x) for x in p]
        details[name] = dict(trades=len(p),net=float(p.sum()),
            profit_factor=float(gross_profit/gross_loss) if gross_loss else None,
            wins=int(sum(p>0)),win_pct=float(100*np.mean(p>0)) if len(p) else None,
            mean_pnl=float(p.mean()) if len(p) else None,
            per_year={str(y):{k:c[k] for k in ('trades','profit_factor','net','win_pct','sampled_liquidation_max_dd_pct')} for y,c in years.items()},
            meets_pf_1_3_each_year=all(c['profit_factor'] is not None and c['profit_factor']>=1.3 and c['trades']>=30 for c in years.values()),
            month_block_net_interval_95=np.percentile(boot,[2.5,97.5]).tolist(),
            bonferroni_month_bootstrap_p=bonferroni_correction((1+sum(null>=p.sum()))/5001,len(cases)),
            ablation=drop_best_worst(tr) if len(p) else None,
            trade_order_monte_carlo=monte_carlo_paths(tr,5000,n=1000) if len(p) else None)
    sr = matrix.mean()/matrix.std(ddof=0).replace(0,np.nan)
    variance = float(sr.dropna().var(ddof=1))
    for name in cases:
        a = matrix[name].to_numpy()
        details[name]['dsr_sensitivities'] = {str(n):deflated_sharpe_ratio(a,n,variance) for n in (len(cases),640,1000,2000)} if np.std(a)>0 else None
    report = dict(candidates=len(cases),sample_calendar_days=len(matrix),years=[2013,2018,2025],
        caveats=['Inspected disjoint calendar years, not untouched forward validation.',
                 'Pooled trade arithmetic is not continuous multi-year account equity.',
                 'DSR on fixed-$5000 daily realized cash; counts are sensitivities, full historical search unknown.',
                 'Month bootstrap uses36 calendar-month allocations, including incomplete source coverage; no future profit probability.',
                 'Missing source dates are encoded as zero cash for aggregation, not evidence of flat exposure or zero returns.',
                 'Coverage-segment mode uses independent 2025 samples with retrospective boundary liquidation and renewed warmup; not a continuous account.' if args.coverage_segments else 'Unsegmented 2025 results include unknown price paths across a month-long source gap; prefer coverage-segment sensitivity.',
                 'Trade-order permutations preserve final profit; not a future-loss forecast.',
                 'Original app forming-candle timing, full risk/MTF/news/confirmation and broker constraints excluded.'],
        cross_trial_daily_sharpe_variance=variance,
        expected_max_sr_sensitivities={str(n):expected_max_sr(n,variance) for n in (len(cases),640,1000,2000)},
        results=details)
    suffix = '_coverage' if args.coverage_segments else ''
    (root/f'summary{suffix}.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    matrix.to_csv(root/f'daily_candidate_returns{suffix}.csv')
    print('candidates',len(cases),'qualified',[k for k,v in details.items() if v['meets_pf_1_3_each_year']],flush=True)
    for name in cases:
        if name.endswith(' static'):
            print(name,[details[name]['per_year'][str(y)]['profit_factor'] for y in (2013,2018,2025)],flush=True)


if __name__=='__main__':
    main()
