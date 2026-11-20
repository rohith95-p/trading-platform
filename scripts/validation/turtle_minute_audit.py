"""Offline M1 refinement plus independently reconstructed opening-quote equity."""
import gc
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from src.backtesting.master import load_master
from src.backtesting.costs import SCENARIOS
from src.backtesting.access import AccessAccount
from src.research.dated_results import save_result
from scripts.research.turtle_s2 import prepare,replay
from scripts.validation.full_metric_suite import ratios


def opening_equity(frame,records,cost):
    if cost.triple_swap_weekday is not None:
        raise ValueError('Vector audit requires explicitly implemented triple-swap schedule')
    times = np.r_[frame.time.to_numpy(dtype=np.int64),int(frame.time.iloc[-1])+60]
    quotes = np.r_[frame.open.to_numpy(),frame.close.iloc[-1]]
    points = np.r_[frame.spread.to_numpy(),frame.spread.iloc[-1]]
    spread = np.where(points>0,points,cost.fixed_spread_points)*.001*cost.spread_multiplier
    events = np.zeros(len(times))
    floating = np.zeros(len(times))
    active = np.zeros(len(times),dtype=np.int16)
    rollover = cost.rollover_hour_utc*3600
    for record in records:
        end = int(times.searchsorted(record['time']))
        if end>=len(times):
            raise ValueError('Exit beyond available minute boundary')
        events[end] += record['pnl']
        side = record['side']
        for fill in record['fills']:
            start = int(times.searchsorted(fill['time'],side='right'))
            if start>=end:
                continue
            marks = quotes[start:end]+(spread[start:end] if side==-1 else 0)
            floating[start:end] += 2*side*(marks-fill['price'])-cost.commission(.02)/2
            if cost.enable_swap:
                nights = (times[start:end]-rollover)//86400-(fill['time']-rollover)//86400
                daily = (cost.swap_long_points if side==1 else cost.swap_short_points)*.001*2
                floating[start:end] += nights*daily
            active[start:end] += 1
    realized = events.cumsum()
    if not np.isclose(realized[-1],sum(r['pnl'] for r in records),atol=1e-8):
        raise ValueError('Reconstructed cash fails ledger reconciliation')
    return times,realized,floating,active


def account_scenario(times,realized,floating,active,records,phase):
    account = AccessAccount(phase,int(times[0]))
    engine = SimpleNamespace(balance=5000.,positions=[],trades=[],stub=SimpleNamespace())
    current_float = 0.
    engine.floating_pl = lambda: current_float
    cursor = 0
    withdrawn = 0.
    status = 'sample_ended'
    stopped_at = int(times[-1])
    for i,ts in enumerate(times):
        while cursor<len(records) and records[cursor]['time']<=ts:
            r = records[cursor]
            engine.trades.append(SimpleNamespace(exit_time=r['time'],net_pl=r['pnl']))
            cursor += 1
        engine.balance = 5000.+realized[i]-withdrawn
        engine.positions = [True] if active[i] else []
        current_float = float(floating[i])
        if account.observe(engine,int(ts)):
            status = account.status
            stopped_at = int(ts)
            break
        if phase=='funded' and current_float<=-.02*account.anchor:
            status = 'protector_liquidation_required'
            stopped_at = int(ts)
            break
        withdrawn = 5000.+realized[i]-engine.balance
    return dict(status=status,stopped_at=stopped_at,
                stopped_utc=pd.Timestamp(stopped_at,unit='s',tz='UTC').isoformat(),
                balance_usd=float(engine.balance),marked_equity_usd=float(engine.balance+current_float),
                hypothetical_cash_payouts=account.payouts,
                hypothetical_cash_total=float(sum(p['cash'] for p in account.payouts)),
                caveat='Limited sampled scenario, not full Atlas validation or pass/payout probability.')


def sequential_scenario(times,realized,floating,active,records,evaluation):
    if evaluation['status']!='passed':
        return dict(status='not_started_evaluation_not_passed',hypothetical_cash_total=0.)
    i = int(times.searchsorted(evaluation['stopped_at']))
    if active[i]:
        raise ValueError('Funded transition must start flat')
    later = [r for r in records if r['entry_time']>=int(times[i])]
    result = account_scenario(times[i:],realized[i:]-realized[i],floating[i:],active[i:],later,'funded')
    result['assumed_activation'] = 'Immediate fresh $5000 funded account, no activation fee or account-creation delay.'
    return result


