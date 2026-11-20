"""Actual-release-date gold reaction screen; fixed follow/fade rules."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import monte_carlo_paths,drop_best_worst
from src.research.metrics import bonferroni_correction
from src.research.dated_results import save_result
from scripts.validation.full_metric_suite import ratios


def release_from_url(url):
    m = re.fullmatch(r'https://www\.bls\.gov/news\.release/archives/(cpi|empsit)_(\d{8})\.(htm|txt)',url)
    if not m:
        raise ValueError('Not an official dated CPI/NFP archive link')
    date = pd.to_datetime(m[2],format='%m%d%Y')
    stamp = (date+pd.Timedelta(hours=8,minutes=30)).tz_localize('America/New_York').tz_convert('UTC')
    return dict(category='CPI' if m[1]=='cpi' else 'NFP',release_utc=stamp.isoformat(),
                event_time=int(stamp.timestamp()),source_url=url)


def simulate(window,side,cost):
    signal = window[:15]
    distance = float(signal['high'].max()-signal['low'].min())
    if distance<=0:
        return None
    row = window[16]
    spread = cost.spread_price(.001,row['spread'])
    entry = float(row['open'])+(spread if side==1 else 0)+side*cost.slip(.001)
    stop = entry-side*distance
    for j in range(16,60):
        row = window[j]
        spread = cost.spread_price(.001,row['spread'])
        hit = row['low']<=stop if side==1 else row['high']+spread>=stop
        if hit:
            opening = row['open']+(spread if side==-1 else 0)
            exit_price = min(opening,stop) if side==1 else max(opening,stop)
            exit_price -= side*cost.slip(.001)
            reason = 'stop'
            break
    else:
        j = 60
        row = window[j]
        exit_price = row['open']+(cost.spread_price(.001,row['spread']) if side==-1 else 0)-side*cost.slip(.001)
        reason = 'time'
    pnl = 2*side*(exit_price-entry)-cost.commission(.02)
    return dict(pnl=float(pnl),exit_time=int(row['time'])+(60 if reason=='stop' else 0),reason=reason)


def main():
    link_path = Path('research/events/bls_release_archive_links_2019_2025.json')
    links = [r['source_url'] for r in json.loads(link_path.read_text())['records']]
    links += json.loads(Path('research/events/bls_december_2018_release_links.json').read_text())
    events = sorted([release_from_url(u) for u in set(links)],key=lambda e:e['event_time'])
    events = [e for e in events if 2019<=pd.Timestamp(e['release_utc']).year<=2025]
    if len({e['event_time'] for e in events})!=len(events):
        raise ValueError('Overlapping event labels need explicit consolidation')
    bars = load_master(('M15','M1'),start=int(pd.Timestamp('2019-01-01',tz='UTC').timestamp()),
                       end=1767225600,use_cache=False).m1
    records,windows,skipped = [],[],[]
    for event in events:
        ts = event['event_time']
        i = bars['time'].searchsorted(ts)
        window = bars[i:i+61]
        if len(window)!=61 or not np.array_equal(window['time'],ts+60*np.arange(61)):
            skipped.append(dict(**event,reason='incomplete_minute_window'))
            continue
        move = float(window['close'][14]-window['open'][0])
        if not move:
            skipped.append(dict(**event,reason='zero_initial_direction'))
            continue
        records.append(dict(**event,signal=1 if move>0 else -1))
        windows.append(window.copy())
    array = np.stack(windows)
    key = hashlib.sha256(str(array.dtype.descr).encode()+array.tobytes()).hexdigest()
    snapshot = Path('research/data/bls_windows')/(key+'.npy')
    snapshot.parent.mkdir(parents=True,exist_ok=True)
    if not snapshot.exists():
        np.save(snapshot,array,allow_pickle=False)
    base = SCENARIOS['realistic_ecn']
    scenarios = dict(base=base,stress=replace(base,spread_multiplier=2.,slippage_points=60.),
                     frictionless=replace(base,spread_multiplier=0.,slippage_points=0.,commission_per_lot_roundtrip=0.))
    report = dict(calendar_events=len(events),used_events=len(records),skipped=skipped,
                  calendar_sha256=hashlib.sha256(link_path.read_bytes()).hexdigest(),
                  windows_snapshot=str(snapshot),windows_content_sha256=key,
                  runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),events=records,results={})
    rng = np.random.default_rng(163060)
    for cost_name,cost in scenarios.items():
        outcome = [{side:simulate(w,side,cost) for side in (-1,1)} for w in windows]
        for arm,multiplier in [('follow',1),('fade',-1)]:
            for first,last in [(2019,2021),(2022,2023),(2024,2025)]:
                ids = [i for i,e in enumerate(records) if first<=pd.Timestamp(e['release_utc']).year<=last]
                p = np.array([outcome[i][records[i]['signal']*multiplier]['pnl'] for i in ids])
                dates = pd.to_datetime([records[i]['release_utc'] for i in ids],utc=True)
                if cost_name=='base':
                    save_result('post_bls_'+arm,pd.Series(p,index=dates),f'{first}-01-01',f'{last}-12-31',
                                specification='research/registry/PREREG_PostBLSReaction_2026-11-11.md',runner=__file__)
                stats = ratios(p,last-first+1)
                tr = [SimpleNamespace(net_pl=x) for x in p]
                stats.update(wins=int(sum(p>0)),ablation=drop_best_worst(tr),monte_carlo=monte_carlo_paths(tr,5000))
                for cat in ('CPI','NFP'):
                    cp = [p[j] for j,i in enumerate(ids) if records[i]['category']==cat]
                    stats[cat] = ratios(cp,last-first+1)
                if cost_name=='base':
                    buy = np.array([outcome[i][1]['pnl'] for i in ids])
                    sell = np.array([outcome[i][-1]['pnl'] for i in ids])
                    null = np.where(rng.random((5000,len(p)))<.5,buy,sell).sum(axis=1)
                    monthly = pd.Series(p,index=dates).groupby(dates.strftime('%Y-%m')).sum()
                    monthly = monthly.reindex(pd.period_range(str(first),str(last)+'-12',freq='M').astype(str),fill_value=0.)
                    totals = rng.choice(monthly.to_numpy(),size=(5000,len(monthly)),replace=True).sum(axis=1)
                    stats.update(random_direction_median_net=float(np.median(null)),
                                 bonferroni_p_vs_random=bonferroni_correction((1+sum(null>=p.sum()))/5001,6),
                                 month_block_net_interval_95=np.percentile(totals,[2.5,97.5]).tolist())
                tag = f'{cost_name} {arm} {first}-{last}'
                report['results'][tag] = stats
                print(tag,len(p),stats['wins'],stats['profit_factor'],stats['net'],flush=True)
    Path('research/registry/post_bls_reaction.json').write_text(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
