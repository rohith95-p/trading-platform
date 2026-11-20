"""Reproduce full and truncated benchmark windows without overwriting old results."""
import json
import os
from pathlib import Path

os.environ['ULTRA_DISABLE_ALERTS']='1'
os.environ['ULTRA_NO_TRIAL_LEDGER']='1'
from scripts.validation.independent_audit_run import job,utc
from src.backtesting.master import window


def main():
    root=Path('research/results/fresh_recent_2026-11-11')
    root.mkdir(parents=True,exist_ok=True)
    a,b=window('RECENT')
    results={}
    for name,start,end in [('RECENT',a,b),('RECENT_CUT',a,utc(2026,9,15))]:
        _,tr,halts,m1=job(name,start,end)
        results[name]=dict(trades=tr,halts=halts,m1=m1)
        print(name,len(tr),round(sum(t['net_pl'] for t in tr),2),flush=True)
    (root/'trades.json').write_text(json.dumps(results),encoding='utf-8')


if __name__=='__main__':
    main()
