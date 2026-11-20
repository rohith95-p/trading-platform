"""M1 execution of original exported Genesis M5 signals; explicit policy variants."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
from src.backtesting.costs import SCENARIOS
from scripts.research.genesis_management import ManagementState,management_actions
from scripts.validation.full_metric_suite import ratios


def learning_multiplier(history):
    if len(history)<10:
        return 1.
    wins = sum(pnl>0 for pnl,r in history)/len(history)
    avg_r = sum(r for pnl,r in history)/len(history)
    return max(.5,min(1.5,1+(wins-.5)*.6+max(-2,min(2,avg_r))*.1))


def simulate_trade(raw,start,signal,cost,policy,known_atr):
    side = 1 if signal['direction']=='BUY' else -1
    slip = cost.slip(.001)
    first = raw[start]
    spread = cost.spread_price(.001,first['spread'])
    entry = first['open']+(spread if side==1 else 0)+side*slip
    risk = signal['sl_distance']
    stop,target = entry-side*risk,entry+side*signal['tp_distance']
    initial_stop = stop
    quantity = .02
    total,swap_total = 0.,0.
    peak,partial,be = 0.,False,False
    counts = dict(partials=0,stop_modifications=0,rejected_stop_modifications=0)
    legs = []
    entry_time = int(first['time'])
    def realize(price,lot,when):
        swap = cost.swap(lot,side==1,entry_time,when,.001,100)
        cash = lot*100*side*(price-entry)-cost.commission(lot)+swap
        legs.append(dict(time=int(when),lots=float(lot),price=float(price),pnl=float(cash),swap=float(swap)))
        return cash,swap
    for j in range(start,len(raw)):
        r = raw[j]
        ts = int(r['time'])
        spread = cost.spread_price(.001,r['spread'])
        ask = spread if side==-1 else 0
        opening = r['open']+ask
        reason = None
        if side*(opening-stop)<=0:
            price,reason = opening-side*slip,'gap_stop'
        elif side*(opening-target)>=0:
            price,reason = target,'target'
        at_open = reason is not None
        if reason is None and policy!='static':
            reference = stop if policy=='original_wiring' else initial_stop
            manager = ManagementState(side,entry,reference,stop,opening,float(known_atr[j]),peak,partial,be)
            actions = management_actions(manager)
            peak = actions['peak']
            r_now = side*(opening-entry)/abs(entry-reference) if reference!=entry else 0.
            for action in actions['actions']:
                if action['action']=='CLOSE_FULL':
                    price,reason = opening-side*slip,'manager_full'
                    at_open = True
                    break
                if action['action']=='PARTIAL_CLOSE' and quantity>=.02-1e-9:
                    amount = .01
                    cash,swap = realize(opening-side*slip,amount,ts)
                    total += cash
                    swap_total += swap
                    quantity -= amount
                    partial = True
                    counts['partials'] += 1
                elif action['action']=='MODIFY_SL':
                    candidate = action['new_sl']
                    if side*(opening-candidate)>0:
                        stop = candidate
                        counts['stop_modifications'] += 1
                    else:
                        counts['rejected_stop_modifications'] += 1
            be = be or r_now>=.5
        if reason is None:
            stop_hit = r['low']<=stop if side==1 else r['high']+ask>=stop
            target_hit = r['high']>=target if side==1 else r['low']+ask<=target
            if stop_hit:
                price,reason = stop-side*slip,'stop'
            elif target_hit:
                price,reason = target,'target'
        if reason is not None:
            # End-of-minute timestamp avoids re-entry before an intraminute stop.
            exit_time = ts if at_open else ts+60
            cash,swap = realize(price,quantity,exit_time)
            total += cash
            swap_total += swap
            break
    else:
        j = len(raw)-1
        r = raw[j]
        exit_time = int(r['time'])+60
        exit_price = r['close']+(cost.spread_price(.001,r['spread']) if side==-1 else 0)-side*slip
        cash,swap = realize(exit_price,quantity,exit_time)
        total += cash
        swap_total += swap
        reason = 'boundary'
    return dict(entry_time=entry_time,exit_time=exit_time,pnl=float(total),swap=float(swap_total),
                next_entry_time=int(raw[j]['time'])+60,
                side=side,entry=float(entry),initial_risk=float(risk),reason=reason,exits=legs,**counts)


def sampled_equity(raw,trades,cost):
    times = np.r_[raw['time'],int(raw['time'][-1])+60]
    quotes = np.r_[raw['open'],raw['close'][-1]]
    points = np.r_[raw['spread'],raw['spread'][-1]]
    spread = np.where(points>0,points,260)*.001
    cash = np.zeros(len(times))
    floating = np.zeros(len(times))
    for trade in trades:
        start = int(times.searchsorted(trade['entry_time']))
        side = trade['side']
        for leg in trade['exits']:
            end = int(times.searchsorted(leg['time']))
            cash[end] += leg['pnl']
            marks = quotes[start:end]+(spread[start:end] if side==-1 else 0)-side*cost.slip(.001)
            floating[start:end] += leg['lots']*100*side*(marks-trade['entry'])-cost.commission(leg['lots'])
            if cost.enable_swap:
                nights = times[start:end]//86400-trade['entry_time']//86400
                swap_rate = cost.swap_long_points if side==1 else cost.swap_short_points
                floating[start:end] += nights*swap_rate*.001*100*leg['lots']
    equity = 5000.+cash.cumsum()+floating
    if not np.isclose(equity[-1]-5000,sum(t['pnl'] for t in trades),atol=1e-7):
        raise ValueError('Genesis equity does not reconcile to trade cash')
    peak = np.maximum.accumulate(np.r_[5000.,equity])
    e = np.r_[5000.,equity]
    return dict(sampled_liquidation_max_dd_usd=float(np.max(peak-e)),
                sampled_liquidation_max_dd_pct=float(100*np.max((peak-e)/peak)),
                sampled_minimum_equity_usd=float(e.min()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('year',type=int)
    args = parser.parse_args()
    root = Path('research/results/genesis_2026-11-11')
    path = root/f'{args.year}.signals.jsonl.gz'
    meta = json.loads(path.with_suffix('.manifest.json').read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest()!=meta['signals_sha256']:
        raise ValueError('Signal export changed')
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        signals = [json.loads(line) for line in stream]
    raw_path = Path(meta['inputs']['M1']['path'])
    if hashlib.sha256(raw_path.read_bytes()).hexdigest()!=meta['inputs']['M1']['sha256']:
        raise ValueError('Minute snapshot changed')
    raw = np.load(raw_path,allow_pickle=False)
    raw = raw[(raw['time']>=meta['start'])&(raw['time']<meta['end'])]
    names = list(signals[0]['signals'])
    times = np.array([r['decision_time_utc'] for r in signals],dtype=np.int64)
    atr = np.array([r['market']['atr'] for r in signals])
    idx = times.searchsorted(raw['time'],side='right')-1
    known_atr = np.where(idx>=0,atr[np.maximum(idx,0)],np.nan)
    available = {name:0 for name in names}
    for row in signals:
        for name in names:
            available[name] += row['signals'][name]['direction']!='NONE'
    report = dict(year=args.year,signal_decisions=len(signals),raw_signal_counts=available,
                  signal_export_sha256=meta['signals_sha256'],results={},
                  caveat='Closed M5 signals, minute manager cadence, fixed .02lot; not full Genesis or Atlas validation.')
    cost = SCENARIOS['realistic_ecn']
    for route in names+['selector_top_fitness','neutral_history_first_actionable','learning_first_actionable']:
        for policy in ('static','original_wiring','constant_initial_risk'):
            trades = []
            busy = meta['start']
            missing_quotes = 0
            invalid_brackets = 0
            history = {name:[] for name in names}
            for row in signals:
                ts = row['decision_time_utc']
                if ts<busy:
                    continue
                if route=='learning_first_actionable':
                    ranked = sorted(names,key=lambda name:row['fitness'][name]*learning_multiplier(history[name]),reverse=True)
                    chosen = next((name for name in ranked if row['signals'][name]['direction']!='NONE'),None)
                else:
                    chosen = route if route in names else row[route]
                if chosen is None:
                    continue
                s = row['signals'][chosen]
                if s['direction']=='NONE':
                    continue
                if s['sl_distance']<=0 or s['tp_distance']<=0:
                    raise ValueError('Actionable original signal has invalid distances')
                i = int(raw['time'].searchsorted(ts))
                if i>=len(raw) or raw['time'][i]!=ts:
                    missing_quotes += 1
                    continue
                if s['sl_distance']<=cost.spread_price(.001,raw['spread'][i])+cost.slip(.001):
                    invalid_brackets += 1
                    continue
                trade = simulate_trade(raw,i,s,cost,policy,known_atr)
                trade['chosen_strategy'] = chosen
                trades.append(trade)
                history[chosen].append((trade['pnl'],trade['pnl']/(2*trade['initial_risk'])))
                busy = trade['next_entry_time']
            p = np.array([t['pnl'] for t in trades])
            stats = ratios(p,1)
            stats.update(sampled_equity(raw,trades,cost))
            stats.update(baskets=trades,missing_entry_quotes=missing_quotes,
                         invalid_initial_brackets=invalid_brackets,
                         partial_closes=sum(t['partials'] for t in trades),
                         rejected_modifications=sum(t['rejected_stop_modifications'] for t in trades))
            report['results'][route+' '+policy] = stats
            print(args.year,route,policy,len(p),stats['profit_factor'],stats['net'],flush=True)
            (root/f'{args.year}.backtest.json').write_text(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':
    main()
