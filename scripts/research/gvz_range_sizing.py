"""Run with python -m scripts.research.gvz_range_sizing from the project root."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.backtesting.master import load_master


def main():
    end = pd.Timestamp('2026-01-01',tz='UTC')
    raw = load_master(('M15',),end=int(end.timestamp())).m15
    frame = pd.DataFrame(raw)
    frame.index = pd.to_datetime(frame.time.to_numpy(),unit='s',utc=True).tz_localize(None)
    groups = frame.resample('D')
    ranges = ((groups.high.max()-groups.low.min())/groups.open.first()).where(groups.size()>=75)
    dates = pd.bdate_range(ranges.index.min(),end.tz_localize(None)-pd.Timedelta(days=1))
    target = ranges.reindex(dates).where(lambda s:s>0)
    valid = target.dropna()
    features = pd.DataFrame(index=dates)
    for n in (1,5,22):
        features[str(n)] = np.log(valid.rolling(n).mean()).reindex(dates).ffill().shift()
    gvz = pd.read_csv('research/data/gvz_through_2025.csv',parse_dates=['DATE']).set_index('DATE').GVZ
    features['gvz'] = np.log(gvz.reindex(dates-pd.Timedelta(days=1),method='ffill',
                                         tolerance=pd.Timedelta(days=3)).to_numpy())
    features.insert(0,'intercept',1.)
    y = np.log(target)
    predictions = pd.DataFrame(index=dates)
    for year in range(2012,2026):
        train = (dates.year<year)&features.notna().all(axis=1)&y.notna()
        test = (dates.year==year)&features.notna().all(axis=1)
        if train.sum()<252: continue
        for label,cols in [('price',['intercept','1','5','22']),('augmented',list(features))]:
            x=features.loc[train,cols]
            coef=np.linalg.lstsq(x,y[train],rcond=None)[0]
            pred=features.loc[test,cols]@coef
            predictions.loc[test,label]=pred
            predictions.loc[test,label+'_half']=(pred>(x@coef).quantile(.8)).astype(float)
    report={'forecast':{},'archived_sizing':{}}
    rng=np.random.default_rng(112011)
    for first,last in [('2012','2015'),('2016','2020'),('2021','2025')]:
        scored=predictions.join(y.rename('observed')).loc[first:last].dropna()
        errors=scored[['price','augmented']].sub(scored.observed,axis=0).abs()
        paired=(errors.price-errors.augmented).resample('ME').agg(['sum','count']).to_numpy()
        draws=paired[rng.integers(len(paired),size=(5000,len(paired)))].sum(axis=1)
        report['forecast'][first+'-'+last]={'sessions':len(scored),**errors.mean().to_dict(),
            'gain_month_resampled_95':np.quantile(draws[:,0]/draws[:,1],[.025,.975]).tolist()}
    root=Path('research/results/project_review_2026-11-11')
    for name in ['OOS_3','OOS_4','OOS_5','DEV','TEST']:
        tr=pd.DataFrame(json.loads((root/(name+'.json')).read_text())['trades']).sort_values('exit_time')
        dates_in=pd.to_datetime(tr.entry_time,unit='s',utc=True).dt.tz_localize(None).dt.normalize()
        flags=predictions.reindex(dates_in).reset_index(drop=True)
        stats={}
        for label in ['baseline','price','augmented']:
            half=np.zeros(len(tr),dtype=bool) if label=='baseline' else flags[label+'_half'].eq(1).to_numpy()&(tr.lots.to_numpy()>=.02)
            p=tr.net_pl.to_numpy()*np.where(half,.5,1.)
            equity=np.r_[0.,np.cumsum(p)]
            stats[label]=dict(trades=len(tr),half_sized=int(half.sum()),net=round(p.sum(),2),
                              pf=round(p[p>0].sum()/-p[p<0].sum(),3),
                              realized_dd=round((np.maximum.accumulate(equity)-equity).max(),2))
        report['archived_sizing'][name]=stats
    Path('research/registry/gvz_range_sizing.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report))


if __name__=='__main__':
    main()
