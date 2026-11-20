"""Post-publication transfer of Baur's September/November gold finding."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from scripts.validation.full_metric_suite import ratios


def main():
    bars = load_master(('M15',),end=int(pd.Timestamp('2026-01-01',tz='UTC').timestamp())).m15
    d = pd.DataFrame(bars)
    d.index = pd.to_datetime(d.time,unit='s',utc=True)
    months = d.resample('MS').first().dropna()
    cost = SCENARIOS['realistic_ecn']
    out = {}
    for first,last in [('2013','2018'),('2019','2025')]:
        trades=[]
        for date,row in months.loc[first:last].iterrows():
            if date.month not in (9,11): continue
            nxt = months.loc[date+pd.offsets.MonthBegin()]
            gross = 2*(nxt.open-cost.ask(row.open,.001,row.spread)-.04)
            net = gross-.07+cost.swap(.02,True,int(row.time),int(nxt.time),.001,100)
            trades.append(dict(month=str(date.date()),net=net))
        summary=ratios(np.array([r['net'] for r in trades]),int(last)-int(first)+1)
        out[first+'-'+last]=dict(summary=summary,trades=trades)
        print(first,last,summary['net'],summary['profit_factor'],summary['win_pct'])
    Path('research/registry/published_gold_season.json').write_text(json.dumps(out,indent=2))


if __name__=='__main__':
    main()
