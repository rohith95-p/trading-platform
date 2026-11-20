"""Run from project root: python -m scripts.research.gold_iv_premium."""
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import requests

from scripts.validation.full_metric_suite import ratios
from src.backtesting.costs import SCENARIOS
from src.backtesting.master import load_master
from src.backtesting.metrics import drop_best_worst, monte_carlo_paths
from src.research.metrics import bonferroni_correction
from src.research.dated_results import save_result


def main():
    archive = Path('research/data/gvz_through_2025.csv')
    if not archive.exists():
        response = requests.get('https://cdn.cboe.com/api/global/us_indices/daily_prices/GVZ_History.csv', timeout=30)
        response.raise_for_status()
        gvz = pd.read_csv(io.BytesIO(response.content), parse_dates=['DATE']).set_index('DATE').sort_index()
        gvz.loc[:'2025'].to_csv(archive)
    gvz = pd.read_csv(archive, parse_dates=['DATE']).set_index('DATE')
    raw = load_master(('M15',), end=int(pd.Timestamp('2026-01-01',tz='UTC').timestamp())).m15
    frame = pd.DataFrame(raw)
    frame.index = pd.to_datetime(frame.time.to_numpy(),unit='s',utc=True).tz_convert('America/New_York')
    def quotes(clock):
        cut = frame.at_time(clock)[['open','spread']].copy()
        cut.index = cut.index.tz_localize(None).normalize()
        return cut
    morning = quotes('09:45')
    afternoon = quotes('15:45').open.rename('exit')
    rv = np.log(afternoon).diff().rolling(21).std()*100*np.sqrt(252)
    premium = (gvz.GVZ-rv).dropna()
    threshold = premium.shift().rolling(252).quantile(.8)
    signals = pd.DataFrame({'active':premium>threshold},index=premium.index)[threshold.notna()]
    market = morning.join(afternoon,how='inner')
    signals.index = signals.index.as_unit('ns')
    market.index = market.index.as_unit('ns')
    data = pd.merge_asof(market,signals,left_index=True,right_index=True,allow_exact_matches=False,
                         tolerance=pd.Timedelta(days=4)).dropna()
    cost = SCENARIOS['realistic_ecn']
    data['pnl'] = 2*(data.exit-data.open-data.spread.map(lambda s:cost.spread_price(.001,s))-2*cost.slip(.001))-cost.commission(.02)
    report = {'input_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'eras':{}}
    rng = np.random.default_rng(112025)
    for first,last in [('2011','2015'),('2016','2020'),('2021','2025')]:
        era = data.loc[first:last]
        trades = era.loc[era.active.astype(bool),'pnl']
        save_result('gold_iv_premium',trades,first+'-01-01',last+'-12-31',
                    specification='research/registry/PREREG_GoldIVPremium_2026-11-11.md',runner=__file__)
        stats = ratios(trades.to_numpy(),5)
        null = np.zeros(2000)
        for _,year in era.groupby(era.index.year):
            count = int(year.active.sum())
            null += [rng.choice(year.pnl.to_numpy(),count,replace=False).sum() for _ in null]
        monthly = trades.resample('ME').agg(['sum','count']).to_numpy()
        draws = monthly[rng.integers(len(monthly),size=(5000,len(monthly)))].sum(axis=1)
        records = [SimpleNamespace(net_pl=x) for x in trades]
        stats.update(wins=int((trades>0).sum()),eligible=len(era),control_median=float(np.median(null)),
                     bonferroni_p=bonferroni_correction((1+sum(null>=trades.sum()))/2001,3),
                     month_ci=np.quantile(draws[:,0]/draws[:,1],[.025,.975]).tolist(),
                     monte_carlo=monte_carlo_paths(records,5000),ablation=drop_best_worst(records),
                     dsr=None,expected_max_sr=None,
                     reason='No complete calendar-aligned return series for the full search family')
        report['eras'][first+'-'+last]=stats
        print(first,last,len(trades),stats['wins'],stats['profit_factor'],stats['net'],stats['control_median'],stats['month_ci'])
    Path('research/registry/gold_iv_premium_metrics.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
