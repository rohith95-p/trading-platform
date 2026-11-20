"""Reconcile independent MT5 native order times with standalone Python comparison ledgers."""
from collections import Counter
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]/'research/results'
OUT=ROOT/'retained_mt5'
ROSTERS={'portfolio':'retained_portfolio','filtered':'AsianRangeFilteredV6','breakout':'AsianBreakoutV6','london':'LondonMomentumTightV6'}
MAGICS={'ASIAN_RANGE_FILTERED_V6':7320,'ASIAN_BREAKOUT_V6':7311,'LONDON_MOMENTUM_TIGHT_V6':7324}


def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def check(year, roster, funded):
    suffix='_funded' if funded else ''
    native_path=OUT/f'{year}_{roster}{suffix}_deals.csv'
    python_dir=ROOT/f'four_strategies_{year}'/ROSTERS[roster]
    if funded:
        python_dir=python_dir/'funded'
    if not native_path.exists() or not (python_dir/'trades.csv').exists(): return None
    n,p=rows(native_path),rows(python_dir/'trades.csv')
    native_open=[r for r in n if r['entry']=='0']
    native_close=[r for r in n if r['entry']=='1']
    assert len(native_open)==len(native_close)
    assert all(float(r['sl'])>0 and float(r['tp'])>0 and abs(float(r['volume'])-.02)<1e-9 for r in native_open)
    assert len({r['position_id'] for r in native_open})==len(native_open)
    nk=Counter((int(r['magic']),int(r['time_msc']),int(r['type'])==0) for r in native_open)
    pk=Counter((MAGICS[r['strategy']],int(r['entry_time_ms']),r['is_buy']=='True') for r in p)
    nmins=Counter((g,t//60000,b) for (g,t,b),v in nk.items() for _ in range(v))
    pmins=Counter((g,t//60000,b) for (g,t,b),v in pk.items() for _ in range(v))
    return {'year':year,'roster':roster,'phase':'funded' if funded else 'evaluation',
            'native_count':len(native_open),'python_count':len(p),'matched_within_minute':(nmins&pmins).total(),
            'matched_exact_millisecond':(nk&pk).total(),'native_only_minutes':list((nmins-pmins).elements()),
            'python_only_minutes':list((pmins-nmins).elements()),'native_net':round(sum(float(r[f]) for r in n for f in ['profit','commission','fee','swap']),2),
            'python_net':round(sum(float(r['net_pl']) for r in p),2),
            'opening_orders_with_visible_stop':len(native_open)}


if __name__=='__main__':
    report=[entry for y in [2025,2026] for roster in ROSTERS for funded in [False,True]
            if (entry:=check(y,roster,funded)) is not None]
    (OUT/'entry_parity.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for entry in report:
        print(*(entry[k] for k in ['year','roster','phase','native_count','python_count','matched_within_minute','matched_exact_millisecond','native_net','python_net']))
