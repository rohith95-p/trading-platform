"""Real-bar screens of two public VWAP/EMA gold mechanisms, with explicit deviations."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import monte_carlo_paths, drop_best_worst
from src.research.dated_results import save_result
from scripts.validation.full_metric_suite import ratios


def indicators(f, arm):
    f = f.copy()
    c,h,l,o = [f[k] for k in ('close','high','low','open')]
    for n in (20,50,200):
        f['ema'+str(n)] = c.ewm(span=n,adjust=False,min_periods=n).mean()
    tr = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    if arm == 'paper_core':
        atr = np.full(len(f),np.nan)
        atr[13] = tr.iloc[:14].mean()
        for i in range(14,len(f)):
            atr[i] = (13*atr[i-1]+tr.iloc[i])/14
        f['atr'] = atr
    else:
        f['atr'] = tr.rolling(14).mean()
    minute = f.index.hour*60+f.index.minute
    active = (minute>=810)&(minute<1200) if arm=='paper_core' else np.ones(len(f),dtype=bool)
    volume = f.tick_volume.where(active,0.)
    groups = f.index.normalize()
    f['vwap'] = (((h+l+c)/3*volume).groupby(groups).cumsum()/volume.groupby(groups).cumsum().replace(0,np.nan)).where(active)
    bullish = (c>f.ema200)&(c>f.vwap)&(c>f.ema50)
    bearish = (c<f.ema200)&(c<f.vwap)&(c<f.ema50)
    if arm == 'github_core':
        buy = bullish & (l.shift()<=f.ema50.shift()) & (c>o)
        sell = bearish & (h.shift()>=f.ema50.shift()) & (c<o)
    else:
        body = abs(c-o)
        lower = pd.concat([c,o],axis=1).min(axis=1)-l
        upper = h-pd.concat([c,o],axis=1).max(axis=1)
        bull_pin = (c>o)&(lower>=2*body)&(upper<=.5*lower)
        bear_pin = (c<o)&(upper>=2*body)&(lower<=.5*upper)
        bull_engulf = (c>o)&(c.shift()<o.shift())&(c>o.shift())&(o<c.shift())
        bear_engulf = (c<o)&(c.shift()>o.shift())&(c<o.shift())&(o>c.shift())
        common = ((c/f.ema200-1).abs()>.001)&(f.tick_volume>1.1*f.tick_volume.rolling(20).mean())&((h-l)>=.8*f.atr)
        buy = bullish & common & (pd.concat([l,l.shift()],axis=1).min(axis=1)<=f.ema50)&(bull_pin|bull_engulf)
        sell = bearish & common & (pd.concat([h,h.shift()],axis=1).max(axis=1)>=f.ema50)&(bear_pin|bear_engulf)
    f['signal'] = np.select([buy,sell],[1,-1],0)
    return f


def replay(f, arm):
    cost = SCENARIOS['realistic_ecn']
    position = None
    pending = None
    exit_pending = False
    records = []
    ambiguous = 0
    for row in f.itertuples():
        spread = cost.spread_price(.001,row.spread)
        minute = row.Index.hour*60+row.Index.minute

        def finish(price, when, reason):
            start,entry,side,stop,target,risk = position
            pnl = 2*side*(price-entry)-cost.commission(.02)
            pnl += cost.swap(.02,side==1,start,when,.001,100)
            records.append(dict(time=int(when),pnl=float(pnl),reason=reason))

        exited = False
        if position and (exit_pending or (arm=='paper_core' and (minute>=1200 or minute<810))):
            side = position[2]
            finish(row.open+(spread if side==-1 else 0)-side*.02,int(row.time),'close_signal_or_session')
            position = None
            exited = True
        exit_pending = False
        if pending and not position and not exited:
            side,stop_source,atr,signal_time = pending
            active = arm!='paper_core' or 810<=minute<1200
            if row.time==signal_time+900 and active:
                entry = row.open+(spread if side==1 else 0)+side*.02
                stop = stop_source if arm=='paper_core' else entry-side*1.5*atr
                risk = side*(entry-stop)
                if risk>0:
                    target = entry+side*3*risk if arm=='paper_core' else side*np.inf
                    position = (int(row.time),entry,side,stop,target,risk)
        pending = None
        if position:
            start,entry,side,stop,target,risk = position
            ask = spread if side==-1 else 0
            stop_hit = row.low<=stop if side==1 else row.high+ask>=stop
            target_hit = row.high>=target if side==1 else row.low+ask<=target
            ambiguous += int(stop_hit and target_hit)
            if stop_hit:
                opening = row.open+ask
                price = min(opening,stop) if side==1 else max(opening,stop)
                finish(price-side*.02,int(row.time)+900,'stop')
                position = None
                exited = True
            elif target_hit:
                finish(target-side*.02,int(row.time)+900,'target')
                position = None
                exited = True
            else:
                floating = side*(row.close+ask-entry)
                trail = row.ema20 if arm=='paper_core' and floating>=2.5*risk else row.ema50
                exit_pending = row.close<trail if side==1 else row.close>trail
        if not position and not exited and row.signal and np.isfinite(row.atr):
            side = int(row.signal)
            stop = row.low-.5*row.atr if side==1 else row.high+.5*row.atr
            pending = (side,stop,row.atr,int(row.time))
    if position:
        side = position[2]
        finish(row.close+(spread if side==-1 else 0)-side*.02,int(row.time)+900,'boundary')
    return records,ambiguous


def main():
    f = pd.DataFrame(load_master(('M15',),end=1767225600).m15)
    f.index = pd.to_datetime(f.time.to_numpy(),unit='s',utc=True)
    report = {}
    for arm in ('github_core','paper_core'):
        d = indicators(f,arm)
        for first,last in [('2005','2011'),('2012','2018'),('2019','2025')]:
            records,ambiguous = replay(d.loc[first:last],arm)
            p = np.array([r['pnl'] for r in records])
            dates = pd.to_datetime([r['time']-1 for r in records],unit='s',utc=True)
            save_result('vwap_ema_'+arm,pd.Series(p,index=dates),first+'-01-01',last+'-12-31',
                        specification='research/registry/PREREG_VWAPEMA_2026-11-11.md',runner=__file__)
            stats = ratios(p,7)
            tr = [SimpleNamespace(net_pl=x) for x in p]
            stats.update(wins=int(sum(p>0)),ambiguous_bars=ambiguous,
                         ablation=drop_best_worst(tr),monte_carlo=monte_carlo_paths(tr,5000))
            report[arm+' '+first+'-'+last] = stats
            print(arm,first,last,len(p),stats['wins'],stats['profit_factor'],stats['net'],flush=True)
    Path('research/registry/vwap_ema.json').write_text(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
