"""Reconcile the backtest engine against the broker (read-only MT5): same legs, window 2026-09-28..10-15.
Run: python scripts/validation/reconcile_live_vs_engine.py   (needs a running MT5 terminal; sends no orders)."""
import sys, os, json, datetime as dt, collections
sys.path.insert(0, r"C:\projects\ultra_core"); os.chdir(r"C:\projects\ultra_core")
import MetaTrader5 as mt5
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.strategies.portfolio_v5_core import PORTFOLIO_6_LEG
U=dt.timezone.utc; S=int(dt.datetime(2026,9,28,tzinfo=U).timestamp()); E=int(dt.datetime(2026,10,16,tzinfo=U).timestamp())
mt5.initialize()
deals=mt5.history_deals_get(dt.datetime.fromtimestamp(S,U),dt.datetime.fromtimestamp(E,U))
byp=collections.defaultdict(list)
for d in deals:
    if d.symbol=="XAUUSDm" and d.type in (0,1) and d.magic>=5000: byp[d.position_id].append(d)
broker=[]
for pid,ds in byp.items():
    i=[x for x in ds if x.entry==0]; o=[x for x in ds if x.entry==1]
    if i and o: broker.append(dict(t=i[0].time,dir='BUY' if i[0].type==0 else 'SELL',magic=i[0].magic,price=i[0].price,exit_t=o[-1].time,exit=o[-1].price,pnl=sum(x.profit+x.swap+x.commission for x in o)))
mt5.shutdown()
broker.sort(key=lambda x:x['t'])
bars=load_bars("XAUUSDm",timeframes=("M15","M5","M1","D1"))
cfg=EngineConfig(sizing_mode="fixed",fixed_lots=0.01,starting_balance=177.0)
res=BacktestEngine(bars=bars,cost=SCENARIOS["observed"],config=cfg).run([c() for c in PORTFOLIO_6_LEG],S,E)
magic={c().name:c().magic for c in PORTFOLIO_6_LEG}
eng=[dict(t=t.entry_time,dir='BUY' if t.is_buy else 'SELL',magic=magic[t.strategy],price=t.entry_price,exit=t.exit_price,pnl=t.net_pl,reason=t.exit_reason) for t in res.trades]
print(f"broker trades: {len(broker)} net ${sum(b['pnl'] for b in broker):.2f} | engine trades: {len(eng)} net ${sum(e['pnl'] for e in eng):.2f}")
used=set(); matched=[]
for b in broker:
    best=None
    for k,e in enumerate(eng):
        if k in used or e['dir']!=b['dir'] or e['magic']!=b['magic']: continue
        dtm=abs(e['t']-b['t'])
        if dtm<=300 and (best is None or dtm<best[0]): best=(dtm,k)
    if best: used.add(best[1]); matched.append((b,eng[best[1]],best[0]))
print("matched (same leg, direction, entry within 5 min):",len(matched),"of",len(broker),"broker and",len(eng),"engine")
import numpy as np
if matched:
    pe=np.array([m[1]['pnl'] for m in matched]); pb=np.array([m[0]['pnl'] for m in matched])
    print("matched P&L: broker $%.2f vs engine $%.2f; mean entry-price gap (broker-engine, long positive=worse) $%.2f; mean time gap %.0fs"%(pb.sum(),pe.sum(),np.mean([(m[0]['price']-m[1]['price'])*(1 if m[0]['dir']=='BUY' else -1) for m in matched]),np.mean([m[2] for m in matched])))
    print("same outcome sign:",sum(1 for m in matched if (m[0]['pnl']>0)==(m[1]['pnl']>0)),"of",len(matched))
print("\nbroker-only trades (engine did not take):")
for b in broker:
    if not any(b is m[0] for m in matched): print("  ",dt.datetime.fromtimestamp(b['t'],U).strftime('%m-%d %H:%M'),b['dir'],b['magic'],"pnl %.2f"%b['pnl'])
print("engine-only trades (broker did not take):",len(eng)-len(matched))
c=collections.Counter(e['magic'] for k,e in enumerate(eng) if k not in used); print("  by magic:",dict(c))
