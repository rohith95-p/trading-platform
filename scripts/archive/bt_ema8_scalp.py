"""
Backtest: TrendlineEMA8Scalp — "One repeatable entry every time"
Instagram strategy: Trendline retrace + candlestick signal + 8 EMA crossover.

Run:
    python -m scripts.bt_ema8_scalp

Results are printed to stdout and written to research/runs/.
"""

from __future__ import annotations
import json
import os
from dataclasses import asdict
from datetime import datetime, timezone

from src.backtesting.costs import SCENARIOS
from src.backtesting.data import load_bars
from src.backtesting.engine import BacktestEngine, EngineConfig
from src.backtesting.metrics import (
    bootstrap_expectancy,
    drop_best_worst,
    monte_carlo_paths,
    summarize,
)
from src.strategies.trendline_ema8_scalp import TrendlineEMA8Scalp

SYMBOL        = "XAUUSDm"
BALANCE       = 163.24          # current live balance
FIXED_LOTS    = 0.02            # matches the live bot
COST_SCENARIO = "realistic"

# ── Validation window (true M1 data) ──────────────────────────────────────
START = "2026-05-21"
END   = "2026-08-29"

# ── Engine config (mirrors the live bot) ──────────────────────────────────
def _ts(d: str) -> int:
    return int(datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def run() -> None:
    print("\n" + "=" * 72)
    print("  BACKTEST: Trendline + 8 EMA Scalp  (Instagram strategy)")
    print("=" * 72)

    bars = load_bars(SYMBOL)
    print(f"  data: M15={len(bars.m15)} D1={len(bars.d1) if bars.d1 is not None else '-'}")
    print(f"  window: {START} -> {END}  |  balance: ${BALANCE:.2f}  |  lots: {FIXED_LOTS}")

    # ── Run 1: default params from screenshot (SL=0.75×ATR, TP=2×ATR) ────
    configs = [
        {"sl": 0.75, "tp": 2.0,  "label": "SL=0.75×ATR  TP=2.0×ATR  (screenshot default)"},
        {"sl": 1.0,  "tp": 2.5,  "label": "SL=1.0×ATR   TP=2.5×ATR  (wider)"},
        {"sl": 0.5,  "tp": 1.5,  "label": "SL=0.5×ATR   TP=1.5×ATR  (tighter)"},
        {"sl": 0.75, "tp": 3.0,  "label": "SL=0.75×ATR  TP=3.0×ATR  (high R)"},
    ]

    results = []
    for cfg_params in configs:
        strat = TrendlineEMA8Scalp(
            sl_atr_mult=cfg_params["sl"],
            tp_atr_mult=cfg_params["tp"],
        )

        cfg = EngineConfig(
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
        )

        eng = BacktestEngine(bars=bars, cost=SCENARIOS[COST_SCENARIO], config=cfg)
        res = eng.run([strat], start_ts=_ts(START), end_ts=_ts(END))
        stats = summarize(res.trades, res.equity, BALANCE)

        bs = bootstrap_expectancy(res.trades)
        mc = monte_carlo_paths(res.trades, BALANCE)
        ood = drop_best_worst(res.trades)

        results.append({
            "label":  cfg_params["label"],
            "sl":     cfg_params["sl"],
            "tp":     cfg_params["tp"],
            "stats":  stats,
            "bs":     bs,
            "mc":     mc,
            "ood":    ood,
            "trades": res.trades,
        })

        _print_result(cfg_params["label"], stats, bs, mc, ood)

    # ── Comparison table ────────────────────────────────────────────────
    print("\n" + "─" * 72)
    print("  COMPARISON SUMMARY")
    print("─" * 72)
    print(f"  {'Config':<40} {'Trades':>6} {'WR%':>6} {'PF':>6} {'Net $':>9} {'MaxDD%':>7}")
    print("  " + "-" * 68)
    for r in results:
        s = r["stats"]
        print(
            f"  {r['label']:<40} "
            f"{s.trades:>6} "
            f"{s.win_rate:>6.1f} "
            f"{s.profit_factor:>6.3f} "
            f"${s.net_pl:>8,.2f} "
            f"{s.max_drawdown_pct:>6.1f}%"
        )

    # ── Save best run ────────────────────────────────────────────────────
    best = max(results, key=lambda r: r["stats"].profit_factor)
    out_dir = os.path.join("research", "runs",
                           f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}_ema8_scalp")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "best_manifest.json"), "w") as f:
        json.dump({
            "strategy": "TrendlineEMA8Scalp",
            "best_config": best["label"],
            "stats": best["stats"].to_dict(),
            "bootstrap": best["bs"],
            "monte_carlo": best["mc"],
            "outlier": best["ood"],
        }, f, indent=2, default=str)
    with open(os.path.join(out_dir, "best_trades.json"), "w") as f:
        json.dump([asdict(t) for t in best["trades"]], f, indent=1, default=str)

    print(f"\n  [BEST] {best['label']}")
    print(f"  Results written to {out_dir}")
    print()


def _print_result(label: str, s, bs, mc, ood) -> None:
    print(f"\n-- {label}")
    print(f"   trades {s.trades:<6} win rate {s.win_rate:>6.2f}%   PF {s.profit_factor:.3f}")
    print(f"   net ${s.net_pl:,.2f}   expectancy ${s.expectancy:.3f}/trade  ({s.expectancy_r:+.4f}R)")
    print(f"   avg win ${s.avg_win:,.2f}   avg loss ${s.avg_loss:,.2f}   payoff {s.payoff_ratio:.2f}x")
    print(f"   max DD ${s.max_drawdown:,.2f} ({s.max_drawdown_pct:.1f}%)   "
          f"balance ${s.start_balance:.2f} -> ${s.end_balance:.2f}  ({s.return_pct:+.1f}%)")
    print(f"   max consec losses {s.max_consec_losses}   "
          f"exits: {dict(sorted(s.exit_reasons.items(), key=lambda kv: -kv[1]))}")
    if bs:
        print(f"   bootstrap CI [{bs['p05']:+.3f}, {bs['p95']:+.3f}]  "
              f"P(edge<=0)={bs['prob_negative']:.1%}")
    if mc:
        print(f"   Monte Carlo p95 MaxDD=${mc['p95_max_dd']:,.2f}  "
              f"P(-50% acct)={mc['prob_50pct_drawdown']:.1%}")
    if ood:
        print(f"   Drop best 3: ${ood['drop_best_3']:,.2f}  "
              f"top-3 = {ood['top3_share_of_gross_profit']:.0f}% of gross profit")


if __name__ == "__main__":
    run()

