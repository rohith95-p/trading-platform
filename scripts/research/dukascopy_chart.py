"""Freeze a separate public Dukascopy XAU/USD bid/ask M1 research snapshot."""
import concurrent.futures
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
import numpy as np


def side_snapshot(side,start,end,root):
    cursor=end*1000;pages=[];observations=[]
    for page in range(40):
        params=dict(path='chart/json3',instrument='XAU/USD',offer_side=side,interval='1MIN',
                    splits='true',stocks='true',time_direction='P',timestamp=str(cursor),jsonp='_callbacks____0')
        url='https://freeserv.dukascopy.com/2.0/index.php?'+urllib.parse.urlencode(params)
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0',
            'Referer':'https://freeserv.dukascopy.com/2.0/?path=chart/index&instrument=XAU/USD'})
        path=root/f'{side}_{cursor}.response.gz'
        if path.exists():
            with gzip.open(path,'rb') as stream:payload=stream.read()
        else:
            payload=urllib.request.urlopen(request,timeout=30).read()
            with gzip.open(path,'wb') as stream:stream.write(payload)
        text=payload.decode();rows=json.loads(text[text.find('(')+1:text.rfind(')')])
        if not rows or rows==[None]:raise ValueError(f'Unexpected empty page {side} {cursor}')
        rows=np.asarray(rows,dtype=float)
        if rows.ndim!=2 or rows.shape[1]!=6 or not np.isfinite(rows).all():raise ValueError('Malformed chart data')
        oldest=int(rows[:,0].min());newest=int(rows[:,0].max())
        if newest>=cursor or oldest>=cursor:raise ValueError('Nondecreasing page cursor')
        pages.append(dict(url=url,file=str(path.resolve()),sha256=hashlib.sha256(payload).hexdigest(),rows=len(rows),oldest_ms=oldest,newest_ms=newest))
        observations.append(rows);print(side,page+1,dt.datetime.fromtimestamp(oldest/1000,dt.UTC).isoformat(),flush=True)
        if oldest<=start*1000:break
        cursor=oldest-1
    else:raise ValueError('Page limit exceeded')
    data=np.concatenate(observations);data=data[np.argsort(data[:,0])]
    _,idx,counts=np.unique(data[:,0],return_index=True,return_counts=True)
    if np.any(counts>1):raise ValueError('Overlapping chart records; inspect before deduplication')
    data=data[(data[:,0]>=start*1000)&(data[:,0]<end*1000)]
    if np.any(data[:,0]%60000):raise ValueError('Non-minute timestamps')
    o,h,l,c=[data[:,i] for i in range(1,5)]
    if np.any(l>np.minimum(o,c)) or np.any(h<np.maximum(o,c)) or np.any(l>h):raise ValueError('Invalid OHLC')
    return data,pages


def main():
    start=int(dt.datetime(2024,12,15,tzinfo=dt.UTC).timestamp());end=int(dt.datetime(2026,1,1,tzinfo=dt.UTC).timestamp())
    root=Path('research/data/dukascopy_2025');root.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures={s:pool.submit(side_snapshot,s,start,end,root) for s in ('B','A')}
        results={s:f.result() for s,f in futures.items()}
    bid,bp=results['B'];ask,ap=results['A']
    common,bi,ai=np.intersect1d(bid[:,0],ask[:,0],return_indices=True)
    dtype=[('time','i8')]+[(side+'_'+field,'f8') for side in ('bid','ask') for field in ('open','high','low','close')]
    out=np.zeros(len(common),dtype=dtype);out['time']=common.astype('i8')//1000
    for side,rows,idx in [('bid',bid,bi),('ask',ask,ai)]:
        for i,name in enumerate(('open','high','low','close'),1):out[side+'_'+name]=rows[idx,i]
    crossed=np.zeros(len(out),dtype=bool)
    for field in ('open','high','low','close'):crossed|=out['ask_'+field]<out['bid_'+field]
    # Keep failures visible; do not silently delete bars to create a clean data set.
    path=root/'XAUUSD_M1_bidask.npy';np.save(path,out,allow_pickle=False)
    gaps=np.diff(out['time']);large=np.flatnonzero(gaps>3*86400)
    report=dict(instrument='XAU/USD',start=start,end=end,rows=len(out),bid_rows=len(bid),ask_rows=len(ask),
                unmatched_bid=len(bid)-len(out),unmatched_ask=len(ask)-len(out),crossed_extrema_rows=int(crossed.sum()),
                median_open_spread=float(np.median(out['ask_open']-out['bid_open'])),
                gaps_over_3_days=[dict(before=int(out['time'][i]),after=int(out['time'][i+1]),seconds=int(gaps[i])) for i in large],
                path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),pages={'B':bp,'A':ap},
                caveat='One provider, public chart endpoint; not broker-specific Atlas ticks. No interpolation, no old-source splice, no strategy outcome selection.')
    (root/'manifest.json').write_text(json.dumps(report,indent=2))
    print('FINAL',json.dumps({k:v for k,v in report.items() if k!='pages'}),flush=True)
    if crossed.any() or len(bid)!=len(out) or len(ask)!=len(out):raise ValueError('Bid/ask alignment requires inspection')


if __name__=='__main__':main()
