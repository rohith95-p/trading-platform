"""Independently check accounting and resample fresh reproduction records."""
import json
from collections import defaultdict
from pathlib import Path
import datetime as dt
import numpy as np
from scipy import stats

OUT = Path(__file__).resolve().parent
rng = np.random.default_rng(20261111)

def metrics(rows):
    p = np.array([t['net_pl'] for t in rows])
    eq = np.r_[5000.,5000.+p.cumsum()]
    loss = -p[p<0].sum()
    dd = np.maximum.accumulate(eq)-eq
    iid_mean = np.array([rng.choice(p,size=len(p),replace=True).mean() for _ in range(5000)])
    by_month = defaultdict(list)
    for t in rows:
        m = dt.datetime.fromtimestamp(t['exit_time'],dt.timezone.utc).strftime('%Y-%m')
        by_month[m].append(t['net_pl'])
    # Whole observed trade-bearing months; no claim of stationary returns.
    blocks = list(by_month.values())
    sums = np.array([sum(x) for x in blocks])
    counts = np.array([len(x) for x in blocks])
    ix = rng.integers(0,len(blocks),size=(5000,len(blocks)))
    block_mean = sums[ix].sum(axis=1)/counts[ix].sum(axis=1)
    perm_dd, boot_final = [], []
    for _ in range(5000):
        e = np.r_[5000.,5000.+rng.permutation(p).cumsum()]
        perm_dd.append(float((np.maximum.accumulate(e)-e).max()))
        boot_final.append(float(5000.+rng.choice(p,size=len(p),replace=True).sum()))
    return dict(trades=len(p),net=float(p.sum()),pf=float(p[p>0].sum()/loss),
        win_pct=float((p>0).mean()*100),expectancy=float(p.mean()),
        realized_max_dd=float(dd.max()),
        per_trade_sortino_target_zero=float(p.mean()/np.sqrt(np.mean(np.minimum(p,0)**2))),
        per_trade_sharpe=float(p.mean()/p.std()),
        iid_bootstrap_expectancy_95=np.quantile(iid_mean,[.025,.975]).tolist(),
        month_block_bootstrap_expectancy_95=np.quantile(block_mean,[.025,.975]).tolist(),
        trade_bearing_months=len(blocks),
        permutation_max_dd_p50_p95=np.quantile(perm_dd,[.5,.95]).tolist(),
        iid_resampled_final_p025_p50_p975=np.quantile(boot_final,[.025,.5,.975]).tolist(),
        iid_resampled_fraction_final_below_start=float((np.array(boot_final)<5000.).mean()),
        caveat='Exploratory conditional resampling, not a posterior or a forecast; pooled eras reset engine state.')

if __name__ == '__main__':
    report = {'accounting':{},'metrics':{}}
    all_oos = []
    for name in ['DEV','TEST','RECENT']+[f'OOS_{i}' for i in range(1,6)]:
        data = json.loads((OUT/(name+'.json')).read_text())
        rows = data['trades']
        errors = defaultdict(int)
        balance = 5000.
        for t in rows:
            gross = (t['exit_price']-t['entry_price'])*(1 if t['is_buy'] else -1)*t['lots']*100.
            balance += t['net_pl']
            errors['gross_identity'] += int(abs(gross-t['gross_pl'])>1e-7)
            errors['net_identity'] += int(abs(t['gross_pl']-t['commission']+t['swap']-t['net_pl'])>1e-7)
            errors['commission'] += int(abs(t['commission']-3.5*t['lots'])>1e-7)
            errors['balance_chain'] += int(abs(balance-t['balance_after'])>1e-7)
            errors['exit_before_entry'] += int(t['exit_time']<t['entry_time'])
            errors['exit_after_window'] += int(t['exit_time']>data['end'])
        report['accounting'][name] = dict(errors)
        report['metrics'][name] = metrics(rows)
        if name.startswith('OOS'):
            all_oos.extend(rows)
    all_oos.sort(key=lambda t:t['exit_time'])
    report['metrics']['OOS_POOLED'] = metrics(all_oos)
    legs = defaultdict(list)
    for t in all_oos:
        legs[t['strategy']].append(t)
    report['oos_per_strategy'] = {k:metrics(v) for k,v in legs.items()}
    (OUT/'independent_statistics.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report['metrics']['OOS_POOLED'],indent=2))
    print('accounting',json.dumps(report['accounting']))
