# PREREG: strategy-specific stops and targets (2026-10-31)

**Question (owner):** stops and targets taken from each strategy's own logic (its range, its breakout candle, its
sweep wick), not generic swings or fixed ATR multiples. Does any of them beat the live ATR stops?

**Entries and exits:** the real live 4-leg entries (`research/results/audit_2026-10-30/trades_no_donchian.json`), exits
replayed on M1 bars with the engine's costs and Friday close (same exit model as `sltp_sweep.py`, which matched the
engine on 560/561 trades). Levels use only M15 bars closed before the entry. Stop buffer 0.1 ATR beyond the level.
Every stop distance is clamped to [0.5, 4.0] x ATR. A target that is already behind the entry falls back to the live
ATR target for that trade.

**Levels**
- Asian legs (Asian Range Filtered, Asian Breakout): Asian range AR = 00:00-06:00 UTC high/low, width W;
  breakout candle BC = the 07:00 UTC M15 bar.
  - Stops: `ar_far` other side of AR · `ar_mid` AR midpoint · `ar_in25` 25% of W back inside the broken edge · `bc` BC's opposite extreme.
  - Targets: `mm1` / `mm1.5` / `mm2` = broken edge + 1 / 1.5 / 2 x W (measured move) · `r2` = 2 x stop distance · `atr` = live ATR target.
- London Momentum Tight: London range LR = 07:00-11:45 UTC bars; EMA21 of London closes.
  - Stops: `lr_far` other side of LR · `lr_mid` LR midpoint · `imp4` extreme of the last 4 London bars · `ema21` beyond EMA21.
  - Targets: `lrx0.5` / `lrx1` = entry + 0.5 / 1 x LR width · `pd` previous UTC day's high (buy) / low (sell) · `r2` · `atr`.
- NY Session Reversal: sweep candle SC = the closed M15 bar that triggered the entry; London range as in the strategy.
  - Stops: `wick` beyond SC's swept extreme · `wick_wide` 0.5 ATR beyond it.
  - Targets: `lr_mid` London midpoint · `lr_far` the opposite London extreme · `r2` · `atr`.

**Sizing modes:** `fixed` 0.02 lots; `eqrisk` lots = 0.02 x live stop distance / variant stop distance, rounded to
0.01, between 0.01 and 0.04 (each trade risks about what the live stop risks).

**Pass bar, per strategy and sizing mode (all four required):**
1. Walk-forward A: the variant with the best DEV net beats live on TEST.
2. Walk-forward B: the variant with the best DEV+TEST net (the candidate) beats or equals live on RECENT.
3. The candidate's worst drawdown (DEV, TEST) <= 1.2 x live.
4. Monte Carlo: bootstrapping the per-trade P&L difference (candidate - live) over all M1 trades, 20,000 resamples,
   P(candidate better) >= 0.90.

A pass is then confirmed with the full engine (trade limits, Atlas guard). No live change during the freeze week.
Variants are fixed above; none may be added after the run starts.
