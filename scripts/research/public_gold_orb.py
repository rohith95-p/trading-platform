import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.metrics import monte_carlo_paths, drop_best_worst
from src.research.metrics import expected_max_sr, deflated_sharpe_ratio, bonferroni_correction
from src.research.dated_results import save_result
from scripts.validation.full_metric_suite import ratios


def payoff(path, side, width, target):
    spread = np.where(path['spread'] > 0, path['spread'], 260)*.001
    entry = path['open'][0] + (spread[0] if side==1 else 0) + side*.02
    stop, limit = entry-side*.5*width, entry+side*target*width
    adjustment = spread if side==-1 else 0.
    hi, lo, op = [path[k]+adjustment for k in ('high','low','open')]
    stopped = lo[:-1]<=stop if side==1 else hi[:-1]>=stop
    won = hi[:-1]>=limit if side==1 else lo[:-1]<=limit
    hits = np.flatnonzero(stopped|won)
    fill = op[-1]-side*.02
    if len(hits):
        j = hits[0]
        if stopped[j]:
            fill = (min(stop,op[j]) if side==1 else max(stop,op[j]))-side*.02
        else:
            fill = limit
    return 2*side*(fill-entry)-.07


def main():
    result = {}
    rng = np.random.default_rng(251111)
    for first,last in [('2005','2011'),('2012','2018'),('2019','2025')]:
        opens = (pd.bdate_range(first,last+'-12-31')+pd.Timedelta(hours=9,minutes=30)).tz_localize('America/New_York')
        data = load_master(('M1','M15'), start=int(opens[0].timestamp()),end=int(opens[-1].timestamp())+23460,use_cache=False).m1
        times = np.ascontiguousarray(data['time'])
        complete = 0
        rows = []
        trade_dates = []
        for dt in opens:
            ts=int(dt.timestamp())
            i=times.searchsorted(ts)
            day=data[i:i+391]
            if len(day)!=391 or day['time'][0]!=ts or not np.all(np.diff(day['time'])==60):
                continue
            complete+=1
            high,low=day['high'][:15].max(),day['low'][:15].min()
            if high<=low: continue
            for e in range(20,150,5):
                close=day['close'][e-1]
                if low<=close<=high: continue
                side=1 if close>high else -1
                rows.append((side,*[payoff(day[e:],s,high-low,t) for t in (1,2) for s in (1,-1)]))
                trade_dates.append(dt.tz_convert('UTC').normalize())
                break
        a=np.asarray(rows)
        longs=a[:,0]>0
        streams=[np.where(longs,a[:,j],a[:,j+1]) for j in (1,3)]
        variance=np.var([p.mean()/p.std() for p in streams],ddof=1)
        for arm,p in enumerate(streams):
            save_result('orb_target_'+str(arm+1),pd.Series(p,index=trade_dates),
                        first+'-01-01',last+'-12-31',
                        specification='research/registry/PREREG_PublicGoldORB_2026-11-11.md',runner=__file__)
            j=1+2*arm
            null=np.array([np.where(rng.permutation(longs),a[:,j],a[:,j+1]).mean() for _ in range(2000)])
            report=ratios(p,int(last)-int(first)+1)
            tr=[SimpleNamespace(net_pl=float(x)) for x in p]
            report.update(weekdays=len(opens),complete=complete,wins=int(sum(p>0)),
                expected_max_sr=expected_max_sr(2,variance),dsr_two_trials=deflated_sharpe_ratio(p,2,variance),
                adjusted_control_p=bonferroni_correction((1+sum(null>=p.mean()))/2001,6),
                permutation=monte_carlo_paths(tr,5000),ablation=drop_best_worst(tr))
            result[f'{first}-{last} target{arm+1}']=report
            print(first,last,complete,len(opens),arm+1,len(p),sum(p>0),report['net'],report['profit_factor'],flush=True)
    Path('research/registry/public_gold_orb_metrics.json').write_text(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
