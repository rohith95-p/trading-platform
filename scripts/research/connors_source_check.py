"""Gold transfer of HATS Connors defaults; same-year, same-trend random controls."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS


def main():
    raw = load_master(('M15',), end=int(pd.Timestamp('2026-01-01',tz='UTC').timestamp())).m15
    f = pd.DataFrame(raw)
    f.index = pd.to_datetime(f.time,unit='s',utc=True)
    d = f.resample('D').agg(dict(time='first',close='last')).dropna()
    c = d.close
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=.5,adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=.5,adjust=False).mean()
    rsi = 100*gain/(gain+loss)
    slow,fast = c.rolling(200).mean(),c.rolling(5).mean()
    d['eligible'] = (c>slow).shift(1,fill_value=False)
    d['entry'] = ((c>slow)&(c<fast)&(rsi<10)).shift(1,fill_value=False)
    d['exit'] = ((c>fast)|(rsi>70)|(c<.95*slow)).shift(1,fill_value=False)
    cost = SCENARIOS['realistic_ecn']
    rng = np.random.default_rng(4201)
    result = {}
    for first,last in [('2005','2011'),('2012','2018'),('2019','2025')]:
        days = d.loc[first:last]
        end = raw['time'].searchsorted(int(f.loc[first:last].time.iloc[-1]),side='right')
        exits = days.time[days.exit].to_numpy()
        options = []
        for day in days[days.eligible].itertuples():
            ts = int(day.time)
            i = raw['time'].searchsorted(ts)
            later = exits.searchsorted(ts,side='right')
            j = raw['time'].searchsorted(exits[later]) if later<len(exits) else end
            price = cost.ask(raw['open'][i],.001,raw['spread'][i])+.02
            stop = price*.97
            hits = np.flatnonzero(raw['low'][i:j]<=stop)
            if hits.size:
                k=i+hits[0]
                bid,close_ts=min(stop,raw['open'][k]),int(raw['time'][k])
            elif j<end:
                bid,close_ts=raw['open'][j],int(raw['time'][j])
            else:
                bid,close_ts=raw['close'][end-1],int(raw['time'][end-1])+900
            pnl=2*(bid-.02-price)-.07+cost.swap(.02,True,ts,close_ts,.001,100)
            options.append((ts,close_ts,pnl,day.Index.year,day.entry))
        actual=[]
        for row in options:
            if row[4] and (not actual or row[0]>actual[-1][1]):
                actual.append(row)
        # Disjoint intervals and exact annual counts; reject infeasible draws.
        sims=[]
        counts=pd.Series([r[3] for r in actual]).value_counts().sort_index()
        pools={y:[r for r in options if r[3]==y] for y in counts.index}
        for _ in range(1000):
            sample=[]
            for year,count in counts.items():
                taken=0
                for idx in rng.permutation(len(pools[year])):
                    row=pools[year][idx]
                    if all(row[0]>s[1] or row[1]<s[0] for s in sample):
                        sample.append(row)
                        taken+=1
                        if taken==count: break
            if len(sample)==len(actual): sims.append(sum(r[2] for r in sample))
        p=np.array([r[2] for r in actual])
        result[first+'-'+last]=dict(trades=len(p),wins=int((p>0).sum()),pf=p[p>0].sum()/-p[p<0].sum(),
            net=p.sum(),control_draws=len(sims),control_median_net=float(np.median(sims)),
            fraction_controls_at_least_as_good=float(np.mean(np.array(sims)>=p.sum())))
    print(json.dumps(result,indent=2))
    Path('research/registry/connors_source_check.json').write_text(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
