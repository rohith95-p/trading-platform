"""Run every strategy class (live, retired, archived, research suites) solo through the
corrected engine on a window (default 2026-01-01 -> data end), 0.01 lot, $10k start
(so ruin cannot truncate the sample), realistic_ecn costs, live trading window + D1 gate.
Usage: python all_strategies_2026.py <worker_idx> <n_workers> <out.jsonl>"""
import sys, os, json, importlib, dataclasses, datetime as dt, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); os.chdir(ROOT)
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.data import load_bars
from src.backtesting.costs import SCENARIOS
from src.backtesting.metrics import summarize

S = "src.strategies."
SPECS = [  # (label, module, class, kwargs)
 ("TREND_PULLBACK_V5", S+"portfolio_v5_core", "TrendPullbackV5", {}),
 ("BB_MEAN_REVERSION_V5", S+"portfolio_v5_core", "BBMeanReversionV5", {}),
 ("NVMR_V5", S+"portfolio_v5_core", "NVMRPortfolioV5", {}),
 ("FVG_NY_TIGHT_V5", S+"portfolio_v5_core", "FVGNYTightV5", {}),
 ("PDHLR_V5(retired)", S+"archive.retired_v5_legs", "PDHLRStrategyV5", {}),
 ("NY_LIQ_EXPANSION(retired)", S+"archive.retired_v5_legs", "NYLiquidityExpansionV5", {}),
 ("LARS_LONDON", S+"bible_strategies", "LARSStrategy", {}),
 ("LKOCS_LONDON", S+"bible_strategies", "LKOCSStrategy", {}),
 ("PDHLR", S+"bible_strategies", "PDHLRStrategy", {}),
 ("NVMR_raw", S+"bible_strategies", "NVMRStrategy", {}),
 ("SESSION_BREAKOUT", S+"grid_strategies", "SessionBreakoutStrat", {}),
 ("LIQ_SWEEP_REVERSAL", S+"liquidity_sweep_reversal", "LiquiditySweepReversal", {}),
 ("NY_LIQ_EXPANSION", S+"ny_liquidity_expansion", "NYLiquidityExpansion", {}),
 ("NY_LONDON_SWEEP_REV", S+"ny_session_suite", "NYLondonSweepReversal", {}),
 ("NY_CONT_BREAKOUT", S+"ny_session_suite", "NYContinuationBreakout", {}),
 ("NY_PM_REVERSAL", S+"ny_session_suite", "NYPMReversal", {}),
 ("TRENDLINE_EMA8_SCALP", S+"trendline_ema8_scalp", "TrendlineEMA8Scalp", {}),
 ("FVG_NY_TIGHT(v4)", S+"portfolio_v4", "FVGNYTight", {}),
 ("FVG_NY_SWEEP", S+"portfolio_v4", "FVGNYSweep", {}),
 ("FVG_NY_VOID", S+"portfolio_v4", "FVGNYVoid", {}),
 ("FVG_NY_SWEEP_OR_VOID", S+"portfolio_v4", "FVGNYSweepOrVoid", {}),
 ("FVG_ASIA_SWEEP", S+"portfolio_v4", "FVGAsiaSweep", {}),
 ("SQUEEZE_ASIA", S+"portfolio_v4", "SqueezeBreakAsia", {}),
 ("EMASTACK_LONDON_TIGHT", S+"portfolio_v4", "EMAStackLondonTight", {}),
 ("RANGEREJECTION_NY_TIGHT", S+"portfolio_v4", "RangeRejectionNYTight", {}),
 ("ASIAN_BREAKOUT(arch)", S+"archive.asian_breakout", "AsianBreakout", {}),
 ("ASIAN_SWEEP(arch)", S+"archive.asian_sweep", "AsianSweep", {}),
 ("EMA_PULLBACK(arch)", S+"archive.ema_pullback", "EMAPullback", {}),
 ("EMA_STACK(arch)", S+"archive.ema_stack", "EMAStack", {}),
 ("KELTNER_BREAKOUT(arch)", S+"archive.keltner_breakout", "KeltnerBreakout", {}),
 ("LONDON_JUDAS(arch)", S+"archive.london_judas_swing", "LondonJudasSwing", {}),
 ("LONDON_OTE_REENTRY(arch)", S+"archive.london_judas_swing", "LondonOTEReentry", {}),
 ("LUXALGO_FVG(arch)", S+"archive.luxalgo_fvg", "LuxAlgoFVG", {}),
 ("MACD_CROSS(arch)", S+"archive.macd_cross", "MACDCross", {}),
 ("MORNING_MOMENTUM(arch)", S+"archive.morning_momentum", "MorningMomentum", {}),
 ("PDHL_BREAKOUT(arch)", S+"archive.pdhl_breakout", "PDHLBreakout", {}),
 ("QQE(arch)", S+"archive.qqe_strategy", "QQEStrategy", {}),
 ("SUPERTREND_EMA(arch)", S+"archive.supertrend_ema", "SupertrendEMA", {}),
 ("TREND_SNIPER_SAR(arch)", S+"archive.trend_sniper_sar", "TrendSniperSAR", {}),
 ("H1_DONCHIAN_100 sl3/tp9", S+"h1_donchian", "H1Donchian", {"channel": 100, "sl_atr_mult": 3.0, "tp_atr_mult": 9.0}),
 ("H1_DONCHIAN_100 sl4/tp12", S+"h1_donchian", "H1Donchian", {"channel": 100, "sl_atr_mult": 4.0, "tp_atr_mult": 12.0}),
]

if __name__ == "__main__":
    wi, nw, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    start = int(dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    end = int(dt.datetime(2026, 10, 14, tzinfo=dt.timezone.utc).timestamp())
    bars = load_bars("XAUUSDm", timeframes=("M15", "M5", "M1", "D1"))
    for k, (label, mod, cls, kw) in enumerate(SPECS):
        if k % nw != wi: continue
        rec = {"label": label}
        try:
            strat = getattr(importlib.import_module(mod), cls)(**kw)
            hist = 600 if "DONCHIAN" in label else 250
            cfg = EngineConfig(sizing_mode="fixed", fixed_lots=0.01, starting_balance=10000.0, history_bars=hist)
            res = BacktestEngine(bars=bars, cost=SCENARIOS["realistic_ecn"], config=cfg).run([strat], start, end)
            d = summarize(res.trades, res.equity, 10000.0).to_dict()
            monthly = {}
            for t in res.trades:
                m = dt.datetime.fromtimestamp(t.exit_time, dt.timezone.utc).strftime("%m")
                monthly[m] = round(monthly.get(m, 0) + t.net_pl, 2)
            rec.update(n=d["trades"], win=d["win_rate"], pf=d["profit_factor"], net=d["net_pl"],
                       maxdd=d["max_drawdown"], avg_win_r=d.get("avg_win_r"), avg_loss_r=d.get("avg_loss_r"),
                       exp_r=d.get("expectancy_r"), monthly=monthly)
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:200]
        open(out, "a").write(json.dumps(rec) + "\n")
        print(rec["label"], rec.get("n"), rec.get("pf"), rec.get("error", ""), flush=True)
