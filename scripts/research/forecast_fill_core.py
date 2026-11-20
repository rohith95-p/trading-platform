"""Explicit fixed-assumption XAUUSD adaptation, not a paper replication."""
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


def prepare(f, *, last_year=2025):
    f = f.copy()
    clock = f.index.tz_convert('America/New_York').tz_localize(None)+pd.Timedelta(hours=7)
    f['session'] = clock.normalize()
    d = f.groupby('session').agg(open=('open','first'),high=('high','max'),low=('low','min'),
                                close=('close','last'),last_time=('time','last'))
    smooth = np.log(d.close).ewm(alpha=.1,adjust=False).mean()
    d['slope'] = smooth.diff()
    d['momentum'] = (d.close>d.close.shift(50)).astype(int)
    tr = pd.concat([d.high-d.low,(d.high-d.close.shift()).abs(),(d.low-d.close.shift()).abs()],axis=1).max(axis=1)
    d['atr'] = tr.rolling(14).mean()
    d['probability'] = np.nan
    freezes = []
    for year in range(2015,last_year+1):
        for month in (1,7):
            freeze = pd.Timestamp(year=year,month=month,day=1)
            end = freeze+pd.DateOffset(months=6)
            train = d.loc[(d.index<freeze)&(d.index>=freeze-pd.DateOffset(years=10)),'slope'].dropna()
            if len(train)<2000 or train.std(ddof=1)<=0:
                continue
            mask = (d.index>=freeze)&(d.index<end)
            z = (d.loc[mask,'slope']-train.mean())/train.std(ddof=1)
            d.loc[mask,'probability'] = .6*((z.clip(-3,3)+3)/6)+.4*d.loc[mask,'momentum']
            freezes.append(dict(freeze=str(freeze.date()),train_last_session=str(train.index[-1].date()),
                                train_count=len(train),mean=float(train.mean()),sd=float(train.std(ddof=1))))
    # Two-session delay: a completed signal, one intervening complete session, then open.
    d['enter'] = ((d.probability>=.52)&(d.slope>0)).shift(2,fill_value=False)
    d['leave'] = (d.probability<.5).shift(2,fill_value=False)
    d['entry_atr'] = d.atr.shift(2)
    d['prior_atr'] = d.atr.shift()
    d['prior_high'] = d.high.shift()
    return f,d,freezes


def replay(f,d):
    cost = SCENARIOS['realistic_ecn']
    position = None
    day = None
    records = []
    session_number = -1
    for row in f.itertuples():
        spread = cost.spread_price(.001,row.spread)

        def finish(price,when,reason):
            entry,start,stop,peak,age = position
            pnl = 2*(price-entry)-cost.commission(.02)+cost.swap(.02,True,start,when,.001,100)
            records.append(dict(time=int(when),entry_time=int(start),pnl=float(pnl),reason=reason))

        if row.session!=day:
            day = row.session
            session_number += 1
            signal = d.loc[day]
            if position:
                entry,start,stop,peak,age = position
                peak = max(peak,signal.prior_high)
                stop = max(stop,peak-1.5*signal.prior_atr)
                position = (entry,start,stop,peak,age)
                if signal.leave or session_number-age>=30:
                    finish(row.open-cost.slip(.001),int(row.time),'signal_or_age')
                    position = None
            if position is None and signal.enter and np.isfinite(signal.entry_atr):
                entry = row.open+spread+cost.slip(.001)
                position = (entry,int(row.time),entry-2*signal.entry_atr,row.open,session_number)
        if position and row.low<=position[2]:
            finish(min(row.open,position[2])-cost.slip(.001),int(row.time)+900,'stop')
            position = None
    if position:
        finish(row.close-cost.slip(.001),int(row.time)+900,'boundary')
    return records


def main():
    f = pd.DataFrame(load_master(('M15',),end=1767225600).m15)
    f.index = pd.to_datetime(f.time.to_numpy(),unit='s',utc=True)
    f,d,freezes = prepare(f)
    report = dict(freezes=freezes,results={})
    all_pnl = []
    for first,last in [(2015,2018),(2019,2021),(2022,2025)]:
        frame = f.loc[(f.session>=str(first))&(f.session<f'{last+1}-01-01')]
        records = replay(frame,d)
        p = np.array([r['pnl'] for r in records])
        dates = pd.to_datetime([r['time']-1 for r in records],unit='s',utc=True)
        all_pnl.append(pd.Series(p,index=dates))
        stats = ratios(p,last-first+1)
        tr = [SimpleNamespace(net_pl=x) for x in p]
        stats.update(wins=int(sum(p>0)),ablation=drop_best_worst(tr),monte_carlo=monte_carlo_paths(tr,5000))
        report['results'][f'{first}-{last}'] = dict(metrics=stats,trades=records)
        print(first,last,len(p),stats['wins'],stats['profit_factor'],stats['net'],flush=True)
    # Use one continuous UTC coverage declaration: adjacent FX-session eras can
    # share a calendar date even though their underlying minutes do not overlap.
    covered = f.loc[(f.session>='2015-01-01')&(f.session<'2026-01-01')]
    save_result('forecast_fill_core',pd.concat(all_pnl),str(covered.index[0].date()),
                str((covered.index[-1]+pd.Timedelta(minutes=14,seconds=59)).date()),
                specification='research/registry/PREREG_ForecastFillCore_2026-11-11.md',runner=__file__)
    Path('research/registry/forecast_fill_core.json').write_text(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
