"""Independent quote/cash checks and family-level daily statistics for CE/ZLSMA."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.research.metrics import deflated_sharpe_ratio,expected_max_sr,bonferroni_correction


def main():
    root=Path('research/registry');output={}
    for suffix,expected in [('',12),('_bidask2025',4)]:
        source=json.loads((root/f'chandelier_zlsma{suffix}.json').read_text())
        if len(source['results'])!=expected:raise ValueError('Incomplete strategy run')
        loaded={};counts=dict(baskets=0,cash_errors=0,entry_errors=0,exit_errors=0)
        daily={};per_case={}
        for label,case in source['results'].items():
            year=int(label[:4]);name=label[5:]
            if year not in loaded:
                m=source['input_manifests'][str(year)]
                loaded[year]=np.load(m['path'] if suffix else m['inputs']['M1']['path'])
            raw=loaded[year];explicit=bool(suffix);prefix='bid_' if explicit else ''
            def price(i,side,field):
                if explicit:return float(raw[('ask_' if side==-1 else 'bid_')+field][i])
                spread=(raw['spread'][i] if raw['spread'][i]>0 else 260)*.001
                return float(raw[field][i]+(spread if side==-1 else 0))
            for t in case['baskets']:
                counts['baskets']+=1;side=t['side'];i=int(raw['time'].searchsorted(t['entry_time']))
                entry=price(i,-side,'open')+side*.02
                counts['entry_errors']+=int(abs(entry-t['entry'])>1e-7 or raw['time'][i]!=t['entry_time'])
                leg=t['exits'][0];nights=leg['time']//86400-t['entry_time']//86400
                swap=-1.031*nights if side==1 else 0.
                cash=2*side*(leg['price']-t['entry'])-.07+swap
                counts['cash_errors']+=int(abs(cash-t['pnl'])>1e-7 or abs(swap-t['swap'])>1e-7 or len(t['exits'])!=1 or leg['lots']!=.02)
                at_open=t['reason'] in ('gap_stop','immediate_stop','signal')
                j=int(raw['time'].searchsorted(t['exit_time'] if at_open else t['exit_time']-60))
                valid= j<len(raw) and raw['time'][j]==(t['exit_time'] if at_open else t['exit_time']-60)
                if t['reason']=='stop':
                    expected_px=t['stop']-side*.02
                    touch=price(j,side,'low' if side==1 else 'high')
                    valid &= side*(touch-t['stop'])<=1e-7
                else:expected_px=price(j,side,'open' if at_open else 'close')-side*.02
                counts['exit_errors']+=int(not valid or abs(expected_px-leg['price'])>1e-7)
            if abs(sum(t['pnl'] for t in case['baskets'])-case['net'])>.006:raise ValueError('Aggregate cash mismatch')
            ix=pd.date_range(f'{year}-01-01',f'{year}-12-31',tz='UTC');series=pd.Series(0.,index=ix)
            for t in case['baskets']:
                ts=t['exit_time']-(1 if t['reason']=='boundary' else 0)
                series.loc[pd.Timestamp(ts,unit='s',tz='UTC').normalize()]+=t['pnl']/5000
            daily.setdefault(name,[]).append(series)
        matrix=pd.DataFrame({k:pd.concat(v).sort_index() for k,v in daily.items()}).fillna(0.)
        sr=matrix.mean()/matrix.std(ddof=0);variance=float(sr.var(ddof=1));rng=np.random.default_rng(86721)
        for name in matrix:
            a=matrix[name].to_numpy();month=(matrix[name]*5000).groupby(matrix.index.strftime('%Y-%m')).sum().to_numpy()
            null=rng.choice(month-month.mean(),size=(5000,len(month)),replace=True).sum(axis=1)
            per_case[name]=dict(dsr_sensitivities={str(n):deflated_sharpe_ratio(a,n,variance) for n in (4,640,1000,2000)},
                bonferroni_month_bootstrap_p=bonferroni_correction((1+sum(null>=a.sum()*5000))/5001,4))
        output[suffix or 'original_snapshot']=dict(audit=counts,statistics=per_case,
            expected_max_sr_sensitivities={str(n):expected_max_sr(n,variance) for n in (4,640,1000,2000)},
            caveats=['Cash/quote/exit-touch checks, not independent full Pine or first-hit replay.',
                     'Disjoint inspected years, zero cash on missing source days; DSR/trial counts are diagnostic sensitivities.',
                     'No bootstrap or permutation result is a future-profit probability.'])
        print(suffix or 'original',counts,flush=True)
    (root/'chandelier_zlsma_audit.json').write_text(json.dumps(output,indent=2,allow_nan=False))
    if any(v['audit'][k] for v in output.values() for k in ('cash_errors','entry_errors','exit_errors')):raise SystemExit('Quote/cash audit failed')


if __name__=='__main__':main()
