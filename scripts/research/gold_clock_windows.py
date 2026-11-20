"""Fixed XAUUSD clock windows with explicit quote and financing assumptions."""
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

ARMS = ('asia_long','london_overnight_long','london_intraday_short')


def schedule(index,arm):
    local = index if arm=='asia_long' else index.tz_convert('Europe/London')
    clock = (0,15) if arm=='asia_long' else ((15,15) if arm=='london_overnight_long' else (10,45))
    mask = (local.weekday<5)&(local.hour==clock[0])&(local.minute==clock[1])
    entries = np.flatnonzero(mask)
    due = []
    for i in entries:
        date = local[i].tz_localize(None).normalize()
        if arm=='asia_long':
            deadline = (date+pd.Timedelta(hours=8)).tz_localize('UTC')
        elif arm=='london_overnight_long':
            deadline = (date+pd.offsets.BDay(1)+pd.Timedelta(hours=10,minutes=30)).tz_localize('Europe/London')
        else:
            deadline = (date+pd.Timedelta(hours=14,minutes=45)).tz_localize('Europe/London')
        due.append(int(deadline.timestamp()))
    return entries,np.array(due,dtype=np.int64)


def replay(frame,arm,cost):
    entries,deadlines = schedule(frame.index,arm)
    raw = frame.to_records(index=False)
    timestamps = raw['time']
    records = []
    busy_until = -1
    side = -1 if arm=='london_intraday_short' else 1
    for i,due in zip(entries,deadlines):
        if timestamps[i]<busy_until:
            continue
        j = timestamps.searchsorted(due)
        first = raw[i]
        entry = first['open']+(cost.spread_price(.001,first['spread']) if side==1 else 0)+side*cost.slip(.001)
        if j<len(raw):
            end = raw[j]
            exit_time = int(end['time'])
            bid = end['open']
            boundary = False
        else:
            end = raw[-1]
            exit_time = int(end['time'])+900
            bid = end['close']
            boundary = True
        exit_price = bid+(cost.spread_price(.001,end['spread']) if side==-1 else 0)-side*cost.slip(.001)
        swap = cost.swap(.02,side==1,int(first['time']),exit_time,.001,100)
        pnl = 2*side*(exit_price-entry)-cost.commission(.02)+swap
        records.append(dict(entry_time=int(first['time']),exit_time=exit_time,pnl=float(pnl),swap=float(swap),
                            delayed_seconds=max(0,exit_time-int(due)),boundary=boundary))
        busy_until = exit_time
    return records


def main():
    f = pd.DataFrame(load_master(('M15',),end=1767225600).m15)
    f.index = pd.to_datetime(f.time.to_numpy(),unit='s',utc=True)
    base = SCENARIOS['realistic_ecn']
    scenarios = dict(base=base,stress=replace(base,spread_multiplier=2.,slippage_points=60.),
                     frictionless=replace(base,spread_multiplier=0.,slippage_points=0.,commission_per_lot_roundtrip=0.,enable_swap=False))
    report = {}
    rng = np.random.default_rng(15151030)
    for arm in ARMS:
        for first,last in [(2005,2011),(2012,2018),(2019,2025)]:
            frame = f.loc[str(first):str(last)]
            for scenario,cost in scenarios.items():
                records = replay(frame,arm,cost)
                p = np.array([r['pnl'] for r in records])
                dates = pd.to_datetime([r['exit_time']-1 for r in records],unit='s',utc=True)
                if scenario=='base':
                    save_result('clock_'+arm,pd.Series(p,index=dates),f'{first}-01-01',f'{last}-12-31',
                                specification='research/registry/PREREG_GoldClockWindows_2026-11-11.md',runner=__file__)
                stats = ratios(p,last-first+1)
                stats.update(wins=int(sum(p>0)),swap_usd=float(sum(r['swap'] for r in records)),
                             delayed_exits=sum(r['delayed_seconds']>0 for r in records),
                             maximum_exit_delay_seconds=max(r['delayed_seconds'] for r in records),
                             forced_boundary_exits=sum(r['boundary'] for r in records))
                if scenario=='base':
                    tr = [SimpleNamespace(net_pl=x) for x in p]
                    monthly = pd.Series(p,index=dates).groupby(dates.strftime('%Y-%m')).sum()
                    monthly = monthly.reindex(pd.period_range(str(first),f'{last}-12',freq='M').astype(str),fill_value=0.)
                    totals = rng.choice(monthly.to_numpy(),size=(5000,len(monthly)),replace=True).sum(axis=1)
                    stats.update(ablation=drop_best_worst(tr),monte_carlo=monte_carlo_paths(tr,5000),
                                 month_block_net_interval_95=np.percentile(totals,[2.5,97.5]).tolist())
                report[f'{arm} {first}-{last} {scenario}'] = stats
                print(arm,first,last,scenario,len(p),stats['profit_factor'],stats['net'],flush=True)
    Path('research/registry/gold_clock_windows.json').write_text(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
