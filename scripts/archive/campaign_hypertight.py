import sys
import importlib
import pkgutil
from pathlib import Path
import multiprocessing

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import summarize
import src.strategies as strategies_pkg

import inspect
from src.strategies.base_strategy import BaseStrategy

def evaluate_strategy(strat_class):
    try:
        # Each worker loads data into its own process memory
        bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1"))
        
        cfg = EngineConfig(
            symbol="XAUUSDm", starting_balance=100.0,
            sizing_mode="fixed", fixed_lots=0.01,
            max_concurrent=2, max_same_direction=2,
            enable_trailing=False, enable_pyramiding=False,
            daily_loss_limit_mode="balance_pct", daily_loss_limit_pct=0.06,
            enable_d1_bias_gate=True,
        )
        
        strat = strat_class()
        
        # FORCE hyper-tight risk settings
        strat.sl_atr_mult = 0.1
        strat.tp_atr_mult = 1.0
        
        eng = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg)
        res = eng.run([strat])
        stats = summarize(res.trades, res.equity, cfg.starting_balance)
        metrics = stats.to_dict()
        
        result_str = f"{strat_class.__name__:<25} | Trades: {metrics.get('trades', 0):<4} | PF: {metrics.get('profit_factor', 0.0):>4.2f} | Net: ${metrics.get('net_pl', 0.0):>6.2f} | DD: {metrics.get('max_drawdown_pct', 0.0):>5.2f}% | WR: {metrics.get('win_rate', 0.0):>5.2f}%"
        print(f"[COMPLETE] {result_str}", flush=True)
        
        return {
            "Strategy": strat_class.__name__,
            "Trades": metrics.get("trades", 0),
            "PF": metrics.get("profit_factor", 0.0),
            "Net": metrics.get("net_pl", 0.0),
            "MaxDD%": metrics.get("max_drawdown_pct", 0.0),
            "WinRate": metrics.get("win_rate", 0.0),
            "ResultStr": result_str
        }
    except Exception as e:
        print(f"[ERROR] {strat_class.__name__}: {e}", flush=True)
        return None

def run_hypertight_campaign_parallel():
    strategies_to_test = []
    
    for _, module_name, _ in pkgutil.iter_modules(strategies_pkg.__path__):
        if module_name in ["archive", "base_strategy"]:
            continue
        try:
            mod = importlib.import_module(f"src.strategies.{module_name}")
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if inspect.isclass(attr) and issubclass(attr, BaseStrategy) and attr is not BaseStrategy:
                    strategies_to_test.append(attr)
        except Exception as e:
            pass

    print(f"Found {len(strategies_to_test)} strategies to test on Hyper-Tight baseline.")
    print("Using 28 cores. Results will stream as they finish...\n", flush=True)
    
    results = []
    with multiprocessing.Pool(28) as pool:
        for res in pool.imap_unordered(evaluate_strategy, strategies_to_test):
            if res is not None:
                results.append(res)

    print("\n\n--- HYPER-TIGHT (0.1 SL / 1.0 TP) FINAL LEADERBOARD ---")
    results.sort(key=lambda x: x["Net"], reverse=True)
    for r in results:
        print(r["ResultStr"])

if __name__ == "__main__":
    run_hypertight_campaign_parallel()
