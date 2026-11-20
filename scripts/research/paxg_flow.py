"""Run with python -m scripts.research.paxg_flow."""
import hashlib
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import requests
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import drop_best_worst, monte_carlo_paths
from src.research.metrics import bonferroni_correction
from src.research.dated_results import save_result
from scripts.validation.full_metric_suite import ratios


def fetch(month):
    base='https://data.binance.vision/data/spot/monthly/klines/PAXGUSDT/30m/'
    url=base+f'PAXGUSDT-30m-{month}.zip'
    response=requests.get(url,timeout=40)
    response.raise_for_status()
    digest=hashlib.sha256(response.content).hexdigest()
    check=requests.get(url+'.CHECKSUM',timeout=30)
    check.raise_for_status()
    if digest!=check.text.split()[0]: raise ValueError('Checksum mismatch: '+month)
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        with z.open(z.namelist()[0]) as stream:
            d=pd.read_csv(stream,header=None)
    d.index=pd.to_datetime(d[0],unit='us' if month>='2025-01' else 'ms',utc=True).dt.tz_convert('Europe/London')
    d=d.at_time('14:00')
    d=d[(d.index.weekday<5)&(d[5]>0)&(d[8]>=10)]
    if not d[9].between(0,d[5]).all(): raise ValueError('Invalid taker volume')
    return 2*d[9]/d[5]-1,digest


def main():
    months=pd.period_range('2021-01','2025-12',freq='M').astype(str)
    with ThreadPoolExecutor(5) as pool:
        parts=list(pool.map(fetch,months))
    flow=pd.concat([p[0] for p in parts]).sort_index()
    active=flow[flow.abs()>flow.abs().shift().rolling(60).quantile(.8)]
    raw=load_master(('M15',),end=int(pd.Timestamp('2026-01-01',tz='UTC').timestamp())).m15
    frame=pd.DataFrame(raw)
    frame.index=pd.to_datetime(frame.time.to_numpy(),unit='s',utc=True)
    cost=SCENARIOS['realistic_ecn']
    rows=[]
    for date,imbalance in active.items():
        times=[date+pd.Timedelta(minutes=m) for m in (0,15,45,75)]
        if not all(t in frame.index for t in times): continue
        first,last,entry,exit_bar=[frame.loc[t] for t in times]
        delta=exit_bar.open-entry.open
        buy=2*(delta-cost.spread_price(.001,entry.spread)-.04)-.07
        sell=2*(-delta-cost.spread_price(.001,exit_bar.spread)-.04)-.07
        rows.append((date,imbalance>0,np.sign(last.close-first.open),buy,sell))
    d=pd.DataFrame(rows,columns=['date','buy_signal','price_sign','buy','sell']).set_index('date')
    rng=np.random.default_rng(202611)
    report={'archive_hashes':dict(zip(months,[p[1] for p in parts])),'eras':{}}
    for start,end in [('2022','2023'),('2024','2025')]:
        era=d.loc[start:end]
        p=np.where(era.buy_signal,era.buy,era.sell)
        save_result('paxg_flow',pd.Series(p,index=era.index),start+'-01-01',end+'-12-31',
                    specification='research/registry/PREREG_PAXGFlow_2026-11-11.md',runner=__file__)
        null=np.zeros(2000)
        for _,year in era.groupby(era.index.year):
            masks=np.array([rng.permutation(year.buy_signal) for _ in null])
            null+=np.where(masks,year.buy.to_numpy(),year.sell.to_numpy()).sum(axis=1)
        stats=ratios(p,2)
        tr=[SimpleNamespace(net_pl=x) for x in p]
        stats.update(wins=int((p>0).sum()),median_random_net=float(np.median(null)),
            price_only_net=float(np.select([era.price_sign>0,era.price_sign<0],[era.buy,era.sell],0.).sum()),
            adjusted_p=bonferroni_correction((1+sum(null>=p.sum()))/2001,2),
            ablation=drop_best_worst(tr),permutation=monte_carlo_paths(tr,5000),
            dsr=None,expected_max_sr=None,reason='Full candidate matrix unavailable')
        report['eras'][start+'-'+end]=stats
        print(start,len(p),stats['wins'],stats['net'],stats['profit_factor'],stats['median_random_net'],stats['price_only_net'],flush=True)
    Path('research/registry/paxg_flow_metrics.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
