"""Run with python -m scripts.research.london_auction from the project root."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from src.backtesting.master import load_master
from src.backtesting.metrics import drop_best_worst, monte_carlo_paths
from src.research.metrics import bonferroni_correction, deflated_sharpe_ratio, expected_max_sr
from src.research.dated_results import save_result


def simulate(bars, entries):
    timestamps = bars['time']
    rows = []
    for entry in entries:
        ts = int(entry.timestamp())
        i = timestamps.searchsorted(ts-1800)
        window = bars[i:i+91]
        if len(window)!=91 or not np.array_equal(window['time'],ts+60*np.arange(-30,61)):
            continue
        history, future = window[:30], window[30:]
        move = history['close'][-1]-history['open'][0]
        distance = history['high'].max()-history['low'].min()
        if not move or distance<=0:
            continue
        spread = np.where(future['spread']>0,future['spread'],260)*.001
        pnl = []
        for side in [np.sign(move),-np.sign(move)]:
            price = future['open'][0]+(spread[0] if side>0 else 0)+side*.02
            stop = price-side*distance
            adverse = future['low'][:60] if side>0 else future['high'][:60]+spread[:60]
            hits = np.flatnonzero(side*(adverse-stop)<=0)
            if len(hits):
                j = hits[0]
                opening = future['open'][j]+(spread[j] if side<0 else 0)
                fill = min(opening,stop) if side>0 else max(opening,stop)
            else:
                fill = future['open'][60]+(spread[60] if side<0 else 0)
            pnl.append(float(2*(side*(fill-price)-.02)-.07))
        rows.append((entry.date().isoformat(),*pnl))
    return pd.DataFrame(rows,columns=['date','follow','fade']).set_index('date')


def main():
    rng = np.random.default_rng(1711)
    summary = {}
    for first,last in [(2005,2011),(2012,2018),(2019,2025)]:
        dates = pd.bdate_range(str(first),f'{last}-12-31')
        entries = (dates+pd.Timedelta(hours=15,minutes=15)).tz_localize('Europe/London')
        bars = load_master(('M1','M15'),start=int(entries[0].timestamp())-1800,
                           end=int(entries[-1].timestamp())+3660,use_cache=False)
        data = simulate(bars.m1,entries)
        calendar = data.reindex(dates.strftime('%Y-%m-%d'),fill_value=0.)
        variance = float((calendar.mean()/calendar.std()).var())
        draws = np.where(rng.random((2000,len(data)))<.5,data.follow,data.fade).mean(axis=1)
        for name in data:
            p = data[name].to_numpy()
            save_result('auction_'+name,pd.Series(p,index=pd.to_datetime(data.index)),
                        str(first)+'-01-01',str(last)+'-12-31',
                        specification='research/registry/PREREG_LondonAuction_2026-11-11.md',runner=__file__)
            daily = calendar[name].to_numpy()/5000
            balance = np.r_[5000.,5000.+np.cumsum(5000*daily)]
            peak = np.maximum.accumulate(balance)
            dd = max(peak-balance)
            dd_pct = max((peak-balance)/peak)
            records = [SimpleNamespace(net_pl=x) for x in p]
            months = data[name].groupby(data.index.str[:7]).agg(['sum','count']).to_numpy()
            blocks = months[rng.integers(len(months),size=(5000,len(months)))].sum(axis=1)
            prob = (1+sum(draws>=p.mean()))/(1+len(draws))
            pf = p[p>0].sum()/-p[p<0].sum()
            summary[f'{first}-{last} {name}'] = dict(trades=len(p),wins=int(sum(p>0)),
                win_pct=100*np.mean(p>0),net=p.sum(),pf=pf,omega_zero=pf,expectancy=p.mean(),
                eligible_fraction=len(data)/len(dates),max_closed_dd_usd=dd,max_closed_dd_fraction=dd_pct,
                expectancy_ci=np.quantile(blocks[:,0]/blocks[:,1],[.025,.975]).tolist(),
                annual_sortino=np.sqrt(252)*daily.mean()/np.sqrt(np.mean(np.minimum(daily,0)**2)),
                calmar=((balance[-1]/5000)**(1/(last-first+1))-1)/dd_pct if balance[-1]>0 else None,
                recovery=p.sum()/dd,expected_max_daily_sr=expected_max_sr(2,variance),
                dsr_two_arm_sensitivity=deflated_sharpe_ratio(daily,2,variance),
                adjusted_control_p=bonferroni_correction(prob,6),
                monte_carlo=monte_carlo_paths(records,5000.),ablation=drop_best_worst(records))
            print(first,last,name,len(p),round(100*np.mean(p>0),1),round(pf,3),round(p.sum(),2),flush=True)
    Path('research/registry/london_auction_metrics.json').write_text(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
