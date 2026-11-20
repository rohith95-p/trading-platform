"""Independent trade cash identities and vectorized static stop/target verification."""
import gzip
import argparse
import json
from pathlib import Path
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--segments-only',action='store_true')
    args = parser.parse_args()
    root = Path('research/results/genesis_2026-11-11')
    report = {}
    for year in (2013,2018,2025):
        if args.segments_only and year!=2025:
            continue
        source = root/f'{year}.signals.jsonl.gz'
        meta = json.loads(source.with_suffix('.manifest.json').read_text())
        raw = np.load(meta['inputs']['M1']['path'],allow_pickle=False)
        raw = raw[(raw['time']>=meta['start'])&(raw['time']<meta['end'])]
        with gzip.open(source,'rt',encoding='utf-8') as stream:
            signals = {r['decision_time_utc']:r['signals'] for r in map(json.loads,stream)}
        cases = [('.segments',30),('.repair.segments',6)] if args.segments_only else [('',30),('.repair',6),('.frictionless',10)]
        for suffix,expected_count in cases:
            path = root/f'{year}.backtest{suffix}.json'
            data = json.loads(path.read_text())
            if len(data['results'])!=expected_count:
                raise ValueError('Incomplete backtest: '+str(path))
            free = suffix=='.frictionless'
            spread = np.zeros(len(raw)) if free else np.where(raw['spread']>0,raw['spread'],260)*.001
            slip,commission = (0.,0.) if free else (.02,3.5)
            counts = dict(trades=0,legs=0,static_verified=0,cash_errors=0,entry_errors=0,exit_errors=0)
            for label,case in data['results'].items():
                for trade in case['baskets']:
                    counts['trades'] += 1
                    end_cap = len(raw)
                    if args.segments_only:
                        segment = data['coverage_segments'][trade['coverage_segment']]
                        if not segment['first_decision']<=trade['entry_time']<trade['exit_time']<=segment['end']:
                            raise ValueError('Trade outside independently warmed coverage segment')
                        end_cap = int(raw['time'].searchsorted(segment['end']))
                    side = trade['side']
                    i = int(raw['time'].searchsorted(trade['entry_time']))
                    expected_entry = raw['open'][i]+(spread[i] if side==1 else 0)+side*slip
                    counts['entry_errors'] += int(abs(expected_entry-trade['entry'])>1e-7)
                    cash = 0.
                    for leg in trade['exits']:
                        counts['legs'] += 1
                        nights = leg['time']//86400-trade['entry_time']//86400
                        swap = -.5155*leg['lots']*100*nights if side==1 and not free else 0.
                        pnl = leg['lots']*100*side*(leg['price']-trade['entry'])-commission*leg['lots']+swap
                        counts['cash_errors'] += int(abs(pnl-leg['pnl'])>1e-7 or abs(swap-leg['swap'])>1e-7)
                        cash += pnl
                    counts['cash_errors'] += int(abs(cash-trade['pnl'])>1e-7 or abs(sum(l['lots'] for l in trade['exits'])-.02)>1e-8)
                    if not label.endswith(' static'):
                        continue
                    counts['static_verified'] += 1
                    s = signals[trade['entry_time']].get(trade['chosen_strategy'])
                    target_distance = s['tp_distance'] if s is not None else 2*trade['initial_risk']
                    stop = trade['entry']-side*trade['initial_risk']
                    target = trade['entry']+side*target_distance
                    end = min(end_cap,int(raw['time'].searchsorted(trade['exit_time'],side='right')))
                    adverse = raw['low'][i:end] if side==1 else raw['high'][i:end]+spread[i:end]
                    favorable = raw['high'][i:end] if side==1 else raw['low'][i:end]+spread[i:end]
                    sl = adverse<=stop if side==1 else adverse>=stop
                    tp = favorable>=target if side==1 else favorable<=target
                    hits = np.flatnonzero(sl|tp)
                    if not len(hits):
                        expected_px = raw['close'][end_cap-1]+(spread[end_cap-1] if side==-1 else 0)-side*slip
                        expected_time = int(raw['time'][end_cap-1])+60
                        valid = trade['reason']=='boundary'
                    else:
                        k = int(hits[0]);j = i+k
                        opening = raw['open'][j]+(spread[j] if side==-1 else 0)
                        expected_time = int(raw['time'][j])
                        if side*(opening-stop)<=0:
                            expected_px = opening-side*slip
                        elif side*(opening-target)>=0:
                            expected_px = target
                        else:
                            expected_px = stop-side*slip if sl[k] else target
                            expected_time += 60
                        valid = True
                    leg = trade['exits'][0]
                    counts['exit_errors'] += int(not valid or abs(expected_px-leg['price'])>1e-7 or expected_time!=leg['time'])
            report[f'{year}{suffix}'] = counts
            print(year,suffix,counts,flush=True)
    (root/('independent_audit_segments.json' if args.segments_only else 'independent_audit.json')).write_text(json.dumps(report,indent=2))
    if any(c[k] for c in report.values() for k in ('cash_errors','entry_errors','exit_errors')):
        raise SystemExit('Independent Genesis audit failed')


if __name__=='__main__':
    main()
