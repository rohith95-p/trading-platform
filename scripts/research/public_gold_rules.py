"""Run with python -m scripts.research.public_gold_rules."""
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import monte_carlo_paths, drop_best_worst
from src.research.metrics import deflated_sharpe_ratio, expected_max_sr, bonferroni_correction
from scripts.validation.full_metric_suite import ratios


def signals(frame, freq):
    bars = frame.resample(freq).agg(dict(open='first', close='last', spread='first',time='first')).dropna()
    close = bars.close
    if freq == 'MS':
        average = close.rolling(10).mean()
        enter, leave = close > average, close < average
    else:
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=.5,adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=.5,adjust=False).mean()
        rsi = 100*gain/(gain+loss)
        enter = (close > close.rolling(200).mean()) & (rsi < 10)
        leave = rsi > 70
        if freq == '2h':
            enter &= (rsi < rsi.shift().rolling(3).min()) & (rsi.shift(2)<60)
        else:
            leave |= close > close.rolling(5).mean()
    return bars.assign(enter=enter.shift(1,fill_value=False),leave=leave.shift(1,fill_value=False))


def simulate(bars, final, cost):
    trades = []
    entry = None
    for row in bars.itertuples():
        if entry is None:
            if row.enter:
                entry = (int(row.time),cost.ask(row.open,.001,row.spread)+cost.slip(.001))
            continue
        if row.leave:
            trades.append((entry,int(row.time),row.open))
            entry = None
    if entry is not None:
        trades.append((entry,int(final.time)+900,final.close))
    return [(ts,2*(bid-cost.slip(.001)-price)-cost.commission(.02)+
             cost.swap(.02,True,start,ts,.001,100)) for (start,price),ts,bid in trades]


def main():
    end = int(pd.Timestamp('2026-01-01',tz='UTC').timestamp())
    raw = load_master(('M15',),end=end).m15
    frame = pd.DataFrame(raw[['time','open','close','spread']])
    frame.index = pd.to_datetime(frame.time,unit='s',utc=True)
    cost = SCENARIOS['realistic_ecn']
    report = {}
    for first,last in [('2005','2011'),('2012','2018'),('2019','2025')]:
        observations = {}
        for freq in ['2h','D','MS']:
            bars = signals(frame, freq).loc[first:last]
            observations[freq] = simulate(bars,frame.loc[first:last].iloc[-1],cost)
        series = {k:np.array([x[1] for x in rows]) for k,rows in observations.items()}
        variance = np.var([x.mean()/x.std() for x in series.values() if len(x)>1],ddof=1)
        for name,x in series.items():
            if len(x)<3:
                report[first+' '+name] = {'trades':len(x),'insufficient':True}
                continue
            stats = ratios(x,int(last)-int(first)+1)
            tr = [SimpleNamespace(net_pl=v) for v in x]
            stats.update(wins=int(sum(x>0)),expected_max_sr=expected_max_sr(3,variance),
                         dsr_three_trial_sensitivity=deflated_sharpe_ratio(x,3,variance),
                         bonferroni_p_win_rate_above_half=bonferroni_correction(
                             binomtest(int(sum(x>0)),len(x),.5,alternative='greater').pvalue,9),
                         monte_carlo=monte_carlo_paths(tr,5000),ablation=drop_best_worst(tr))
            report[first+' '+name]=stats
            print(first,name,len(x),stats['wins'],stats['profit_factor'],stats['net'],flush=True)
    Path('research/registry/public_gold_rules_metrics.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
