"""Funding sensitivity on unchanged fixed-size basket paths; not an Atlas quote."""
import hashlib
import json
from pathlib import Path
import numpy as np


def profit_factor(pnl):
    p = np.asarray(pnl,dtype=float)
    loss = -p[p<0].sum()
    return float(p[p>0].sum()/loss) if loss else None


def maximum_charge(no_funding,ounce_nights,target=1.3):
    """Largest uniform long USD/oz/calendar-day debit retaining target PF."""
    initial = profit_factor(no_funding)
    if initial is None or initial<target:
        return None
    lo,hi = 0.,2.
    if profit_factor(no_funding-hi*ounce_nights)>=target:
        return None  # No finite threshold found in declared search interval.
    for _ in range(70):
        mid = (lo+hi)/2
        if profit_factor(no_funding-mid*ounce_nights)>=target:
            lo = mid
        else:
            hi = mid
    return float(lo)


def main():
    source = Path('research/registry/turtle_s2.json')
    data = json.loads(source.read_text())
    report = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        caveat='Uniform long USD/oz/calendar-day debit, short funding zero. Not historical or current Atlas rates. Fixed baskets only, no equity-dependent sizing or liquidation.',results={})
    for key,case in data.items():
        if not key.endswith('base'):
            continue
        rows = case['basket_records']
        p = np.array([r['pnl'] for r in rows])
        swap = np.array([r['swap'] for r in rows])
        # Baseline charges .5155 dollars per oz per calendar rollover to longs;
        # shorts are zero. Funding does not change fixed-size entry/exit decisions.
        ounce_nights = -swap/.5155
        no_funding = p-swap
        scenarios = {}
        for charge in (0.,.01,.05,.10,.25,.5155,1.):
            result = no_funding-charge*ounce_nights
            scenarios[str(charge)] = dict(net_usd=float(result.sum()),profit_factor=profit_factor(result))
        report['results'][key] = dict(baskets=len(rows),long_ounce_nights=float(ounce_nights.sum()),
            maximum_uniform_long_charge_for_pf_1_3=maximum_charge(no_funding,ounce_nights),scenarios=scenarios)
    Path('research/registry/turtle_funding_sensitivity.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
