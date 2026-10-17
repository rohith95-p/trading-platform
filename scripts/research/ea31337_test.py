"""Run the three EA31337-inspired hypotheses solo through the corrected engine (gate ON, live window, 0.01 lot, $10k,
realistic_ecn) over 2022-08..2026-10 and dump [entry_time, exit_time, net_pl, risk]. Args: idx outdir"""
import sys, os, json, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT); os.chdir(ROOT)
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.strategies.ea31337_hypotheses import SuperTrendH, MABreakoutH, PinbarH
JOBS = [(SuperTrendH, 1.0, 2.0), (SuperTrendH, 2.0, 4.0), (MABreakoutH, 1.0, 2.0), (MABreakoutH, 2.0, 4.0), (PinbarH, 1.0, 1.5), (PinbarH, 2.0, 3.0)]
cls, sl, tp = JOBS[int(sys.argv[1])]; out = sys.argv[2]
bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1"))
ts = lambda d: int(d.replace(tzinfo=dt.timezone.utc).timestamp())
s = cls(sl, tp)
res = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=EngineConfig(sizing_mode="fixed", fixed_lots=0.01, starting_balance=10000.0)).run([s], ts(dt.datetime(2022, 8, 1)), ts(dt.datetime(2026, 10, 14)))
json.dump([[t.entry_time, t.exit_time, t.net_pl, abs(t.entry_price - t.initial_sl)] for t in res.trades], open(os.path.join(out, s.name + ".json"), "w"))
print("done", s.name, len(res.trades), flush=True)
