"""Read-only historical reproduction; writes only this review's artifacts."""
import os
os.environ['ULTRA_DISABLE_ALERTS'] = '1'
os.environ['ULTRA_TRADE_24H'] = '1'
os.environ['ULTRA_NO_TRIAL_LEDGER'] = '1'  # reproductions, not candidate selections
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import json
import dataclasses
import hashlib
import datetime as dt
from concurrent.futures import ProcessPoolExecutor
import numpy as np

OUT = Path(__file__).resolve().parent

def utc(*a):
    return int(dt.datetime(*a, tzinfo=dt.timezone.utc).timestamp())

def job(name, a, b, guarded):
    from scripts.validation.independent_audit_run import job as audit_job
    from src.backtesting.engine import BacktestEngine, EngineConfig
    from src.backtesting.master import load_master
    from src.backtesting.costs import SCENARIOS
    from src.strategies.portfolio_atlas import PORTFOLIO
    if guarded:
        _, rows, halts, diag = audit_job(name, a, b)
        cfg = 'independent_audit_run.job; Atlas guarded'
        provenance = None
    else:
        bars = load_master(('M15', 'M1', 'D1'), start=a, end=b)
        config = EngineConfig.live_parity_preset(
            sizing_mode='fixed', fixed_lots=0.02, starting_balance=5000.,
            max_concurrent=3, max_same_direction=3, history_bars=7500,
            protect_profit=False, m1_policy='skip')
        result = BacktestEngine(bars, SCENARIOS['realistic_ecn'], config).run(
            [c() for c in PORTFOLIO], a, b)
        rows = [dataclasses.asdict(t) for t in result.trades]
        halts, diag, cfg = [], result.diagnostics, config.as_dict()
        provenance = getattr(bars, 'provenance', None)
    def default(v):
        return v.item() if hasattr(v, 'item') else str(v)
    data = dict(name=name, start=a, end=b, guarded=guarded, config=cfg,
                trades=rows, halts=halts, diagnostics=diag, provenance=provenance)
    (OUT / (name + '.json')).write_text(json.dumps(data, default=default), encoding='utf-8')
    p = np.array([t['net_pl'] for t in rows])
    eq = np.r_[5000., 5000. + p.cumsum()]
    summary = dict(trades=len(rows), net=float(p.sum()),
                   pf=float(p[p > 0].sum() / -p[p < 0].sum()) if (p < 0).any() else None,
                   win_pct=float(100 * (p > 0).mean()) if len(p) else 0,
                   realized_max_dd=float((np.maximum.accumulate(eq)-eq).max()),
                   halts=halts, diagnostics=diag,
                   trade_hash=hashlib.sha256(json.dumps(rows, sort_keys=True, default=default).encode()).hexdigest())
    print(name, json.dumps({k:v for k,v in summary.items() if k != 'diagnostics'}), flush=True)
    return name, summary

if __name__ == '__main__':
    from src.backtesting.master import WINDOWS
    jobs = [(n, a, b, True) for n,a,b in WINDOWS]
    jobs += [(f'OOS_{i+1}', utc(*a), utc(*b), False) for i,(a,b) in enumerate([
        ((2004,7,1),(2008,1,1)), ((2008,1,1),(2012,1,1)),
        ((2012,1,1),(2016,1,1)), ((2016,1,1),(2020,1,1)),
        ((2020,1,1),(2022,8,1))])]
    report = {}
    with ProcessPoolExecutor(2) as pool:
        for name, result in pool.map(job, *zip(*jobs)):
            report[name] = result
            (OUT/'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
