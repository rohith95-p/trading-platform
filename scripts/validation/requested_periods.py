"""Exact requested-date price-rule replays plus explicitly separate archived cash inventory."""
import os
os.environ['ULTRA_DISABLE_ALERTS']='1'
os.environ['ULTRA_NO_TRIAL_LEDGER']='1'
import dataclasses
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from scripts.validation.full_metric_suite import ratios
from scripts.research import public_supertrend,public_gold_rules,turtle_s2,gold_clock_windows,forecast_fill_core

ROOT=Path('research/results/requested_periods_2026-11-11')
PERIODS={'2019-2024':('2019-01-01','2025-01-01'),'2026_available':('2026-01-01','2026-10-30')}


def stats(records,first,end):
    times=[int(x[0]) for x in records];cash=np.array([float(x[1]) for x in records])
    a=int(pd.Timestamp(first,tz='UTC').timestamp());b=int(pd.Timestamp(end,tz='UTC').timestamp())
    if any(t<a or t>b for t in times):raise ValueError('Out-of-period trade')
    result=ratios(cash,(b-a)/(365.25*86400))
    result['annual_net']={str(y):round(sum(p for t,p in records if pd.Timestamp(t-1 if t==b else t,unit='s',tz='UTC').year==y),2) for y in range(int(first[:4]),int(end[:4])+(end[5:]!='01-01'))}
    result['exit_cash_records']=[dict(time=int(t),pnl=float(p)) for t,p in records]
    return result


def prices():
    ROOT.mkdir(parents=True,exist_ok=True)
    bars=load_master(('M15',),end=int(pd.Timestamp('2026-10-30',tz='UTC').timestamp()))
    f=pd.DataFrame(bars.m15);f.index=pd.to_datetime(f.time.to_numpy(),unit='s',utc=True)
    cost=SCENARIOS['realistic_ecn'];prepared_turtle=turtle_s2.prepare(f)
    forecast,days,freezes=forecast_fill_core.prepare(f,last_year=2026)
    report=dict(periods=PERIODS,costs=cost.descriptor(),results={},
        input_m15_sha256=hashlib.sha256(bars.m15.tobytes()).hexdigest(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),freezes=freezes,
        caveat='Fixed .02lot base costs; M15/coarser path, no Atlas account gates; exact start-flat/end-liquidated research windows, not live profitability certification.')
    def save(name,period,records):
        report['results'].setdefault(name,{})[period]=stats(records,*PERIODS[period])
        c=report['results'][name][period];print(name,period,c['trades'],c['net'],c['profit_factor'],flush=True)
        (ROOT/'price_replays.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    def subset(frame,period):
        a,b=PERIODS[period];return frame[(frame.index>=a)&(frame.index<b)]
    for period in PERIODS:
        for units in (1,4):
            records,_=turtle_s2.replay(subset(prepared_turtle,period),units,cost)
            save('turtle_s2_'+str(units)+'unit_m15',period,[(x['time'],x['pnl']) for x in records])
        for arm in gold_clock_windows.ARMS:
            records=gold_clock_windows.replay(subset(f,period),arm,cost)
            save('clock_'+arm,period,[(x['exit_time'],x['pnl']) for x in records])
        records=forecast_fill_core.replay(subset(forecast,period),days)
        save('forecast_fill_core',period,[(x['time'],x['pnl']) for x in records])
    for timeframe in ['1h','4h']:
        d=f.resample(timeframe).agg(dict(time='first',open='first',high='max',low='min',close='last',spread='first')).dropna()
        d=public_supertrend.indicators(d)
        for period in PERIODS:save('supertrend_'+timeframe,period,public_supertrend.replay(subset(d,period)))
    for freq,name in [('2h','rsi2_r3_2h'),('D','rsi2_daily_pullback'),('MS','faber_monthly_sma10')]:
        d=public_gold_rules.signals(f,freq)
        for period in PERIODS:
            save(name,period,public_gold_rules.simulate(subset(d,period),subset(f,period).iloc[-1],cost))
    # Same fixed UTC US-to-Asia rule as scripts/research/us_asia_continuation.py.
    def clock_series(clock,field,prior=False):
        selected=f.at_time(clock)
        series=pd.Series(selected[field].to_numpy(),index=selected.index.normalize())
        if prior:series.index+=pd.Timedelta(days=1)
        return series
    days=pd.concat(dict(us_open=clock_series('14:30','open',True),us_close=clock_series('23:45','close',True),
        entry=clock_series('00:15','open'),spread=clock_series('00:15','spread'),exit=clock_series('08:00','open')),axis=1).dropna()
    days=days[(days.index.weekday>=1)&(days.index.weekday<=4)&(days.us_close>days.us_open)]
    for period in PERIODS:
        selected=subset(days,period)
        cash=2*(selected.exit-selected.entry-selected.spread.map(lambda s:cost.spread_price(.001,s))-2*cost.slip(.001))-cost.commission(.02)
        save('us_asia_continuation',period,[(int((ts+pd.Timedelta(hours=8)).timestamp()),pnl) for ts,pnl in cash.items()])


def portfolio():
    from src.backtesting.engine import BacktestEngine,EngineConfig
    from src.strategies.portfolio_atlas import PORTFOLIO
    os.environ['ULTRA_TRADE_24H']='1'
    a=int(pd.Timestamp('2019-01-01',tz='UTC').timestamp());b=int(pd.Timestamp('2025-01-01',tz='UTC').timestamp())
    bars=load_master(('M15','M1','D1'),start=a,end=b)
    config=EngineConfig.live_parity_preset(sizing_mode='fixed',fixed_lots=.02,starting_balance=5000.,max_concurrent=3,max_same_direction=3,history_bars=7500,protect_profit=False,m1_policy='skip')
    result=BacktestEngine(bars,SCENARIOS['realistic_ecn'],config).run([c() for c in PORTFOLIO],a,b)
    trades=[dataclasses.asdict(t) for t in result.trades]
    groups={}
    for name in sorted({t['strategy'] for t in trades}):
        groups[name]=stats([(t['exit_time'],t['net_pl']) for t in trades if t['strategy']==name],'2019-01-01','2025-01-01')
        print('PORTFOLIO',name,groups[name]['net'],flush=True)
    (ROOT/'portfolio_2019_2024.json').write_text(json.dumps(dict(config=config.as_dict(),results=groups,trades=trades,diagnostics=result.diagnostics,caveat='Contributions within shared four-strategy portfolio, not standalone replays; no full Atlas account-rule enforcement.'),indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--portfolio',action='store_true');args=parser.parse_args()
    ROOT.mkdir(parents=True,exist_ok=True)
    portfolio() if args.portfolio else prices()
