"""Fixed-2oz buy/hold comparison, not a market-neutral alpha regression."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from scripts.research.forecast_fill_core import prepare


def main():
    path = Path('research/registry/forecast_fill_core.json')
    core = json.loads(path.read_text())
    f = pd.DataFrame(load_master(('M15',),end=1767225600).m15)
    f.index = pd.to_datetime(f.time.to_numpy(),unit='s',utc=True)
    f,_,_ = prepare(f)
    cost = SCENARIOS['realistic_ecn']
    report = dict(core_result_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),results={})
    for first,last in [(2015,2018),(2019,2021),(2022,2025)]:
        era = f.loc[(f.session>=str(first))&(f.session<f'{last+1}-01-01')]
        start,end = era.iloc[0],era.iloc[-1]
        entry = cost.ask(start.open,.001,start.spread)+cost.slip(.001)
        exit_price = end.close-cost.slip(.001)
        swap = cost.swap(.02,True,int(start.time),int(end.time)+900,.001,100)
        net = 2*(exit_price-entry)-cost.commission(.02)+swap
        key = f'{first}-{last}'
        record = dict(benchmark='uncapped_fixed_2oz_buy_hold',net_usd=float(net),
                      swap_usd=float(swap),core_net_usd=core['results'][key]['metrics']['net'],
                      caveat='No stops, margin liquidation or Atlas floors. Difference is dollar P&L, not risk-adjusted alpha.')
        record['core_minus_hold_usd'] = record['core_net_usd']-float(net)
        report['results'][key] = record
    Path('research/registry/forecast_fill_benchmark.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
