"""Fixed public CE/ZLSMA rules, synthetic signal candles, real XAUUSD execution."""
import hashlib
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from src.backtesting.costs import SCENARIOS
from scripts.validation.full_metric_suite import ratios
from scripts.research.genesis_backtest import sampled_equity
from src.backtesting.metrics import drop_best_worst,monte_carlo_paths


def linreg_last(values,n=50):
    x=np.arange(n,dtype=float);center=x-x.mean()
    weights=1/n+center*(n-1-x.mean())/(center@center)
    result=np.full(len(values),np.nan)
    if len(values)>=n:
        result[n-1:]=np.convolve(values,weights[::-1],mode='valid')
    return result


def indicators(raw,heikin=True):
    o,h,l,c=[raw[k].astype(float).copy() for k in ('open','high','low','close')]
    if heikin:
        hc=(o+h+l+c)/4;ho=np.empty(len(c));ho[0]=(o[0]+c[0])/2
        for i in range(1,len(c)):ho[i]=(ho[i-1]+hc[i-1])/2
        h=np.maximum(h,np.maximum(ho,hc));l=np.minimum(l,np.minimum(ho,hc));c=hc
    prev=np.r_[np.nan,c[:-1]]
    tr=np.maximum(h-l,np.maximum(abs(h-prev),abs(l-prev)));tr[0]=h[0]-l[0]
    long=c-2*tr;short=c+2*tr
    side=np.ones(len(c),dtype=int)
    for i in range(1,len(c)):
        if c[i-1]>long[i-1]:long[i]=max(long[i],long[i-1])
        if c[i-1]<short[i-1]:short[i]=min(short[i],short[i-1])
        side[i]=1 if c[i]>short[i-1] else (-1 if c[i]<long[i-1] else side[i-1])
    lsma=linreg_last(c);z=2*lsma-linreg_last(lsma)
    previous=np.r_[1,side[:-1]]
    entry=np.where((side==1)&(previous==-1)&(c>z),1,np.where((side==-1)&(previous==1)&(c<z),-1,0))
    prior_z=np.r_[np.nan,z[:-1]]
    close_long=(c<z)&(prev>=prior_z);close_short=(c>z)&(prev<=prior_z)
    return dict(entry=entry,stop=np.where(entry==1,long,short),close_long=close_long,close_short=close_short)


def replay(raw,bars,features,period,start,end,cost):
    events={int(t)+period:i for i,t in enumerate(bars['time']) if start<=int(t)+period<end}
    position=None;trades=[];wrong_side=0
    def finish(px,ts,reason,next_time):
        nonlocal position
        p=position;swap=cost.swap(.02,p['side']==1,p['entry_time'],ts,.001,100)
        cash=2*p['side']*(px-p['entry'])-cost.commission(.02)+swap
        p.update(exit_time=int(ts),next_entry_time=int(next_time),reason=reason,pnl=float(cash),swap=float(swap),
                 exits=[dict(time=int(ts),price=float(px),lots=.02,pnl=float(cash),swap=float(swap))])
        trades.append(p);position=None
    def ask(row,field):
        return row['ask_'+field] if 'ask_'+field in raw.dtype.names else row[field]+cost.spread_price(.001,row['spread'])
    for row in raw:
        ts=int(row['time']);spread=cost.spread_price(.001,row['spread']);slip=cost.slip(.001)
        # A resting stop has priority over newly actionable closed-bar market orders.
        if position:
            side=position['side'];opening=row['open'] if side==1 else ask(row,'open')
            if side*(opening-position['stop'])<=0:
                finish(opening-side*slip,ts,'gap_stop',ts)
        e=events.get(ts)
        if e is not None:
            direction=int(features['entry'][e])
            if position and ((position['side']==1 and features['close_long'][e]) or
                             (position['side']==-1 and features['close_short'][e]) or
                             (direction and direction!=position['side'])):
                side=position['side'];finish((row['open'] if side==1 else ask(row,'open'))-side*slip,ts,'signal',ts)
            if direction:
                stop=float(features['stop'][e])
                if position is None:
                    entry=float((ask(row,'open') if direction==1 else row['open'])+direction*slip)
                    position=dict(entry_time=ts,entry=entry,side=direction,stop=stop,initial_risk=abs(entry-stop))
                else:position['stop']=stop
        if position:
            side=position['side'];stop=position['stop'];opening=row['open'] if side==1 else ask(row,'open')
            if side*(opening-stop)<=0:
                wrong_side+=1;finish(opening-side*slip,ts,'immediate_stop',ts+60)
            elif (row['low']<=stop if side==1 else ask(row,'high')>=stop):
                finish(stop-side*slip,ts+60,'stop',ts+60)
    if position:
        side=position['side'];finish((raw['close'][-1] if side==1 else ask(raw[-1],'close'))-side*cost.slip(.001),int(raw['time'][-1])+60,'boundary',end)
    return trades,wrong_side


