"""Exploratory historical CFTC crowding screen. Run as a module."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
import requests
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import monte_carlo_paths, drop_best_worst
from src.research.metrics import deflated_sharpe_ratio, expected_max_sr, bonferroni_correction
from src.research.dated_results import save_result
from scripts.validation.full_metric_suite import ratios


def main():
    date='report_date_as_yyyy_mm_dd'
    cols=[date,'m_money_positions_long_all','m_money_positions_short_all','open_interest_all']
    archive=Path('research/data/gold_cftc_through_2025.json')
    if not archive.exists():
        response=requests.get('https://publicreporting.cftc.gov/resource/72hh-3qpy.json',
            params={'cftc_contract_market_code':'088691','$where':date+" < '2026-01-01T00:00:00'",'$select':','.join(cols),'$order':date,'$limit':5000},timeout=30)
        response.raise_for_status()
        rows=response.json()
        if not 800<len(rows)<5000: raise ValueError('Unexpected report coverage')
        archive.write_text(json.dumps(rows))
    weekly=pd.DataFrame(json.loads(archive.read_text())).set_index(date).astype(float)
    weekly.index=pd.to_datetime(weekly.index,utc=True).normalize()+pd.Timedelta(days=14)
    if weekly.index.has_duplicates or not weekly.index.is_monotonic_increasing: raise ValueError('Invalid COT dates')
    net=(weekly.iloc[:,0]-weekly.iloc[:,1])/weekly.iloc[:,2]
    history=net.shift().rolling(52)
    side=(net>history.quantile(.9)).astype(int)-(net<history.quantile(.1)).astype(int)
    raw=load_master(('M15',),end=int(pd.Timestamp('2026-01-01',tz='UTC').timestamp())).m15
    frame=pd.DataFrame(raw)
    frame.index=pd.to_datetime(frame.time.to_numpy(),unit='s',utc=True).tz_convert('America/New_York')
    def at(clock):
        d=frame.at_time(clock).copy()
        d.index=pd.to_datetime(d.index.date,utc=True)
        return d[['open','spread']]
    days=at('09:45').join(at('12:00'),how='inner',lsuffix='_in',rsuffix='_out')
    days['side']=side.reindex(days.index,method='ffill',tolerance=pd.Timedelta(days=7))
    days=days[days.side.abs()==1]
    cost=SCENARIOS['realistic_ecn']
    result={'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'reports':len(weekly),'eras':{}}
    rng=np.random.default_rng(88691)
    for start,end in [('2010','2014'),('2015','2019'),('2020','2025')]:
        era=days.loc[start:end]
        move=era.open_out-era.open_in
        buy=2*(move-era.spread_in.map(lambda x:cost.spread_price(.001,x))-.04)-.07
        sell=2*(-move-era.spread_out.map(lambda x:cost.spread_price(.001,x))-.04)-.07
        streams=[np.where(era.side==direction,buy,sell) for direction in [1,-1]]
        variance=np.var([p.mean()/p.std() for p in streams],ddof=1)
        for name,p in zip(['follow','fade'],streams):
            save_result('cot_'+name,pd.Series(p,index=era.index),start+'-01-01',end+'-12-31',
                        specification='research/registry/PREREG_GoldCOT_2026-11-11.md',runner=__file__)
            stats=ratios(p,int(end)-int(start)+1)
            records=[SimpleNamespace(net_pl=x) for x in p]
            # Keep weekly positioning clusters together; circular weekly shifts are diagnostic.
            w=era.index.tz_localize(None).to_period('W-MON').factorize()[0]
            signs=np.array([era.side.iloc[np.flatnonzero(w==i)[0]] for i in np.unique(w)])
            null=[np.where(np.roll(signs,k)[w]==(1 if name=='follow' else -1),buy,sell).mean()
                  for k in range(1,len(signs))]
            stats.update(wins=int((p>0).sum()),expected_max_sr=expected_max_sr(2,variance),
                dsr_two_arm=deflated_sharpe_ratio(p,2,variance),
                adjusted_shift_p=bonferroni_correction((1+sum(np.asarray(null)>=p.mean()))/(1+len(null)),6),
                ablation=drop_best_worst(records),monte_carlo=monte_carlo_paths(records,5000))
            result['eras'][start+' '+name]=stats
            print(start,name,len(p),stats['wins'],stats['profit_factor'],stats['net'])
    Path('research/registry/gold_cot_crowding_metrics.json').write_text(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
