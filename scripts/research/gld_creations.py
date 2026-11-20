"""Screen lagged ETF creations against spot returns; retain only aggregate outputs."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree
from zipfile import ZipFile
import numpy as np
import pandas as pd
import requests
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import drop_best_worst, monte_carlo_paths
from src.research.metrics import bonferroni_correction
from src.research.dated_results import save_result
from scripts.validation.full_metric_suite import ratios

URL='https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en'


def signals():
    response=requests.get(URL,timeout=30)
    response.raise_for_status()
    with ZipFile(BytesIO(response.content)) as z:
        strings=[''.join(node.itertext()) for node in ElementTree.fromstring(z.read('xl/sharedStrings.xml'))]
        rows=ElementTree.fromstring(z.read('xl/worksheets/sheet2.xml')).findall('.//{*}row')
    records=[]
    for row in rows:
        fields={}
        for cell in row:
            col=cell.get('r','').rstrip('0123456789')
            v=cell.findtext('{*}v')
            if col in ('A','C','I') and v:
                fields[col]=strings[int(v)] if cell.get('t')=='s' else v
        if fields.get('A')=='Date':
            assert fields['I']=='Total Ounces of Gold in the Trust' and fields['C']=='Ounces of Gold per Share'
            continue
        try:
            date=pd.to_datetime(fields['A'],format='%d-%b-%Y')
            shares=float(fields['I'])/float(fields['C'])
        except (ValueError,KeyError,ZeroDivisionError):
            continue
        if date.year<=2025 and np.isfinite(shares) and shares>0: records.append((date,shares))
    shares=pd.Series(dict(records)).sort_index()
    assert len(shares)==len(records) and len(shares)>4500
    change=shares.pct_change().shift(2)
    age=shares.index.to_series()-shares.index.to_series().shift(2)
    return np.sign(change.where(change.abs()>.0025)).where(age<=pd.Timedelta(days=7)),hashlib.sha256(response.content).hexdigest()


def main():
    side,digest=signals()
    raw=load_master(('M15',),end=int(pd.Timestamp('2026-01-01',tz='UTC').timestamp())).m15
    frame=pd.DataFrame(raw)
    frame.index=pd.to_datetime(frame.time.to_numpy(),unit='s',utc=True).tz_convert('America/New_York')
    def quotes(clock):
        q=frame.at_time(clock)[['open','spread']].copy()
        q.index=q.index.tz_localize(None).normalize()
        return q
    days=quotes('09:45').join(quotes('15:45'),lsuffix='_in',rsuffix='_out').join(side.rename('side')).dropna()
    cost=SCENARIOS['realistic_ecn']
    delta=days.open_out-days.open_in
    days['buy']=2*(delta-days.spread_in.map(lambda x:cost.spread_price(.001,x))-2*cost.slip(.001))-cost.commission(.02)
    days['sell']=2*(-delta-days.spread_out.map(lambda x:cost.spread_price(.001,x))-2*cost.slip(.001))-cost.commission(.02)
    rng=np.random.default_rng(111120)
    report={'source':URL,'sha256':digest,'eras':{}}
    for start,end in [('2005','2011'),('2012','2018'),('2019','2025')]:
        era=days.loc[start:end]
        p=np.where(era.side>0,era.buy,era.sell)
        save_result('gld_creations',pd.Series(p,index=era.index),start+'-01-01',end+'-12-31',
                    specification='research/registry/PREREG_GLDCreations_2026-11-11.md',runner=__file__)
        null=np.zeros(2000)
        for _,year in era.groupby(era.index.year):
            mask=year.side.to_numpy()>0
            null+=np.where(np.array([rng.permutation(mask) for _ in null]),year.buy.to_numpy(),year.sell.to_numpy()).sum(axis=1)
        stats=ratios(p,7)
        records=[SimpleNamespace(net_pl=x) for x in p]
        stats.update(wins=int((p>0).sum()),median_control_net=float(np.median(null)),
                     adjusted_control_p=bonferroni_correction((1+sum(null>=p.sum()))/2001,3),
                     ablation=drop_best_worst(records),monte_carlo=monte_carlo_paths(records,5000),
                     dsr=None,expected_max_sr=None,selection_limitation='Full search return matrix unavailable')
        report['eras'][start+'-'+end]=stats
        print(start,end,len(p),stats['wins'],stats['profit_factor'],stats['net'],stats['median_control_net'],stats['adjusted_control_p'])
    Path('research/registry/gld_creations_metrics.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