def equity_metrics(raw,trades,cost):
    if 'ask_open' not in raw.dtype.names:return sampled_equity(raw,trades,cost)
    times=np.r_[raw['time'],int(raw['time'][-1])+60]
    bid=np.r_[raw['open'],raw['close'][-1]];ask=np.r_[raw['ask_open'],raw['ask_close'][-1]]
    cash=np.zeros(len(times));floating=np.zeros(len(times))
    for trade in trades:
        i=int(times.searchsorted(trade['entry_time']));j=int(times.searchsorted(trade['exit_time']));side=trade['side']
        cash[j]+=trade['pnl'];mark=(bid if side==1 else ask)[i:j]-side*cost.slip(.001)
        floating[i:j]+=2*side*(mark-trade['entry'])-cost.commission(.02)
        if cost.enable_swap:
            nights=times[i:j]//86400-trade['entry_time']//86400
            floating[i:j]+=nights*(cost.swap_long_points if side==1 else cost.swap_short_points)*.001*2
    equity=np.r_[5000.,5000+cash.cumsum()+floating];peak=np.maximum.accumulate(equity)
    if not np.isclose(equity[-1]-5000,sum(t['pnl'] for t in trades),atol=1e-7):raise ValueError('Cash/equity mismatch')
    return dict(sampled_liquidation_max_dd_usd=float((peak-equity).max()),sampled_liquidation_max_dd_pct=float((100*(peak-equity)/peak).max()),sampled_minimum_equity_usd=float(equity.min()))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bidask2025',action='store_true');args=parser.parse_args()
    report=dict(source=json.loads(Path('research/sources/chandelier_zlsma/manifest.json').read_text()),
                runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),results={},
                caveat='Independent covered samples, inspected years; no synthetic-price fills, full Pine engine parity, or continuous Atlas/account claims.')
    cost=SCENARIOS['realistic_ecn'];report['costs']=cost.descriptor()
    for year in ((2025,) if args.bidask2025 else (2013,2018,2025)):
        meta=json.loads(Path('research/data/dukascopy_2025/manifest.json' if args.bidask2025 else f'research/data/genesis/{year}.json').read_text())
        arrays={}
        inputs={'M1':meta} if args.bidask2025 else meta['inputs']
        report.setdefault('input_manifests',{})[str(year)]=meta
        for tf,info in inputs.items():
            p=Path(info['path'])
            if hashlib.sha256(p.read_bytes()).hexdigest()!=info['sha256']:raise ValueError('Source snapshot changed')
            arrays[tf]=np.load(p,allow_pickle=False)
        if args.bidask2025:
            from scripts.research.genesis_prepare import aggregate_m5
            source=arrays['M1'];normal=np.zeros(len(source),dtype=[('time','i8'),('open','f8'),('high','f8'),('low','f8'),('close','f8'),('spread','i8')]+[(f'ask_{k}','f8') for k in ('open','high','low','close')])
            normal['time']=source['time']
            for field in ('open','high','low','close'):
                normal[field]=source['bid_'+field];normal['ask_'+field]=source['ask_'+field]
            normal['spread']=np.rint((normal['ask_open']-normal['open'])*1000).astype('i8')
            arrays={'M1':normal,'M5':aggregate_m5(normal)}
            meta={**meta,'start':1735689600}
        raw=arrays['M1'];bounds=[0,*list(np.flatnonzero(np.diff(raw['time'])>7*86400)+1),len(raw)]
        for tf,period in [('M1',60),('M5',300)]:
            for ha in (True,False):
                records=[];segments=[];immediate=0
                for n,(lo,hi) in enumerate(zip(bounds[:-1],bounds[1:])):
                    chunk=raw[lo:hi];bars=arrays[tf]
                    bars=bars[(bars['time']>=int(chunk['time'][0]))&(bars['time']+period<=int(chunk['time'][-1])+60)]
                    if len(bars)<300:continue
                    start=max(meta['start'],int(bars['time'][299])+period)
                    end=min(meta['end'],int(chunk['time'][-1])+60)
                    execution=chunk[(chunk['time']>=start)&(chunk['time']<end)]
                    if not len(execution):continue
                    features=indicators(bars,ha)
                    trades,invalid=replay(execution,bars,features,period,start,end,cost)
                    for trade in trades:trade['coverage_segment']=n
                    p=np.array([t['pnl'] for t in trades]);stats=ratios(p,(end-start)/(365.25*86400))
                    stats.update(equity_metrics(execution,trades,cost))
                    segments.append(dict(segment=n,start=start,end=end,stats=stats))
                    records.extend(trades);immediate+=invalid
                pnl=np.array([t['pnl'] for t in records]);stats=ratios(pnl,1)
                tr=[SimpleNamespace(net_pl=x) for x in pnl]
                stats.update(segments=segments,baskets=records,immediate_stops=immediate,
                             ablation=drop_best_worst(tr),permutation=monte_carlo_paths(tr,5000,n=1000))
                label=f'{year} {tf} '+('HA' if ha else 'ordinary')
                report['results'][label]=stats
                print(label,len(pnl),stats['profit_factor'],stats['net'],flush=True)
                suffix='_bidask2025' if args.bidask2025 else ''
                Path(f'research/registry/chandelier_zlsma{suffix}.json').write_text(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':main()
