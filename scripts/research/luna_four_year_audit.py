"""Measure a continuous Luna MT5 report against its own quote feed.

Monthly starts are ledger replays: each gets $5,000, starts flat and follows the
same subsequent fills. They stop at the first evaluation pass or breach.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.luna_six_month_audit import portfolio_states, read_report, stamp

INITIAL = 5000.
DTYPE = [('ms','<i8'), ('bid','<f8'), ('ask','<f8')]


def analyze(report, cache, output):
    metrics, deals = read_report(report)
    filled, longs, shorts, cash, balances = portfolio_states(deals)
    months = pd.period_range('2022-11', '2026-10', freq='M')
    years, attempts, active = {}, [], []
    day_number = None
    last_equity = INITIAL
    tick_count = 0
    floating_max = 0.

    entries = np.array([int(d['ts']*1000) for d in deals if d['action']=='in'], dtype='int64')
    exits = [d for d in deals if d['action']=='out']
    end_ms = int(pd.Timestamp('2026-11-01',tz='UTC').timestamp()*1000)
    for i, month in enumerate(months):
        ticks = np.memmap(cache / f'ticks{i+3}.bin', dtype=DTYPE, mode='r')
        tick_count += len(ticks)
        year = str(month.year)
        annual = years.setdefault(year, dict(start=last_equity, peak=last_equity, drawdown=0., drawdown_pct=0.))
        start_ms = int(month.start_time.tz_localize('UTC').timestamp()*1000)
        state = filled.searchsorted(start_ms, side='left')-1
        # A fresh account does not inherit a position from the previous month.
        while state+1 < len(filled) and (longs[state] or shorts[state]):
            state += 1
        first_ms = max(int(filled[state]), start_ms)
        attempt = dict(start=str(month), first_ms=first_ms, offset=INITIAL-balances[state],
                       peak=INITIAL, result='open')
        times_opened = np.r_[start_ms, entries[entries>=first_ms], end_ms]
        gaps = np.flatnonzero(np.diff(times_opened)>=30*86400000)
        attempt['inactivity_ms'] = int(times_opened[gaps[0]]+30*86400000) if len(gaps) else end_ms+1
        attempt['target_ms'] = next((int(d['ts']*1000) for d in exits
                                     if d['ts']*1000>=first_ms and d['balance']+attempt['offset']>=5150),end_ms+1)
        attempts.append(attempt)
        active.append(attempt)
        for lo in range(0,len(ticks),250000):
            q = ticks[lo:lo+250000]
            t = q['ms']
            p = filled.searchsorted(t, side='right')-1
            eq = cash[p]+longs[p]*q['bid']-shorts[p]*q['ask']
            bal = balances[p]
            peak = np.maximum.accumulate(np.maximum(annual['peak'],eq))
            annual['drawdown'] = max(annual['drawdown'],float((peak-eq).max()))
            annual['drawdown_pct'] = max(annual['drawdown_pct'],float(((peak-eq)/peak).max()*100))
            annual['peak'] = float(peak[-1])
            annual['end'] = float(eq[-1])
            floating_max = max(floating_max,float((bal-eq).max()))
            segment = np.r_[0,np.flatnonzero(np.diff(t//86400000))+1,len(t)]
            for a,b in zip(segment[:-1],segment[1:]):
                current = t[a]//86400000
                if current!=day_number:
                    anchor=last_equity
                    day_number=current
                for attempt in list(active):
                    begin=max(a,int(t.searchsorted(attempt['first_ms'])))
                    if begin>=b: continue
                    window=t[begin:b]
                    offset=attempt['offset']
                    e=eq[begin:b]+offset
                    peaks=np.maximum.accumulate(np.maximum(attempt['peak'],e))

                    rules={'daily breach': e<(anchor+offset)*.95, 'trailing breach':e<peaks*.90,
                           'inactivity breach':window>=attempt['inactivity_ms'],
                           'target':window>=attempt['target_ms']}
                    found=[(int(np.argmax(mask)),name) for name,mask in rules.items() if mask.any()]
                    if found:
                        j,name=min(found,key=lambda v:v[0])
                        when = {'target': attempt['target_ms'], 'inactivity breach': attempt['inactivity_ms']}.get(name,int(window[j]))
                        attempt.update(result=name,time=stamp(when),equity=round(float(e[j]),2))
                        active.remove(attempt)
                    attempt['peak']=float(peaks[-1])
                last_equity=float(eq[b-1])
    assert tick_count==int(metrics['Ticks'].replace(' ','')),(tick_count,metrics)
    for y,ann in years.items():
        ds=[d for d in deals if pd.Timestamp(d['ts'],unit='s',tz='UTC').year==int(y)]
        closed=[d['profit']+d['swap']+d['fee'] for d in ds if d['action']=='out']
        gp=sum(v for v in closed if v>0)
        gl=-sum(v for v in closed if v<0)
        ann.update(trades=len(closed),wins=sum(v>0 for v in closed),profit=sum(d['profit']+d['swap']+d['fee'] for d in ds),
                   equity_profit=ann['end']-ann['start'],pf=gp/gl if gl else None,
                   without_best=sum(closed)-max(closed,default=0))
    booked={}
    for d in deals:
        day=stamp(int(d['ts']*1000))[:10]
        booked[day]=booked.get(day,0.)+d['profit']+d['fee']+d['swap']
    qualifying={day:round(value,2) for day,value in booked.items() if round(value,2)>=25.}
    for attempt in attempts:
        if attempt['result']=='target':
            attempt['subsequent_qualifying_days_before_deductions']=sum(day>attempt['time'][:10] for day in qualifying)
    result=dict(qualifying_days_before_deductions=qualifying,metrics=metrics,years=years,monthly_attempts=attempts,maximum_floating_loss=floating_max,
                maximum_order_lots=max((d['volume'] for d in deals if d['action']=='in'),default=0),
                ticks=tick_count)
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for field in ['report','cache','output']: p.add_argument(field,type=Path)
    analyze(**vars(p.parse_args()))
