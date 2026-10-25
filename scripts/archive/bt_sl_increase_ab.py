"""
A/B Backtest: SL Increase + PDHLR Regime Filter
=================================================
Control:   Portfolio V5 with original 0.1x ATR SL, no regime filter
Treatment: Portfolio V5 with 0.5x ATR SL + PDHLR strong-trend regime filter

Run:
    python -m scripts.bt_sl_increase_ab
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone

from src.backtesting.costs import SCENARIOS
from src.backtesting.data import load_bars
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.metrics import bootstrap_expectancy, drop_best_worst, monte_carlo_paths, summarize

SYMBOL     = "XAUUSDm"
BALANCE    = 163.24
FIXED_LOTS = 0.01
START      = "2026-05-21"
END        = "2026-08-29"


def _ts(d: str) -> int:
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def _base_cfg() -> EngineConfig:
    return EngineConfig(
        symbol=SYMBOL,
        starting_balance=BALANCE,
        sizing_mode="fixed",
        fixed_lots=FIXED_LOTS,
        max_concurrent=1,
        max_same_direction=1,
        enable_trailing=False,
        enable_pyramiding=False,
        daily_loss_limit_mode="balance_pct",
        daily_loss_limit_pct=0.03,
        enable_d1_bias_gate=True,
        dedup_per_candle=True,
        direction_gate="d1_ema20",
    )


def _make_control():
    """Original V5 portfolio: sl=0.1, no regime filter."""
    from src.strategies.grid_strategies import TrendPullbackStrat, BBMeanReversionStrat
    from src.strategies.bible_strategies import NVMRStrategy, PDHLRStrategy
    from src.strategies.ny_liquidity_expansion import NYLiquidityExpansion
    from src.strategies.portfolio_v4 import _LiquidityFilteredFVG

    strats = []

    tp = TrendPullbackStrat(); tp.name = 'TREND_PULLBACK_V5'; tp.magic = 5001
    tp.sl_atr_mult = 0.1; tp.tp_atr_mult = 2.0; strats.append(tp)

    bb = BBMeanReversionStrat(); bb.name = 'BB_MEAN_REVERSION_V5'; bb.magic = 5002
    bb.sl_atr_mult = 0.1; bb.tp_atr_mult = 2.0; strats.append(bb)

    nv = NVMRStrategy(); nv.name = 'NVMR_TARGET_10_V5'; nv.magic = 5003
    nv.sl_atr_mult = 0.1; nv.tp_atr_mult = 2.0; strats.append(nv)

    fvg = _LiquidityFilteredFVG(); fvg.name = 'FVG_NY_TIGHT_V5'; fvg.magic = 5005
    fvg.session = (17.5, 21.5); fvg.sl_atr_mult = 0.1; fvg.tp_atr_mult = 2.0; strats.append(fvg)

    pd_ = PDHLRStrategy(); pd_.name = 'PDHLR_STRATEGY_V5'; pd_.magic = 5008
    pd_.sl_atr_mult = 0.1; pd_.tp_atr_mult = 2.0; pd_.strong_trend_atr_mult = 0.0; strats.append(pd_)

    ny = NYLiquidityExpansion(); ny.name = 'NY_LIQUIDITY_EXPANSION_V5'; ny.magic = 5009
    ny.sl_atr_mult = 0.1; ny.tp_atr_mult = 2.0; strats.append(ny)
    return strats


def _make_treatment():
    """New V5 portfolio: sl=0.5, PDHLR regime filter active."""
    from src.strategies.portfolio_v5_6_leg import (
        TrendPullbackV5, BBMeanReversionV5, NVMRPortfolioV5,
        FVGNYTightV5, PDHLRStrategyV5, NYLiquidityExpansionV5,
    )
    return [
        TrendPullbackV5(), BBMeanReversionV5(), NVMRPortfolioV5(),
        FVGNYTightV5(), PDHLRStrategyV5(), NYLiquidityExpansionV5(),
    ]


def _run(bars, strats, label):
    cfg = _base_cfg()
    eng = BacktestEngine(bars=bars, cost=SCENARIOS["realistic"], config=cfg)
    res = eng.run(strats, start_ts=_ts(START), end_ts=_ts(END))
    stats = summarize(res.trades, res.equity, BALANCE)
    bs = bootstrap_expectancy(res.trades)
    mc = monte_carlo_paths(res.trades, BALANCE)
    ood = drop_best_worst(res.trades)
    return stats, bs, mc, ood, res.trades, res.diagnostics


def _fmt(label, stats, bs, mc, ood, diag):
    print(f"\n{'='*68}")
    print(f"  {label}")
    print(f"{'='*68}")
    print(f"  trades {stats.trades:<6} win rate {stats.win_rate:>6.2f}%   PF {stats.profit_factor:.4f}")
    print(f"  net ${stats.net_pl:,.2f}   expectancy ${stats.expectancy:.3f}/trade  ({stats.expectancy_r:+.4f}R)")
    print(f"  avg win ${stats.avg_win:,.2f}   avg loss ${stats.avg_loss:,.2f}   payoff {stats.payoff_ratio:.2f}x")
    print(f"  max DD ${stats.max_drawdown:,.2f} ({stats.max_drawdown_pct:.1f}%)  "
          f"balance ${stats.start_balance:.2f} -> ${stats.end_balance:.2f}  ({stats.return_pct:+.1f}%)")
    print(f"  max consec losses {stats.max_consec_losses}   "
          f"exits: {dict(sorted(stats.exit_reasons.items(), key=lambda kv: -kv[1]))}")
    d1_blocked = diag.get("entries_blocked_d1_bias", 0)
    print(f"  D1 bias gate blocked: {d1_blocked} signals")
    if bs:
        print(f"  bootstrap CI [{bs['p05']:+.3f}, {bs['p95']:+.3f}]  "
              f"P(edge<=0)={bs['prob_negative']:.1%}")
    if mc:
        print(f"  Monte Carlo p95 MaxDD=${mc['p95_max_dd']:,.2f}  "
              f"P(-50% acct)={mc['prob_50pct_drawdown']:.1%}")
    if ood:
        print(f"  Drop best 3: ${ood['drop_best_3']:,.2f}  "
              f"top-3 = {ood['top3_share_of_gross_profit']:.0f}% of gross profit")


def run():
    print(f"\n{'='*68}")
    print(f"  A/B: SL Increase (0.1->0.5 ATR) + PDHLR Regime Filter")
    print(f"  Window: {START} -> {END} | Balance: ${BALANCE} | Lots: {FIXED_LOTS}")
    print(f"  Cost: realistic (bar-spread + 20pt slippage + swap)")
    print(f"{'='*68}")

    bars = load_bars(SYMBOL)
    print(f"  data: M15={len(bars.m15)}  D1={len(bars.d1) if bars.d1 is not None else '-'}")

    print("\nRunning CONTROL (sl=0.1, no regime filter)...")
    ctrl_stats, ctrl_bs, ctrl_mc, ctrl_ood, ctrl_trades, ctrl_diag = _run(
        bars, _make_control(), "CONTROL"
    )

    print("Running TREATMENT (sl=0.5, PDHLR regime filter)...")
    trt_stats, trt_bs, trt_mc, trt_ood, trt_trades, trt_diag = _run(
        bars, _make_treatment(), "TREATMENT"
    )

    _fmt("CONTROL  -- sl=0.1 ATR, no regime filter (original)",
         ctrl_stats, ctrl_bs, ctrl_mc, ctrl_ood, ctrl_diag)
    _fmt("TREATMENT -- sl=0.5 ATR + PDHLR regime filter (new)",
         trt_stats, trt_bs, trt_mc, trt_ood, trt_diag)

    pf_delta    = trt_stats.profit_factor - ctrl_stats.profit_factor
    dd_delta    = trt_stats.max_drawdown_pct - ctrl_stats.max_drawdown_pct
    trade_delta = trt_stats.trades - ctrl_stats.trades
    net_delta   = trt_stats.net_pl - ctrl_stats.net_pl

    print(f"\n{'='*68}")
    print(f"  DELTA (Treatment - Control)")
    print(f"{'='*68}")
    print(f"  PF:      {ctrl_stats.profit_factor:.4f} -> {trt_stats.profit_factor:.4f}   ({pf_delta:+.4f})")
    print(f"  Net $:   ${ctrl_stats.net_pl:,.2f} -> ${trt_stats.net_pl:,.2f}   ({net_delta:+,.2f})")
    print(f"  Max DD%: {ctrl_stats.max_drawdown_pct:.1f}% -> {trt_stats.max_drawdown_pct:.1f}%   ({dd_delta:+.1f}pp)")
    print(f"  Trades:  {ctrl_stats.trades} -> {trt_stats.trades}   ({trade_delta:+d})")

    if pf_delta > 0.05 and dd_delta <= 0:
        verdict = "APPROVE -- PF improved and DD not worse. Safe to re-deploy."
    elif pf_delta > 0.05:
        verdict = "TENTATIVE APPROVE -- PF improved but DD increased. Review carefully."
    elif pf_delta > 0.0:
        verdict = "MARGINAL -- Small PF gain. Check per-strategy breakdown."
    elif pf_delta < -0.05:
        verdict = "REJECT -- New config hurts PF."
    else:
        verdict = "NEUTRAL -- No meaningful change."

    print(f"\n  VERDICT: {verdict}")

    out_dir = os.path.join("research", "runs",
                           f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}_sl_increase_ab")
    os.makedirs(out_dir, exist_ok=True)
    manifest = {
        "experiment": "sl_increase_pdhlr_regime_filter_ab",
        "window": {"start": START, "end": END},
        "balance": BALANCE, "lots": FIXED_LOTS,
        "changes": ["sl_atr_mult: 0.1 -> 0.5", "PDHLR: strong_trend_atr_mult=3.0 regime filter"],
        "control":   {"stats": ctrl_stats.to_dict(), "bootstrap": ctrl_bs,
                       "monte_carlo": ctrl_mc, "outlier": ctrl_ood},
        "treatment": {"stats": trt_stats.to_dict(), "bootstrap": trt_bs,
                       "monte_carlo": trt_mc, "outlier": trt_ood},
        "delta": {"pf": round(pf_delta, 4), "net_pl": round(net_delta, 2),
                  "max_dd_pct": round(dd_delta, 2), "trade_count": trade_delta},
        "verdict": verdict,
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    with open(os.path.join(out_dir, "control_trades.json"), "w") as f:
        json.dump([asdict(t) for t in ctrl_trades], f, indent=1, default=str)
    with open(os.path.join(out_dir, "treatment_trades.json"), "w") as f:
        json.dump([asdict(t) for t in trt_trades], f, indent=1, default=str)
    print(f"\n  Results -> {out_dir}\n")


if __name__ == "__main__":
    run()
