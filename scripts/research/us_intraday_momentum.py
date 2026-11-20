"""Run with python -m scripts.research.us_intraday_momentum."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import monte_carlo_paths,drop_best_worst
from src.research.metrics import bonferroni_correction
from src.research.dated_results import save_result
from scripts.validation.full_metric_suite import ratios


def main():
    raw=load_master(('M15',),end=1767225600).m15
    f=pd.DataFrame(raw)
    f.index=pd.to_datetime(f.time.to_numpy(),unit='s',utc=True).tz_convert('America/New_York')
    def at(clock,field):
        s=f.at_time(clock)[field].copy()
        s.index=s.index.tz_localize(None).normalize()
        return s
    d=pd.concat(dict(signal=at('08:45','close')-at('08:30','open'),entry=at('15:30','open'),
        exit=at('16:00','open'),spread_in=at('15:30','spread'),spread_out=at('16:00','spread')),axis=1).dropna()
    d=d[d.signal!=0]
    cost=SCENARIOS['realistic_ecn']
    move=d.exit-d.entry
    d['buy']=2*(move-d.spread_in.map(lambda s:cost.spread_price(.001,s))-.04)-.07
    d['sell']=2*(-move-d.spread_out.map(lambda s:cost.spread_price(.001,s))-.04)-.07
    report={}
    rng=np.random.default_rng(8301530)
    for first,last in [('2005','2011'),('2012','2018'),('2019','2025')]:
        era=d.loc[first:last]
        p=np.where(era.signal>0,era.buy,era.sell)
        save_result('us_intraday_momentum',pd.Series(p,index=era.index),first+'-01-01',last+'-12-31',
                    specification='research/registry/PREREG_USIntradayMomentum_2026-11-11.md',runner=__file__)
        null=np.zeros(2000)
        for _,year in era.groupby(era.index.year):
            masks=np.array([rng.permutation(year.signal.to_numpy()>0) for _ in null])
            null+=np.where(masks,year.buy.to_numpy(),year.sell.to_numpy()).sum(axis=1)
        stats=ratios(p,7)
        records=[SimpleNamespace(net_pl=v) for v in p]
        stats.update(wins=int((p>0).sum()),median_random=float(np.median(null)),
                     adjusted_p=bonferroni_correction((1+sum(null>=p.sum()))/2001,3),
                     monte_carlo=monte_carlo_paths(records,5000),ablation=drop_best_worst(records))
        report[first+'-'+last]=stats
        print(first,last,len(p),stats['wins'],stats['profit_factor'],stats['net'],stats['median_random'])
    Path('research/registry/us_intraday_momentum.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