def main():
    risk_only = '--risk-only' in sys.argv
    output = Path('research/registry/turtle_minute_audit.json')
    if risk_only:
        report = json.loads(output.read_text())
        backup = output.with_name('turtle_minute_audit_initial_risk.json')
        if not backup.exists():
            backup.write_bytes(output.read_bytes())
    else:
        report = dict(method='M1 execution, fixed M15 daily signal, minute-opening equity sampling',results={})
    report['risk_analysis_runner_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    source = pd.DataFrame(load_master(('M15',),end=1767225600).m15)
    source.index = pd.to_datetime(source.time.to_numpy(),unit='s',utc=True)
    source = prepare(source)
    names = ['n_value','entry_high','entry_low','exit_high','exit_low']
    features = source.groupby('session')[names].first()
    del source
    gc.collect()
    cost = SCENARIOS['realistic_ecn']
    for first,last in [(2005,2011),(2012,2018),(2019,2025)]:
        start = int(pd.Timestamp(str(first),tz='UTC').timestamp())
        end = int(pd.Timestamp(str(last+1),tz='UTC').timestamp())
        raw = load_master(('M1',),start=start,end=end,use_cache=False).m1
        raw = raw[(raw['time']>=start)&(raw['time']<end)]
        digest = hashlib.sha256(str(raw.dtype.descr).encode()+raw.tobytes()).hexdigest()
        frame = pd.DataFrame(raw[['time','open','high','low','close','spread']])
        frame.index = pd.to_datetime(frame.time.to_numpy(),unit='s',utc=True)
        frame['session'] = (frame.index.tz_convert('America/New_York').tz_localize(None)+pd.Timedelta(hours=7)).normalize()
        frame = frame.join(features,on='session')
        coverage = dict(rows=len(frame),input_content_sha256=digest,
                        gaps_over_one_minute=int(sum(np.diff(raw['time'])>60)),
                        maximum_gap_seconds=int(np.diff(raw['time']).max()))
        del raw
        for max_units in (1,4):
            tag = f'{max_units}unit {first}-{last}'
            if risk_only:
                records = report['results'][tag]['baskets']
                diagnostics = report['results'][tag]['diagnostics']
                if coverage['input_content_sha256']!=report['results'][tag]['coverage']['input_content_sha256']:
                    raise ValueError('Risk replay requires the original execution quotes')
            else:
                records,diagnostics = replay(frame,max_units,cost,bar_seconds=60)
            p = np.array([r['pnl'] for r in records])
            dates = pd.to_datetime([r['time']-1 for r in records],unit='s',utc=True)
            if not risk_only:
                save_result('turtle_s2_m1_'+str(max_units)+'unit',pd.Series(p,index=dates),f'{first}-01-01',f'{last}-12-31',
                            specification='research/registry/PREREG_TurtleMinuteAudit_2026-11-11.md',runner=__file__)
            times,realized,floating,active = opening_equity(frame,records,cost)
            equity = 5000.+realized+floating
            peak = np.maximum.accumulate(equity)
            stats = ratios(p,7)
            case = dict(metrics=stats,coverage=coverage,diagnostics=diagnostics,baskets=records,
                        sampled_opening_equity_max_dd_usd=float(np.max(peak-equity)),
                        sampled_opening_equity_max_dd_pct=float(100*np.max((peak-equity)/peak)),
                        evaluation=account_scenario(times,realized,floating,active,records,'evaluation'),
                        funded=account_scenario(times,realized,floating,active,records,'funded'))
            # Assumed .01-lot counterfactual: all cash values scale linearly,
            # with the same fills/signals. Actual Atlas lot rules remain unknown.
            half_records = [dict(r,pnl=r['pnl']*.5) for r in records]
            case['assumed_001_lot_unit'] = dict(
                evaluation=account_scenario(times,realized*.5,floating*.5,active,half_records,'evaluation'),
                funded=account_scenario(times,realized*.5,floating*.5,active,half_records,'funded'))
            case['funded_after_evaluation'] = sequential_scenario(times,realized,floating,active,records,case['evaluation'])
            half = case['assumed_001_lot_unit']
            half['funded_after_evaluation'] = sequential_scenario(times,realized*.5,floating*.5,active,half_records,half['evaluation'])
            report['results'][tag] = case
            print(tag,len(p),stats['profit_factor'],stats['net'],case['sampled_opening_equity_max_dd_pct'],
                  case['evaluation']['status'],case['funded']['status'],case['funded']['hypothetical_cash_total'],flush=True)
            Path('research/registry/turtle_minute_audit.json').write_text(json.dumps(report,indent=2,allow_nan=False))
            del times,realized,floating,active,equity,peak
        del frame
        gc.collect()


if __name__=='__main__':
    main()
