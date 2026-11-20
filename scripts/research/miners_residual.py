"""Run with python -m scripts.research.miners_residual."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
import requests
from src.backtesting.costs import SCENARIOS
from src.backtesting.master import load_master
from src.backtesting.metrics import monte_carlo_paths, drop_best_worst
from src.research.metrics import bonferroni_correction
from src.research.dated_results import save_result
from scripts.validation.full_metric_suite import ratios


def close(ticker):
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+ticker
    response=requests.get(url,params=dict(period1=1147824000,period2=1767225600,interval='1d'),
                          headers={'User-Agent':'Mozilla/5.0'},timeout=30)
    response.raise_for_status()
    payload=response.json()['chart']['result'][0]
    dates=pd.to_datetime(payload['timestamp'],unit='s',utc=True).tz_convert('America/New_York').tz_localize(None).normalize()
    return pd.Series(payload['indicators']['quote'][0]['close'],index=dates,name=ticker)


def main():
    archive=Path('research/data/miners_factor_closes_through_2025.csv')
    if not archive.exists():
        prices=pd.concat([close(t) for t in ('GDX','GLD','SPY')],axis=1).sort_index().loc[:'2025'].dropna()
        prices.to_csv(archive)
    prices=pd.read_csv(archive,index_col=0,parse_dates=True)
    returns=np.log(prices).diff().dropna()
    factors=np.column_stack((np.ones(len(returns)),returns[['GLD','SPY']]))
    miners=returns.GDX.to_numpy()
    sides=pd.Series(np.nan,index=returns.index)
    for i in range(126,len(returns)-1):
        x=factors[i-126:i]
        y=miners[i-126:i]
        beta=np.linalg.lstsq(x,y,rcond=None)[0]
        surprise=miners[i]-factors[i]@beta
        if abs(surprise)>1.5*np.sqrt(np.mean((y-x@beta)**2)):
            sides.iloc[i+1]=np.sign(surprise)
    raw=load_master(('M15',),end=1767225600).m15
    frame=pd.DataFrame(raw)
    frame.index=pd.to_datetime(frame.time.to_numpy(),unit='s',utc=True).tz_convert('America/New_York')
    def at(clock):
        q=frame.at_time(clock)[['open','spread']].copy()
        q.index=q.index.tz_localize(None).normalize()
        return q
    d=at('09:45').join(at('15:45'),lsuffix='_in',rsuffix='_out').join(sides.rename('side')).join(returns.GLD.shift().rename('gold')).dropna()
    cost=SCENARIOS['realistic_ecn']
    move=d.open_out-d.open_in
    d['buy']=2*(move-d.spread_in.map(lambda s:cost.spread_price(.001,s))-2*cost.slip(.001))-cost.commission(.02)
    d['sell']=2*(-move-d.spread_out.map(lambda s:cost.spread_price(.001,s))-2*cost.slip(.001))-cost.commission(.02)
    report={}
    rng=np.random.default_rng(12615)
    for first,last in [('2007','2012'),('2013','2018'),('2019','2025')]:
        era=d.loc[first:last]
        p=np.where(era.side>0,era.buy,era.sell)
        save_result('miners_residual',pd.Series(p,index=era.index),first+'-01-01',last+'-12-31',
                    specification='research/registry/PREREG_MinersResidual_2026-11-11.md',runner=__file__)
        null=np.zeros(2000)
        for _,year in era.groupby(era.index.year):
            masks=np.array([rng.permutation(year.side.to_numpy())>0 for _ in null])
            null+=np.where(masks,year.buy.to_numpy(),year.sell.to_numpy()).sum(axis=1)
        stats=ratios(p,int(last)-int(first)+1)
        trades=[SimpleNamespace(net_pl=v) for v in p]
        stats.update(wins=int((p>0).sum()),prior_gold_control=float(np.select([era.gold>0,era.gold<0],[era.buy,era.sell],0.).sum()),
                     median_random_net=float(np.median(null)),adjusted_p=bonferroni_correction((1+sum(null>=p.sum()))/2001,3),
                     ablation=drop_best_worst(trades),permutation=monte_carlo_paths(trades,5000),
                     dsr=None,expected_max_sr=None,reason='Aligned full-search matrix unavailable')
        report[first+'-'+last]=stats
        print(first,last,len(p),stats['wins'],stats['net'],stats['profit_factor'],stats['prior_gold_control'],stats['median_random_net'])
    Path('research/registry/miners_residual_metrics.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
