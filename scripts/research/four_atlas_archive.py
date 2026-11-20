"""Exness Standard quote archive used in the four-strategy comparison.

The sharing key for derived minutes is the hash of the original zip. Archive
order breaks ties at identical millisecond timestamps. The signal data carry
only bid bars, tick counts and the spread of the first quote in each bar.
"""
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

import numpy as np
import pandas as pd
from src.backtesting.data import BarSet, SymbolSpec

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / 'research/xauusd_archive/payload/exness/XAUUSDm'
COVERAGE = ROOT / 'research/results/luna_four_year_20261120/tick_coverage.json'
CACHE = Path(tempfile.gettempdir()) / 'UltraCoreFourArchive20261120'
LUNA = Path(tempfile.gettempdir()) / 'UltraEAReview20261120/Velora/MQL5/Files/LunaArchive48'
QUOTE = np.dtype([('ms','<i8'),('bid','<f8'),('ask','<f8')])
BAR = np.dtype([('time','<i8'),('open','<f8'),('high','<f8'),('low','<f8'),
                ('close','<f8'),('tick_volume','<u8'),('spread','<i4'),('real_volume','<u8')])


@lru_cache(None)
def coverage():
    return {row['month']:row for row in json.loads(COVERAGE.read_text())}


def _source(year, month):
    entry = coverage()[f'{year}-{month:02}']
    zip_path = ARCHIVE / f'Exness_XAUUSDm_{year}_{month:02}.zip'
    return zip_path, entry


@lru_cache(None)
def ticks_for_month(year, month):
    path, entry = _source(year, month)
    ordinal = (year-2022)*12 + month-9 + 1
    raw = LUNA / f'ticks{ordinal}.bin'
    if not raw.exists():
        CACHE.mkdir(exist_ok=True)
        raw = CACHE / (entry['sha256']+'.bin')
        if not raw.exists():
            tmp=raw.with_suffix(f'.{os.getpid()}.part')
            with path.open('rb') as f:
                if hashlib.file_digest(f,'sha256').hexdigest()!=entry['sha256']:
                    raise ValueError(f'Archive hash changed: {path}')
            with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as stream, tmp.open('wb') as out:
                for df in pd.read_csv(stream,usecols=['Timestamp','Bid','Ask'],chunksize=500000):
                    arr=np.empty(len(df),dtype=QUOTE)
                    arr['ms']=pd.to_datetime(df.Timestamp,format='ISO8601',utc=True).dt.as_unit('ms').astype('int64')
                    arr['bid'],arr['ask']=df.Bid,df.Ask
                    arr.tofile(out)
            tmp.replace(raw)
    arr = np.memmap(raw,dtype=QUOTE,mode='r')
    if len(arr)!=entry['ticks'] or any(
        ts != pd.Timestamp(entry[key]).value//1_000_000
        for ts,key in [(arr['ms'][0],'first'),(arr['ms'][-1],'last')]):
        raise ValueError(f'Quote coverage mismatch {year}-{month}')
    return arr


def _minutes(year, month):
    _,entry=_source(year,month)
    CACHE.mkdir(exist_ok=True)
    path=CACHE/(entry['sha256']+'-bid-open-spread-v1.npy')
    if path.exists():
        return np.load(path,allow_pickle=False)
    q=ticks_for_month(year,month)
    labels=q['ms']//60000
    idx=np.r_[0, np.flatnonzero(np.diff(labels))+1]
    ends=np.r_[idx[1:],len(labels)]
    result=np.zeros(len(idx),dtype=BAR)
    result['time']=labels[idx]*60
    result['open']=q['bid'][idx]
    result['high']=np.maximum.reduceat(q['bid'],idx)
    result['low']=np.minimum.reduceat(q['bid'],idx)
    result['close']=q['bid'][ends-1]
    result['spread']=np.rint((q['ask'][idx]-q['bid'][idx])*1000).astype('int32')
    result['tick_volume']=ends-idx
    tmp=path.with_suffix(f'.{os.getpid()}.npy')
    np.save(tmp,result)
    tmp.replace(path)
    return result


def _aggregate(minutes, step):
    keys=minutes['time']//step
    idx=np.r_[0,np.flatnonzero(np.diff(keys))+1]
    ends=np.r_[idx[1:],len(keys)]
    result=np.zeros(len(idx),dtype=BAR)
    result['time']=keys[idx]*step
    result['open']=minutes['open'][idx]
    result['high']=np.maximum.reduceat(minutes['high'],idx)
    result['low']=np.minimum.reduceat(minutes['low'],idx)
    result['close']=minutes['close'][ends-1]
    result['spread']=minutes['spread'][idx]
    result['tick_volume']=np.add.reduceat(minutes['tick_volume'],idx)
    return result


def load_bars(year=2026):
    if year not in (2025,2026):
        raise ValueError('Approved years are 2025 and 2026')
    last=10 if year==2026 else 12
    dates=[(year-1,m) for m in range(7,13)] + [(year,m) for m in range(1,last+1)]
    minutes=np.concatenate([_minutes(y,m) for y,m in dates])
    spec=SymbolSpec(**json.loads((ROOT/'research/data/XAUUSDm_M15.manifest.json').read_text())['spec'])
    bars=BarSet(symbol=spec.symbol,m1=minutes,m15=_aggregate(minutes,900),m5=None,
                d1=_aggregate(minutes,86400),spec=spec,manifests={})
    first=int(datetime(year,1,1,tzinfo=timezone.utc).timestamp())
    if np.count_nonzero(bars.m15['time']<first)<7500:
        raise ValueError('Insufficient M15 warm-up before first tradable date')
    return bars


if __name__=='__main__':
    b=load_bars()
    print('M1, M15, D1',len(b.m1),len(b.m15),len(b.d1),b.hash_key())
