"""Provisional size feasibility, explicitly not an Atlas contract verification."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from scripts.research.turtle_s2 import prepare


def main():
    raw = load_master(('M15',),end=1767225600).m15
    f = pd.DataFrame(raw)
    f.index = pd.to_datetime(f.time.to_numpy(),unit='s',utc=True)
    f = prepare(f)
    source = Path('research/registry/turtle_s2.json')
    data = json.loads(source.read_text())
    report = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        assumed_minimum_lot=.01,assumed_contract_oz_per_lot=100.,reference_balance=5000.,
        caveat='Assumed contract, not verified Atlas settings. Budgets are internal scenarios, not firm rules. Stop risk excludes funding/gap reserve and floating drawdown.',results={})
    for key,case in data.items():
        if not (key.startswith('1unit') and key.endswith('base')):
            continue
        dates = pd.to_datetime([r['entry_time'] for r in case['basket_records']],unit='s',utc=True)
        n = f.loc[dates,'n_value'].to_numpy()
        risk = 2*n+.055  # One oz, stop slippage .02 plus .01-lot roundtrip commission .035.
        report['results'][key] = dict(entries=len(risk),
            min_unit_stop_risk_percentiles_usd=np.percentile(risk,[10,50,90]).tolist(),
            eligible_entries_by_internal_budget_pct={str(pct):int(sum(risk<=5000*pct/100)) for pct in (.25,.5,1.,2.)})
    Path('research/registry/turtle_min_lot_feasibility.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
