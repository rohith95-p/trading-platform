import zipfile,pandas as pd,numpy as np,sys
from pathlib import Path
base=Path(sys.argv[1])
for i,mon in enumerate(pd.period_range('2022-09','2026-10',freq='M'),1):
 p=Path('research/xauusd_archive/payload/exness/XAUUSDm')/f'Exness_XAUUSDm_{mon.year}_{mon.month:02d}.zip'
 ticks=base/f'ticks{i}.bin'
 with zipfile.ZipFile(p) as z,z.open(z.namelist()[0]) as f,ticks.open('wb') as out:
  for chunk in pd.read_csv(f,usecols=['Timestamp','Bid','Ask'],chunksize=400000):
   a=np.empty(len(chunk),dtype=[('ms','<i8'),('b','<f8'),('a','<f8')])
   a['ms']=pd.to_datetime(chunk.Timestamp,format='ISO8601',utc=True).dt.as_unit('ms').astype('int64')
   a['b']=chunk.Bid;a['a']=chunk.Ask;a.tofile(out)
 q=np.memmap(ticks,dtype=a.dtype,mode='r')
 minute=q['ms']//60000
 starts=np.r_[0,np.flatnonzero(np.diff(minute))+1]
 ends=np.r_[starts[1:],len(q)]
 r=np.empty(len(starts),dtype=[('ts','<i8'),('o','<f8'),('h','<f8'),('l','<f8'),('c','<f8'),('vol','<i8'),('spread','<i8')])
 r['ts']=minute[starts]*60;r['o']=q['b'][starts];r['c']=q['b'][ends-1]
 r['h']=np.maximum.reduceat(q['b'],starts);r['l']=np.minimum.reduceat(q['b'],starts)
 r['vol']=ends-starts;r['spread']=np.rint(np.minimum.reduceat(q['a']-q['b'],starts)*1000)
 r.tofile(base/f'rates{i}.bin')
 print(i,mon,len(q),flush=True)
