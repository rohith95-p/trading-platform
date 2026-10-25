# Pre-Registration: Momentum Portfolio Candidates
**Date:** 2026-10-25
**Author:** Ultra Core Research

## Hypotheses

### H1: D1 EMA 21/50 Crossover
**Claim:** The daily EMA 21/50 crossover strategy on XAUUSDm produces PF > 1.2
on out-of-sample data after realistic costs (spread + commission + swap).
**Source:** quant-signals.com backtest: PF 1.85, 38.1% win rate, 8,693 trades.
**Parameters:** EMA fast=21, slow=50. SL 2.0x ATR14, TP 4.0x ATR14.
**Edge trigger:** signal on cross only, not while the cross persists.

### H2: Donchian 20-Day Breakout
**Claim:** The 20-day Donchian channel breakout on XAUUSDm produces PF > 1.2
on out-of-sample data after realistic costs.
**Source:** Turtle Trading System 2 rules; practitioner data shows ~6% CAGR,
42% win rate, 2.6 risk/reward on gold (2000-2025).
**Parameters:** Channel=20 days. SL 2.0x ATR14, TP 6.0x ATR14.
**Edge trigger:** signal on new breakout only.

### H3: Time Series Momentum (TSMOM 63-day)
**Claim:** The 63-day lookback TSMOM strategy on XAUUSDm produces PF > 1.1
on out-of-sample data after realistic costs.
**Source:** Moskowitz, Ooi, Pedersen (2012), "Time Series Momentum", Journal
of Financial Economics. Sharpe 0.64-1.31 across 58 instruments including gold.
CBS thesis found 3-month lookback optimal for individual instruments.
**Parameters:** Lookback=63 trading days. SL 1.5x ATR14, TP 3.0x ATR14.
**Edge trigger:** signal on direction change only.

## Data Splits (4.2 years of M15 data: 2022-07 to 2026-10)
- **DEV (in-sample):** 2022-08-01 to 2024-02-01 (~18 months)
- **VALIDATE (first OOS):** 2024-02-01 to 2025-06-01 (~16 months)
- **HOLDOUT (final OOS):** 2025-06-01 to 2026-10-13 (~16 months)

## Engine Config
- `sizing_mode="fixed"`, `fixed_lots=0.01`
- `starting_balance=105.74` (current account)
- `history_bars=600` (enough for 55+ D1 bars from M15)
- `enable_d1_bias_gate=False` (these ARE the D1 strategies)
- `dedup_per_candle=True`
- `max_concurrent=2`, `max_same_direction=2`
- Cost: `realistic_ecn` (spread + commission + swap)

## Success Criteria
A strategy passes if:
1. PF > 1.2 on DEV (in-sample fit)
2. PF > 1.1 on VALIDATE (first OOS confirmation)
3. PF > 1.0 on HOLDOUT (final OOS -- must not lose money)
4. Max drawdown < 35% on all splits
5. Trade count > 20 per split (enough for statistical significance)

## Portfolio Construction
Strategies that pass all criteria enter the live portfolio alongside the
existing D1 EMA20 direction gate. They replace (not supplement) the four
losing V5 strategies. The Highlander rule applies: only the highest-conviction
daily signal fires per candle.
