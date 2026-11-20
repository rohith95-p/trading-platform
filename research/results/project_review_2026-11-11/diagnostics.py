"""Independent arithmetic and provenance checks. No terminal/network access."""
import ast
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT))
from src.core.sizing_ladder import SizingLadder
from src.research.ledger import trial_id
from src.backtesting.data import BarSet, SymbolSpec
from src.backtesting.metrics import k_eff_correction

inventory = {}
for folder in ('src', 'scripts', 'tests'):
    files = list((ROOT/folder).rglob('*.py'))
    inventory[folder] = {'files': len(files), 'lines': 0, 'functions': 0, 'classes': 0}
    for p in files:
        text = p.read_text(encoding='utf-8-sig')
        tree = ast.parse(text)
        inventory[folder]['lines'] += len(text.splitlines())
        inventory[folder]['functions'] += sum(isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) for x in ast.walk(tree))
        inventory[folder]['classes'] += sum(isinstance(x, ast.ClassDef) for x in ast.walk(tree))

data = []
for p in (ROOT/'research').rglob('*.npy'):
    a = np.load(p, mmap_mode='r')
    item = {'path': str(p.relative_to(ROOT)), 'rows': len(a), 'bytes': p.stat().st_size}
    if 'time' in (a.dtype.names or ()) and len(a):
        t = a['time']
        item.update(first=int(t[0]), last=int(t[-1]), duplicate_or_reversed=int((np.diff(t)<=0).sum()))
    mf = p.with_suffix('.manifest.json')
    if mf.exists():
        m = json.loads(mf.read_text())
        actual = hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
        item['manifest_hash_matches'] = actual == m['sha256']
    data.append(item)

# Same number and size of losses: std(losses) is zero, but downside risk is real.
p = np.array([2., -1., 2., -1.])
sortino = dict(example=p.tolist(), current_downside_std=float(np.std(p[p<0])),
               target_semideviation=float(np.sqrt(np.mean(np.minimum(p,0)**2))),
               target_sortino=float(p.mean()/np.sqrt(np.mean(np.minimum(p,0)**2))))

# These are identical per-trade outcomes at unrelated dates. Trade-index
# alignment reports perfect correlation without knowing they never overlap.
s = [1., -2., 3., -1., 2., -3.]
keff = k_eff_correction([s,s], 2)
spec = SymbolSpec('XAUUSDm',3,.001,.001,.1,.01,200.,.01,100.)
a = np.zeros(2, dtype=[('time','i8'),('close','f8')])
b = a.copy()
b['close'] = 999.
hashes = [BarSet('XAUUSDm',x,None,None,None,spec,{}).hash_key() for x in (a,b)]

log_summary = {}
for p in (ROOT/'logs'/'trades').glob('*.jsonl'):
    counts = Counter()
    total = malformed = 0
    with p.open(encoding='utf-8-sig') as f:
        for line in f:
            try:
                r = json.loads(line)
                counts[str(r.get('event', r.get('type', 'unknown')))] += 1
                total += 1
            except (ValueError, TypeError):
                malformed += 1
    log_summary[p.name] = dict(rows=total, malformed=malformed, events=dict(counts))

report = dict(inventory=inventory, data=data, sortino_demonstration=sortino,
              keff_without_date_alignment=keff,
              distinct_master_arrays_same_hash=hashes,
              sizing_example=dict(balance=5000, lots=.02, gold_price_stop_distance=10,
                  helper_risk_fraction=SizingLadder.get_risk_pct(5000,.02,10),
                  contract_aware_risk_fraction=.02*100*10/5000),
              ledger_id_inputs='strategy names, window, EngineConfig, costs; no strategy parameters/code/data hash',
              sample_ledger_id=trial_id(['EXAMPLE'], [1,2], {'fixed_lots':.02}, 'same-cost'),
              local_trade_log_summary=log_summary)
(OUT/'diagnostics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('data','local_trade_log_summary')}, indent=2))
print('datasets', len(data), 'manifest_mismatches', sum(x.get('manifest_hash_matches') is False for x in data))
