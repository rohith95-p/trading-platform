"""Gold-only reproduction of the published band-flip rule."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import drop_best_worst,monte_carlo_paths
from src.research.dated_results import save_result
from scripts.validation.full_metric_suite import ratios


def indicators(d):
    c,h,l=[d[x].to_numpy() for x in ('close','high','low')]
    tr=np.maximum(h-l,np.maximum(abs(h-np.r_[c[0],c[:-1]]),abs(l-np.r_[c[0],c[:-1]])))
    atr=np.full(len(c),np.nan)
    atr[9]=tr[:10].mean()
    for i in range(10,len(c)): atr[i]=(9*atr[i-1]+tr[i])/10
    upper=(h+l)/2+3*atr
    lower=(h+l)/2-3*atr
    side=np.full(len(c),-1)
    for i in range(10,len(c)):
        if not (upper[i]<upper[i-1] or c[i-1]>upper[i-1]): upper[i]=upper[i-1]
        if not (lower[i]>lower[i-1] or c[i-1]<lower[i-1]): lower[i]=lower[i-1]
        side[i]=(1 if c[i]>upper[i] else -1) if side[i-1]==-1 else (-1 if c[i]<lower[i] else 1)
    d['atr']=atr
    d['signal']=pd.Series(side,index=d.index).where(np.r_[False,side[1:]!=side[:-1]],0).shift(1).fillna(0)
    d['atr_entry']=d.atr.shift(1)
    return d


def replay(d):
    cost=SCENARIOS['realistic_ecn']
    position=None
    records=[]
    for row in d.itertuples():
        spread=cost.spread_price(.001,row.spread)
        def finish(price):
            start,entry,side,stop=position
            pnl=2*(price-entry)*side-.07+cost.swap(.02,side==1,start,int(row.time),.001,100)
            records.append((int(row.time),pnl))
        if position and row.signal and row.signal!=position[2]:
            side=position[2]
            finish(row.open+(spread if side==-1 else 0)-side*.02)
            position=None
        if position is None and row.signal and np.isfinite(row.atr_entry):
            side=int(row.signal)
            entry=row.open+(spread if side==1 else 0)+side*.02
            position=(int(row.time),entry,side,entry-side*3*row.atr_entry)
        if position:
            side,stop=position[2:]
            hit=row.low<=stop if side==1 else row.high+spread>=stop
            if hit:
                opening=row.open+(spread if side==-1 else 0)
                finish((min(opening,stop) if side==1 else max(opening,stop))-side*.02)
                position=None
    if position:
        finish(row.close+(spread if position[2]==-1 else 0)-position[2]*.02)
    return records


def main():
    raw=load_master(('M15',),end=1767225600).m15
    f=pd.DataFrame(raw)
    f.index=pd.to_datetime(f.time.to_numpy(),unit='s',utc=True)
    report={}
    for timeframe in ['1h','4h']:
        d=f.resample(timeframe).agg(dict(time='first',open='first',high='max',low='min',close='last',spread='first')).dropna()
        d=indicators(d)
        for first,last in [('2005','2011'),('2012','2018'),('2019','2025')]:
            records=replay(d.loc[first:last])
            p=np.array([r[1] for r in records])
            pnl=pd.Series(p,index=pd.to_datetime([r[0] for r in records],unit='s',utc=True))
            save_result('supertrend_'+timeframe,pnl,first+'-01-01',last+'-12-31',
                specification='research/registry/PREREG_PublicSupertrend_2026-11-11.md',runner=__file__)
            stats=ratios(p,7)
            tr=[SimpleNamespace(net_pl=x) for x in p]
            stats.update(wins=int(sum(p>0)),ablation=drop_best_worst(tr),permutation=monte_carlo_paths(tr,5000))
            report[first+' '+timeframe]=stats
            print(first,timeframe,len(p),stats['wins'],stats['profit_factor'],stats['net'],flush=True)
    Path('research/registry/public_supertrend_metrics.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
