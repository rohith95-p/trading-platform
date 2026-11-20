"""Freeze M1 inputs and complete M5 aggregates for the original-bytecode worker."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from src.backtesting.master import load_master


def aggregate_m5(raw):
    t = raw['time']
    starts = np.flatnonzero(t%300==0)
    starts = starts[starts+4<len(raw)]
    for k in range(1,5):
        starts = starts[t[starts+k]==t[starts]+60*k]
    out = np.zeros(len(starts),dtype=raw.dtype)
    out['time'] = t[starts]
    out['open'] = raw['open'][starts]
    out['close'] = raw['close'][starts+4]
    out['high'] = np.max(np.stack([raw['high'][starts+k] for k in range(5)]),axis=0)
    out['low'] = np.min(np.stack([raw['low'][starts+k] for k in range(5)]),axis=0)
    out['spread'] = raw['spread'][starts]
    for name in ('tick_volume','real_volume'):
        if name in raw.dtype.names:
            out[name] = sum(raw[name][starts+k] for k in range(5))
    return out


def main():
    root = Path('research/data/genesis')
    root.mkdir(parents=True,exist_ok=True)
    for year in (2013,2018,2025):
        start = int(pd.Timestamp(str(year),tz='UTC').timestamp())
        end = int(pd.Timestamp(str(year+1),tz='UTC').timestamp())
        raw = load_master(('M1',),start=start,end=end,use_cache=False).m1
        raw = raw[raw['time']>=start-7*86400]
        five = aggregate_m5(raw)
        paths = {}
        for tf,a in [('M1',raw),('M5',five)]:
            path = root/f'{year}_{tf}.npy'
            np.save(path,a,allow_pickle=False)
            paths[tf] = dict(path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=len(a))
        (root/f'{year}.json').write_text(json.dumps(dict(year=year,start=start,end=end,point=.001,inputs=paths),indent=2))
        print(year,len(raw),len(five),flush=True)


if __name__=='__main__':
    main()
