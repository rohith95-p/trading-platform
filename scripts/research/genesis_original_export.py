"""Run with the handoff CPython3.13 environment; original bytecode remains unchanged."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('year',type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    handoff = Path('C:/Users/rohit/OneDrive/Documents/Desktop/WMC Genesis/strategy_research')
    sys.path.insert(0,str(handoff))
    from load_original import load_original
    from export_signals import read_bars,evaluate_window
    Analyzer,Selector = load_original()
    analyzer,selector = Analyzer('XAUUSD.m'),Selector()
    import numpy as np
    meta = json.loads((root/f'research/data/genesis/{args.year}.json').read_text())
    path = Path(meta['inputs']['M5']['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['inputs']['M5']['sha256']:
        raise ValueError('Input snapshot changed')
    bars = read_bars(path)
    spreads = np.load(path,allow_pickle=False)['spread']
    out = root/f'research/results/genesis_2026-11-11/{args.year}.signals.jsonl.gz'
    out.parent.mkdir(parents=True,exist_ok=True)
    count = 0
    begun = time.perf_counter()
    progress = out.with_suffix('.progress.json')
    with gzip.open(out,'wt',encoding='utf-8') as stream:
        for end in range(300,len(bars)):
            ts = int(bars.time.iloc[end-1])+300
            if not meta['start']<=ts<meta['end']:
                continue
            window = bars.iloc[end-300:end]
            spread = float(spreads[end-1]) or 260.
            record = evaluate_window(analyzer,selector,window,ts,spread)
            record['next_bar_is_contiguous'] = int(bars.time.iloc[end])==ts
            record['spread_points_input'] = spread
            stream.write(json.dumps(record,allow_nan=False,ensure_ascii=False)+'\n')
            count += 1
            if count%1000==0:
                state = dict(decisions=count,last_decision=ts,elapsed_seconds=time.perf_counter()-begun)
                progress.write_text(json.dumps(state))
                print(args.year,count,round(state['elapsed_seconds'],1),flush=True)
    result = dict(**meta,decisions=count,elapsed_seconds=time.perf_counter()-begun,
                  signals_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
                  runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  bytecode_manifest=json.loads((handoff/'bytecode_manifest.json').read_text()),
                  exclusions=['full AIBrain','learning','confidence/confirmation','MTF','original trade management'])
    out.with_suffix('.manifest.json').write_text(json.dumps(result,indent=2))
    print(args.year,'COMPLETED',count,flush=True)


if __name__=='__main__':
    main()
