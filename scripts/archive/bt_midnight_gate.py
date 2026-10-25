"""
A/B Backtest: NY Midnight Open Gate (ICT Day Gate)
====================================================

Hypothesis: Filtering entries so that in BEARISH bias we only short when
price is ABOVE the NY Midnight Open (premium), and in BULLISH bias we only
long when price is BELOW it (discount), improves PF and reduces bad entries.

Gate rule (per ICT Smart Money):
  - BEARISH + price > midnight_open  -> shorts ALLOWED  (premium = good sell zone)
  - BEARISH + price < midnight_open  -> shorts BLOCKED   (already at discount)
  - BULLISH + price < midnight_open  -> longs ALLOWED   (discount = good buy zone)
  - BULLISH + price > midnight_open  -> longs BLOCKED    (already at premium)

NY Midnight = 00:00 EST = 05:00 UTC (winter/EST) = 04:00 UTC (summer/EDT)
Validation window is May-Aug 2026 (EDT/summer) -> midnight = 04:00 UTC = 09:30 IST

Run:
    python -m scripts.bt_midnight_gate
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np

from src.backtesting.costs import SCENARIOS
from src.backtesting.data import load_bars
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.metrics import bootstrap_expectancy, drop_best_worst, monte_carlo_paths, summarize
from src.strategies.portfolio_v5_6_leg import (
    TrendPullbackV5, BBMeanReversionV5, NVMRPortfolioV5,
    FVGNYTightV5, PDHLRStrategyV5, NYLiquidityExpansionV5,
)

SYMBOL      = "XAUUSDm"
BALANCE     = 163.24
FIXED_LOTS  = 0.02
START       = "2026-05-21"
END         = "2026-08-29"

IST = timezone(timedelta(hours=5, minutes=30))
EST = timezone(timedelta(hours=-5))   # standard (winter)
EDT = timezone(timedelta(hours=-4))   # daylight (summer) -- validation window


def _ts(d: str) -> int:
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def _midnight_open_price(m15_view: np.ndarray) -> Optional[float]:
    """
    Find the close price of the M15 bar whose open falls at / just after
    00:00 EST (04:00 UTC in EDT / summer) for the current day.

    The bar timestamped at 04:00 UTC is the first bar of the NYC algorithmic
    day. We use [-2] (last closed bar) timestamp to identify today, then walk
    backward through m15_view to find the 04:00 UTC bar for that IST calendar day.
    """
    if m15_view is None or len(m15_view) < 2:
        return None

    # Current day in IST (from the last closed bar [-2])
    bar_ts  = int(m15_view[-2]["time"])
    bar_ist = datetime.fromtimestamp(bar_ts, tz=timezone.utc).astimezone(IST)
    today_ist = bar_ist.date()

    # Target UTC timestamp: 04:00 UTC on the current IST calendar day
    # (this is 00:00 EDT and 09:30 IST)
    target_dt_utc = datetime(
        today_ist.year, today_ist.month, today_ist.day,
        4, 0, 0, tzinfo=timezone.utc
    )
    target_ts = int(target_dt_utc.timestamp())

    # Walk backward from [-2] to find the bar closest to target_ts
    times = m15_view["time"].astype(np.int64)
    # Find the last bar whose time <= target_ts
    idx = int(np.searchsorted(times, target_ts, side="right")) - 1
    if idx < 0:
        return None

    return float(m15_view[idx]["close"])


class MidnightGateStrategy:
    """
    Wrapper that adds the NY Midnight Open premium/discount filter on top of
    any BaseStrategy. Transparent to the engine — same evaluate() interface.
    """

    def __init__(self, inner):
        self._inner = inner
        self.name          = inner.name
        self.magic         = inner.magic
        self.sl_atr_mult   = getattr(inner, "sl_atr_mult", None)
        self.tp_atr_mult   = getattr(inner, "tp_atr_mult", None)
        self.execute_immediately = getattr(inner, "execute_immediately", True)
        self.edge_trigger  = getattr(inner, "edge_trigger", False)
        self._blocked_count = 0

    def evaluate(self, m15_rates, m5_rates=None):
        sig = self._inner.evaluate(m15_rates, m5_rates)
        if sig is None:
            return None

        midnight_price = _midnight_open_price(m15_rates)
        if midnight_price is None:
            return sig  # no data -> don't block

        current_close = float(m15_rates[-2]["close"])

        # The gate only makes sense when we also know the D1 bias.
        # Since the engine computes D1 bias separately and applies it AFTER
        # evaluate(), we use a proxy: M15 EMA20 trend direction as the
        # intraday regime indicator (conservative: slower to flip than D1 EMA20).
        closes = m15_rates["close"].astype(float)
        if len(closes) < 22:
            return sig

        # Simple EMA20 on M15 as bias proxy (same math as main_loop._calc_ema)
        mult = 2.0 / 21.0
        ema = closes[0]
        for c in closes[1:]:
            ema = c * mult + ema * (1 - mult)
        m15_ema20 = ema

        intraday_bias = "BULLISH" if closes[-2] > m15_ema20 else "BEARISH"

        # Apply the midnight gate
        if intraday_bias == "BEARISH":
            # Only short when price is ABOVE midnight open (premium zone)
            if sig.is_buy:
                return sig   # D1 gate will block longs anyway; let it handle
            if current_close < midnight_price:
                # Price already below midnight open on a bearish day = discount
                # Shorting here means chasing into oversold territory
                self._blocked_count += 1
                return None

        elif intraday_bias == "BULLISH":
            # Only long when price is BELOW midnight open (discount zone)
            if not sig.is_buy:
                return sig   # D1 gate will handle counter-trend shorts
            if current_close > midnight_price:
                # Price already above midnight open on a bullish day = premium
                # Buying here means chasing into overbought territory
                self._blocked_count += 1
                return None

        return sig

    def check_pending_confirmation(self, m15_rates):
        return getattr(self._inner, "check_pending_confirmation", lambda x: None)(m15_rates)

    def set_pending(self, signal, candle_time):
        fn = getattr(self._inner, "set_pending", None)
        if fn:
            fn(signal, candle_time)


def _make_strategies(wrap: bool):
    raw = [
        TrendPullbackV5(), BBMeanReversionV5(), NVMRPortfolioV5(),
        FVGNYTightV5(), PDHLRStrategyV5(), NYLiquidityExpansionV5(),
    ]
    if wrap:
        return [MidnightGateStrategy(s) for s in raw]
    return raw


def _base_cfg():
    return EngineConfig(
        symbol=SYMBOL,
        starting_balance=BALANCE,
        sizing_mode="fixed",
        fixed_lots=FIXED_LOTS,
        max_concurrent=2,
        max_same_direction=2,
        enable_trailing=False,
        enable_pyramiding=False,
        daily_loss_limit_mode="balance_pct",
        daily_loss_limit_pct=0.06,
        enable_d1_bias_gate=True,
        dedup_per_candle=True,
        direction_gate="d1_ema20",
    )


def _run_one(bars, label, wrap):
    strats = _make_strategies(wrap)
    cfg    = _base_cfg()
    eng    = BacktestEngine(bars=bars, cost=SCENARIOS["realistic"], config=cfg)
    res    = eng.run(strats, start_ts=_ts(START), end_ts=_ts(END))
    stats  = summarize(res.trades, res.equity, BALANCE)
    bs     = bootstrap_expectancy(res.trades)
    mc     = monte_carlo_paths(res.trades, BALANCE)
    ood    = drop_best_worst(res.trades)
    blocked = sum(getattr(s, "_blocked_count", 0) for s in strats) if wrap else 0
    return stats, bs, mc, ood, blocked, res.trades, res.diagnostics


def _fmt(label, stats, bs, mc, ood, blocked, diag):
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
    if blocked:
        print(f"  midnight gate blocked: {blocked} signals")
    d1_blocked = diag.get("entries_blocked_d1_bias", 0)
    print(f"  D1 bias gate blocked: {d1_blocked} signals total")
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
    print(f"  A/B BACKTEST: NY Midnight Open (ICT Day Gate) on PORTFOLIO_V5")
    print(f"  Window: {START} -> {END} | Balance: ${BALANCE} | Lots: {FIXED_LOTS}")
    print(f"{'='*68}")

    bars = load_bars(SYMBOL)
    print(f"  data: M15={len(bars.m15)}  D1={len(bars.d1) if bars.d1 is not None else '-'}")

    # --- Control: PORTFOLIO_V5 with D1 gate only (current live config) ---
    print("\nRunning CONTROL (D1 gate only)...")
    ctrl_stats, ctrl_bs, ctrl_mc, ctrl_ood, _, ctrl_trades, ctrl_diag = _run_one(
        bars, "CONTROL", wrap=False
    )

    # --- Treatment: + Midnight open gate ---
    print("Running TREATMENT (D1 gate + Midnight open gate)...")
    trt_stats, trt_bs, trt_mc, trt_ood, trt_blocked, trt_trades, trt_diag = _run_one(
        bars, "TREATMENT", wrap=True
    )

    _fmt("CONTROL  -- D1 EMA20 gate only (current live config)",
         ctrl_stats, ctrl_bs, ctrl_mc, ctrl_ood, 0, ctrl_diag)
    _fmt("TREATMENT -- D1 EMA20 gate + NY Midnight Open gate",
         trt_stats, trt_bs, trt_mc, trt_ood, trt_blocked, trt_diag)

    # --- Delta summary ---
    pf_delta    = trt_stats.profit_factor - ctrl_stats.profit_factor
    dd_delta    = trt_stats.max_drawdown_pct - ctrl_stats.max_drawdown_pct
    trade_delta = trt_stats.trades - ctrl_stats.trades
    net_delta   = trt_stats.net_pl - ctrl_stats.net_pl

    print(f"\n{'='*68}")
    print(f"  DELTA (Treatment - Control)")
    print(f"{'='*68}")
    print(f"  PF:      {ctrl_stats.profit_factor:.4f} -> {trt_stats.profit_factor:.4f}   "
          f"({pf_delta:+.4f})")
    print(f"  Net $:   ${ctrl_stats.net_pl:,.2f} -> ${trt_stats.net_pl:,.2f}   "
          f"({net_delta:+,.2f})")
    print(f"  Max DD%: {ctrl_stats.max_drawdown_pct:.1f}% -> {trt_stats.max_drawdown_pct:.1f}%   "
          f"({dd_delta:+.1f}pp)")
    print(f"  Trades:  {ctrl_stats.trades} -> {trt_stats.trades}   ({trade_delta:+d})")
    print(f"  Signals blocked by midnight gate: {trt_blocked}")

    # --- Verdict ---
    print(f"\n  VERDICT:")
    if pf_delta > 0.05 and dd_delta < 0:
        verdict = "APPROVE -- PF improved and DD reduced. Register and add to live."
    elif pf_delta > 0.05:
        verdict = "TENTATIVE APPROVE -- PF improved. Review DD carefully before adding live."
    elif pf_delta > 0.0 and abs(trade_delta) > 50:
        verdict = "MARGINAL -- Small PF gain but significant trade reduction. Borderline."
    elif pf_delta < -0.02:
        verdict = "REJECT -- Gate hurts PF. Do not add to live."
    else:
        verdict = "NEUTRAL -- No meaningful improvement. Gate adds no edge."
    print(f"  {verdict}")

    # --- Save results ---
    out_dir = os.path.join("research", "runs",
                           f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}_midnight_gate_ab")
    os.makedirs(out_dir, exist_ok=True)

    manifest = {
        "experiment": "midnight_open_gate_ab",
        "window": {"start": START, "end": END},
        "balance": BALANCE,
        "lots": FIXED_LOTS,
        "control": {
            "stats": ctrl_stats.to_dict(),
            "bootstrap": ctrl_bs,
            "monte_carlo": ctrl_mc,
            "outlier": ctrl_ood,
        },
        "treatment": {
            "midnight_gate_blocked": trt_blocked,
            "stats": trt_stats.to_dict(),
            "bootstrap": trt_bs,
            "monte_carlo": trt_mc,
            "outlier": trt_ood,
        },
        "delta": {
            "pf": round(pf_delta, 4),
            "net_pl": round(net_delta, 2),
            "max_dd_pct": round(dd_delta, 2),
            "trade_count": trade_delta,
        },
        "verdict": verdict,
    }

    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    with open(os.path.join(out_dir, "control_trades.json"), "w") as f:
        json.dump([asdict(t) for t in ctrl_trades], f, indent=1, default=str)
    with open(os.path.join(out_dir, "treatment_trades.json"), "w") as f:
        json.dump([asdict(t) for t in trt_trades], f, indent=1, default=str)

    print(f"\n  Results -> {out_dir}")
    print()


if __name__ == "__main__":
    run()
