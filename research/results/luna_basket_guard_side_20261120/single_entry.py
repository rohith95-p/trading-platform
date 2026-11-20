"""Single-entry alternative using only the first signal from each recorded Luna basket."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from replay import BASE,SOURCE,OUTPUT,DTYPE,DAY,split_baskets


def test(deals, folder):
    monthly = {m:np.memmap(folder/f"ticks{m}.bin",dtype=DTYPE,mode="r") for m in range(5,11)}
    trades=[]
    last_exit=0
    day_pnl={}
    for basket in split_baskets(deals):
        signal=basket[0]
        start=int(signal['ts']*1000)
        if start<=last_exit or day_pnl.get(start//DAY,0)<=-20: continue
        m=pd.Timestamp(start,unit='ms',tz='UTC').month
        q=monthly[m]
        a,b=q['ms'].searchsorted([start,start+3600000])
        # Include the first observed quote at the 60-minute timeout, including session gaps.
        v=q[a:min(b+1,len(q))]
        if len(v)==0: continue
        side=signal['side']
        mark=v['bid']-signal['price'] if side=='buy' else signal['price']-v['ask']
        hit=np.flatnonzero((mark<=-10)|((v['ms']>=start+181000)&(mark>=2)))
        j=int(hit[0]) if len(hit) else len(v)-1
        last_exit=int(v['ms'][j])
        pnl=float(mark[j])-.10
        day_pnl[last_exit//DAY]=day_pnl.get(last_exit//DAY,0)+pnl
        trades.append(pnl)
    r=np.array(trades)
    return dict(trades=len(r), net=round(float(r.sum()),2), pf=round(float(r[r>0].sum()/-r[r<0].sum()),3),win_pct=round(float((r>0).mean()*100),2),best_removed=round(float(r.sum()-r.max()),2))
if __name__=='__main__':
    results={}
    for name,folder in [('broker_evaluation',BASE/'Luna'/'direct_quote_cache'),('evaluation',BASE/'Velora'/'MQL5'/'Files'/'LunaArchive')]:
        results[name]=test(json.loads((SOURCE/f'{name}.json').read_text())['deals'],folder)
    print(results)
    (OUTPUT/'single_entry_results.json').write_text(json.dumps(results,indent=2))
