"""Causal independent adaptation of a public sweep/imbalance concept."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import monte_carlo_paths,drop_best_worst
from src.research.dated_results import save_result
from scripts.validation.full_metric_suite import ratios


def confirmed_pivot(rows, i):
    """Pivot index i-3 is knowable only at the close of index i."""
    if i<6:
        return None
    p = i-3
    neighbors = list(rows[p-3:p])+list(rows[p+1:i+1])
    if all(rows[p].high>r.high for r in neighbors):
        return (p,rows[p].high,-1)
    if all(rows[p].low<r.low for r in neighbors):
        return (p,rows[p].low,1)
    return None


def advance_zone(sweep,rows,i):
    """Return first fully confirmed zone; OB priority ends after three bars."""
    origin,side = sweep['origin'],sweep['side']
    if i<=origin+3 and i>0:
        now,prev = rows[i],rows[i-1]
        opposite = prev.close<prev.open if side==1 else prev.close>prev.open
        reversal = now.close>now.open if side==1 else now.close<now.open
        if opposite and reversal:
            return (prev.high,prev.low,i)
    if origin<=i-2<=origin+4 and sweep.get('fvg') is None:
        left,right = rows[i-2],rows[i]
        if side==1 and right.low-left.high>1:
            sweep['fvg'] = (right.low,left.high,i)
        elif side==-1 and left.low-right.high>1:
            sweep['fvg'] = (left.low,right.high,i)
    if i>=origin+3:
        return sweep.get('fvg')
    return None


def replay(frame,trend):
    cost = SCENARIOS['realistic_ecn']
    d = frame.copy()
    d['fast'] = d.close.ewm(span=20,adjust=False).mean()
    d['slow'] = d.close.ewm(span=50,adjust=False).mean()
    rows = list(d.itertuples())
    levels,searches,orders = [],[],[]
    position = None
    records = []
    diagnostics = dict(confirmed_pivots=0,sweeps=0,confirmed_zones=0,ambiguous_bars=0,
                       entry_bar_targets_deferred=0)
    day = None
    segment_start = 0
    for i,row in enumerate(rows):
        today = row.Index.date()
        minute = row.Index.hour*60+row.Index.minute
        spread = cost.spread_price(.001,row.spread)
        gap = i>0 and row.time!=rows[i-1].time+900

        def finish(price,when,reason):
            entry,side,stop,target,start = position
            pnl = 2*side*(price-entry)-cost.commission(.02)
            pnl += cost.swap(.02,side==1,start,when,.001,100)
            records.append(dict(time=int(when),pnl=float(pnl),reason=reason))

        if position and (today!=day or minute>=1380 or gap):
            side = position[1]
            finish(row.open+(spread if side==-1 else 0)-side*.02,int(row.time),'clock_or_gap')
            position = None
        if today!=day or gap:
            levels,searches,orders = [],[],[]
            segment_start = i
            day = today
        entered = False
        open_fill = False
        if position is None and minute<1365 and i>0:
            for order in orders:
                if not (order['known']<i<=order['expiry']):
                    continue
                side,limit,stop = order['side'],order['limit'],order['stop']
                prev = rows[i-1]
                if trend and not ((prev.close>prev.slow and prev.fast>rows[i-2].fast) if side==1
                                  else (prev.close<prev.slow and prev.fast<rows[i-2].fast)):
                    continue
                touched = row.low+spread<=limit if side==1 else row.high>=limit
                if touched:
                    opening = row.open+(spread if side==1 else 0)
                    entry = min(opening,limit) if side==1 else max(opening,limit)
                    risk = side*(entry-stop)
                    if risk<=0:
                        continue
                    position = (entry,side,stop,entry+side*2*risk,int(row.time))
                    entered = True
                    open_fill = row.open+spread<=limit if side==1 else row.open>=limit
                    break
            if entered:
                orders,searches = [],[]
        if position:
            entry,side,stop,target,start = position
            ask = spread if side==-1 else 0
            stop_hit = row.low<=stop if side==1 else row.high+ask>=stop
            target_hit = row.high>=target if side==1 else row.low+ask<=target
            diagnostics['ambiguous_bars'] += int(stop_hit and target_hit)
            if stop_hit:
                opening = row.open+ask
                price = min(opening,stop) if side==1 else max(opening,stop)
                finish(price-side*.02,int(row.time)+900,'stop')
                position = None
            elif target_hit:
                if entered and not open_fill:
                    diagnostics['entry_bar_targets_deferred'] += 1
                else:
                    finish(target,int(row.time)+900,'target')
                    position = None
        orders = [o for o in orders if i<o['expiry']]
        remaining = []
        for _,level,side in levels:
            swept = row.low<level and row.close>level if side==1 else row.high>level and row.close<level
            broken = row.close<level if side==1 else row.close>level
            if swept:
                searches.append(dict(origin=i,side=side,wick=row.low if side==1 else row.high))
                diagnostics['sweeps'] += 1
            elif not broken:
                remaining.append((i,level,side))
        levels = remaining
        pending = []
        for search in searches:
            zone = advance_zone(search,rows,i)
            if zone:
                top,bottom,known = zone
                side = search['side']
                limit = top if side==1 else bottom
                stop = min(search['wick'],bottom)-.5 if side==1 else max(search['wick'],top)+.5
                orders.append(dict(side=side,limit=limit,stop=stop,known=i,expiry=search['origin']+12))
                diagnostics['confirmed_zones'] += 1
            elif i<search['origin']+6:
                pending.append(search)
        searches = pending
        if i-segment_start>=6:
            pivot = confirmed_pivot(rows,i)
            if pivot:
                levels.append(pivot)
                diagnostics['confirmed_pivots'] += 1
    if position:
        side = position[1]
        finish(row.close+(spread if side==-1 else 0)-side*.02,int(row.time)+900,'boundary')
    return records,diagnostics


def main():
    f = pd.DataFrame(load_master(('M15',),end=1767225600).m15)
    f.index = pd.to_datetime(f.time.to_numpy(),unit='s',utc=True)
    report = {}
    for trend in (False,True):
        name = 'sweep_ema' if trend else 'sweep_raw'
        for first,last in [('2005','2011'),('2012','2018'),('2019','2025')]:
            records,diagnostics = replay(f.loc[first:last],trend)
            p = np.array([r['pnl'] for r in records])
            dates = pd.to_datetime([r['time']-1 for r in records],unit='s',utc=True)
            save_result(name+'_executable_open',pd.Series(p,index=dates),first+'-01-01',last+'-12-31',
                        specification='research/registry/PREREG_PublicSweep_2026-11-11.md',runner=__file__)
            stats = ratios(p,7)
            tr = [SimpleNamespace(net_pl=x) for x in p]
            stats.update(wins=int(sum(p>0)),diagnostics=diagnostics,
                         ablation=drop_best_worst(tr),monte_carlo=monte_carlo_paths(tr,5000))
            report[name+' '+first+'-'+last] = stats
            print(name,first,last,len(p),stats['wins'],stats['profit_factor'],stats['net'],flush=True)
    Path('research/registry/public_sweep_executable_open.json').write_text(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
