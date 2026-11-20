"""Run with python -m scripts.research.us_asia_continuation."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import monte_carlo_paths, drop_best_worst
from scripts.validation.full_metric_suite import ratios
from src.research.metrics import bonferroni_correction


def main():
    end=int(pd.Timestamp('2026-01-01',tz='UTC').timestamp())
    raw=load_master(('M15',),end=end).m15
    f=pd.DataFrame(raw)
    f.index=pd.to_datetime(f.time,unit='s',utc=True)
    f['date']=f.index.normalize()
    def series(clock, field, prior=False):
        values=f.at_time(clock).set_index('date')[field]
        if prior: values.index+=pd.Timedelta(days=1)
        return values
    d=pd.concat(dict(us_open=series('14:30','open',True),us_close=series('23:45','close',True),
        entry=series('00:15','open'),spread=series('00:15','spread'),exit=series('08:00','open')),axis=1).dropna()
    d=d[(d.index.weekday>=1)&(d.index.weekday<=4)].copy()
    d['signal']=d.us_close>d.us_open
    cost=SCENARIOS['realistic_ecn']
    d['pnl']=2*(d.exit-d.entry-d.spread.map(lambda s:cost.spread_price(.001,s))-2*cost.slip(.001))-cost.commission(.02)
    rng=np.random.default_rng(7240)
    output={}
    for start,stop in [('2005','2011'),('2012','2018'),('2019','2025'),('2019','2024-07-21'),('2024-07-22','2025')]:
        era=d.loc[start:stop]
        trades=era.loc[era.signal,'pnl']
        null=np.zeros(2000)
        for _,year in era.groupby(era.index.year):
            count=int(year.signal.sum())
            null += [rng.choice(year.pnl.to_numpy(),count,replace=False).sum() for _ in null]
        report=ratios(trades.to_numpy(),(era.index[-1]-era.index[0]).days/365.25)
        records=[SimpleNamespace(net_pl=x) for x in trades]
        report.update(wins=int((trades>0).sum()),eligible=len(era),median_control_net=float(np.median(null)),
            bonferroni_p=bonferroni_correction((1+sum(null>=trades.sum()))/2001,5),
            monte_carlo=monte_carlo_paths(records,5000),ablation=drop_best_worst(records),
            deflated_sharpe=None,expected_max_sr=None,
            selection_adjustment_limitation='Full cross-study candidate return matrix unavailable.')
        output[f'{start} to {stop}']=report
        print(start,stop,len(trades),report['wins'],report['net'],report['profit_factor'],round(np.median(null)),report['bonferroni_p'])
    Path('research/registry/us_asia_continuation.json').write_text(json.dumps(output,indent=2))


if __name__=='__main__':
    main()
