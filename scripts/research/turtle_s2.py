"""Gold-only System Two adaptations with channel exits and explicit quote costs."""
from dataclasses import replace
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


def prepare(f):
    f = f.copy()
    clock = f.index.tz_convert('America/New_York').tz_localize(None)+pd.Timedelta(hours=7)
    f['session'] = clock.normalize()
    d = f.groupby('session').agg(high=('high','max'),low=('low','min'),close=('close','last'))
    tr = pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
    n = np.full(len(d),np.nan)
    n[19] = tr.iloc[:20].mean()
    for i in range(20,len(d)):
        n[i] = (19*n[i-1]+tr.iloc[i])/20
    features = pd.DataFrame(dict(n_value=n,entry_high=d.high.rolling(55).max()+.001,
                                 entry_low=d.low.rolling(55).min()-.001,
                                 exit_high=d.high.rolling(20).max()+.001,
                                 exit_low=d.low.rolling(20).min()-.001),index=d.index).shift(1)
    return f.join(features,on='session')


def replay(frame,max_units,cost,*,bar_seconds=900):
    units = []
    side,stop,n_value = 0,None,None
    records = []
    diagnostics = dict(ambiguous_entry_bars=0,new_unit_stop_bars=0,unit_fills=0)
    for row in frame.itertuples():
        spread = cost.spread_price(.001,row.spread)
        ask = spread if side==-1 else 0

        def finish(price,when,reason):
            swap = sum(cost.swap(.02,side==1,start,when,.001,100) for _,start in units)
            pnl = sum(2*side*(price-entry)-cost.commission(.02) for entry,_ in units)+swap
            records.append(dict(time=int(when),entry_time=units[0][1],pnl=float(pnl),swap=float(swap),
                                units=len(units),side=side,reason=reason,
                                fills=[dict(price=float(price),time=int(ts)) for price,ts in units]))

        def active_stop():
            return max(stop,row.exit_low) if side==1 else min(stop,row.exit_high)

        if units:
            level = active_stop()
            hit = row.low<=level if side==1 else row.high+spread>=level
            if hit:
                opening = row.open+ask
                exit_price = min(opening,level) if side==1 else max(opening,level)
                finish(exit_price-side*cost.slip(.001),int(row.time)+bar_seconds,'stop_or_channel')
                units = []
                continue
        if not units:
            if not np.isfinite(row.entry_high) or not np.isfinite(row.n_value) or row.n_value<=0:
                continue
            up,down = row.high>=row.entry_high,row.low<=row.entry_low
            if up and down:
                if row.open>=row.entry_high:
                    side = 1
                elif row.open<=row.entry_low:
                    side = -1
                else:
                    diagnostics['ambiguous_entry_bars'] += 1
                    continue
            elif up or down:
                side = 1 if up else -1
            else:
                continue
            trigger = row.entry_high if side==1 else row.entry_low
            bid = max(row.open,trigger) if side==1 else min(row.open,trigger)
            entry = bid+(spread if side==1 else 0)+side*cost.slip(.001)
            units = [(entry,int(row.time))]
            n_value = row.n_value
            stop = entry-side*2*n_value
            diagnostics['unit_fills'] += 1
            new_unit = True
        else:
            new_unit = False
        while len(units)<max_units:
            trigger = units[-1][0]+side*.5*n_value
            hit = row.high>=trigger if side==1 else row.low<=trigger
            if not hit:
                break
            bid = max(row.open,trigger) if side==1 else min(row.open,trigger)
            entry = bid+(spread if side==1 else 0)+side*cost.slip(.001)
            units.append((entry,int(row.time)))
            stop = max(stop,entry-2*n_value) if side==1 else min(stop,entry+2*n_value)
            diagnostics['unit_fills'] += 1
            new_unit = True
        if new_unit:
            level = active_stop()
            hit = row.low<=level if side==1 else row.high+spread>=level
            if hit:
                diagnostics['new_unit_stop_bars'] += 1
                opening = row.open+(spread if side==-1 else 0)
                exit_price = min(opening,level) if side==1 else max(opening,level)
                finish(exit_price-side*cost.slip(.001),int(row.time)+bar_seconds,'new_unit_stop_or_channel')
                units = []
    if units:
        finish(row.close+(spread if side==-1 else 0)-side*cost.slip(.001),int(row.time)+bar_seconds,'boundary')
    return records,diagnostics


def main():
    f = pd.DataFrame(load_master(('M15',),end=1767225600).m15)
    f.index = pd.to_datetime(f.time.to_numpy(),unit='s',utc=True)
    f = prepare(f)
    base = SCENARIOS['realistic_ecn']
    scenarios = dict(base=base,stress=replace(base,spread_multiplier=2.,slippage_points=60.),
                     frictionless=replace(base,spread_multiplier=0.,slippage_points=0.,commission_per_lot_roundtrip=0.,enable_swap=False))
    report = {}
    for max_units in (1,4):
        for first,last in [(2005,2011),(2012,2018),(2019,2025)]:
            for scenario,cost in scenarios.items():
                records,diagnostics = replay(f.loc[str(first):str(last)],max_units,cost)
                p = np.array([r['pnl'] for r in records])
                if scenario=='base':
                    dates = pd.to_datetime([r['time']-1 for r in records],unit='s',utc=True)
                    save_result('turtle_s2_'+str(max_units)+'unit',pd.Series(p,index=dates),f'{first}-01-01',f'{last}-12-31',
                                specification='research/registry/PREREG_TurtleS2_2026-11-11.md',runner=__file__)
                stats = ratios(p,7)
                stats.update(wins=int(sum(p>0)),swap_usd=float(sum(r['swap'] for r in records)),
                             diagnostics=diagnostics,observation='basket_cash_pnl',
                             maximum_units=max(r['units'] for r in records))
                if scenario=='base':
                    tr = [SimpleNamespace(net_pl=x) for x in p]
                    stats.update(ablation=drop_best_worst(tr),monte_carlo=monte_carlo_paths(tr,5000),basket_records=records)
                report[f'{max_units}unit {first}-{last} {scenario}'] = stats
                print(max_units,first,last,scenario,len(p),stats['profit_factor'],stats['net'],flush=True)
    Path('research/registry/turtle_s2.json').write_text(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
