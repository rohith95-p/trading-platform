"""Independent XAUUSD adaptation of a documented prior-day range breakout."""
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import monte_carlo_paths, drop_best_worst
from src.research.dated_results import save_result
from scripts.validation.full_metric_suite import ratios


def replay(frame):
    cost = SCENARIOS['realistic_ecn']
    clock = frame.index.tz_convert('America/New_York').tz_localize(None) + pd.Timedelta(hours=7)
    daily = frame.assign(day=clock.normalize()).groupby('day').agg(high=('high','max'),low=('low','min'))
    previous = daily.shift(1)
    previous['age'] = daily.index.to_series().diff().dt.days
    previous.iloc[:2] = np.nan  # Initial, potentially partial, day cannot set levels.
    position = None
    pending = None
    day = None
    used = set()
    records = []
    ambiguous = 0
    last_time = None

    for row, local in zip(frame.itertuples(), clock):
        today = local.normalize()
        hour = local.hour + local.minute / 60
        spread = cost.spread_price(.001, row.spread)

        def finish(price, when, reason):
            start, entry, side, stop, target, entry_day = position
            pnl = 2 * side * (price-entry) - cost.commission(.02)
            pnl += cost.swap(.02, side == 1, start, when, .001, 100)
            records.append(dict(time=int(when), pnl=float(pnl), reason=reason))

        if position and (today != position[5] or hour >= 23):
            side = position[2]
            finish(row.open + (spread if side == -1 else 0) - side*.02, int(row.time), 'clock')
            position = None
        if today != day:
            day, used = today, set()
        if pending:
            side, stop, signal_day, signal_time = pending
            if position is None and today == signal_day and hour < 20 and row.time == signal_time+900:
                entry = row.open + (spread if side == 1 else 0) + side*.02
                risk = side*(entry-stop)
                if risk > 0:
                    position = (int(row.time), entry, side, stop, entry+side*2*risk, today)
            pending = None
        if position:
            side, stop, target = position[2:5]
            ask = spread if side == -1 else 0
            stop_hit = row.low <= stop if side == 1 else row.high+ask >= stop
            target_hit = row.high >= target if side == 1 else row.low+ask <= target
            ambiguous += int(stop_hit and target_hit)
            if stop_hit:
                opening = row.open+ask
                price = min(opening,stop) if side == 1 else max(opening,stop)
                finish(price-side*.02, int(row.time)+900, 'stop')
                position = None
            elif target_hit:
                finish(target-side*.02, int(row.time)+900, 'target')
                position = None
        levels = previous.loc[today]
        if hour >= 1 and np.isfinite(levels.high) and levels.age <= 7:
            side = 1 if row.close > levels.high else (-1 if row.close < levels.low else 0)
            if side and side not in used:
                used.add(side)
                if position is None:
                    pending = (side, levels.low if side == 1 else levels.high, today, int(row.time))
        last_time = int(row.time)+900
    if position:
        side = position[2]
        finish(row.close+(spread if side == -1 else 0)-side*.02, last_time, 'boundary')
    return records, ambiguous


def main():
    f = pd.DataFrame(load_master(('M15',),end=1767225600).m15)
    f.index = pd.to_datetime(f.time.to_numpy(),unit='s',utc=True)
    report = {}
    for first,last in [('2005','2011'),('2012','2018'),('2019','2025')]:
        records, ambiguous = replay(f.loc[first:last])
        p = np.array([r['pnl'] for r in records])
        dates = pd.to_datetime([r['time']-1 for r in records],unit='s',utc=True)
        save_result('prior_day_breakout',pd.Series(p,index=dates),first+'-01-01',last+'-12-31',
                    specification='research/registry/PREREG_PriorDayBreakout_2026-11-11.md',runner=__file__)
        stats = ratios(p,7)
        tr = [SimpleNamespace(net_pl=x) for x in p]
        stats.update(wins=int(sum(p>0)),ambiguous_bars=ambiguous,
                     ablation=drop_best_worst(tr),monte_carlo=monte_carlo_paths(tr,5000))
        report[first+'-'+last] = stats
        print(first,last,len(p),stats['wins'],stats['profit_factor'],stats['net'],ambiguous,flush=True)
    Path('research/registry/prior_day_breakout.json').write_text(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
