# Pre-registration — three TradingView indicator strategies on XAUUSDm (trials #646-#654)

Frozen 2026-10-19 BEFORE any result was computed. Owner-requested ports of: (A) "20 EMA Daytrading" (Pine v1), (B) "UT Bot Alerts" (key 1, ATR 10, no Heikin Ashi), (C) "QQE signals" (RSI 14, smoothing 5, factor 4.238, threshold 10, unused). Closed after the first run; no parameter changes.
Prior: these are generic indicator systems of the kind already falsified (#640, EA31337 SuperTrend/MA/Pinbar). They are tested because the owner asked, with the SL/TP set fixed in advance so the exit cannot be tuned after the fact.

## Signals (ported literally; evaluated on CLOSED M15 bars; entry at the next bar open)
- **A (20 EMA):** e20 = EMA(close, 20). Pine v1 `crossover(close[1], e20)` is read literally: close[t-1] > e20[t] AND close[t-2] <= e20[t-1]; long additionally needs close[t] >= high[t-1]. Short is the mirror: close[t-1] < e20[t] AND close[t-2] >= e20[t-1] AND close[t] <= low[t-1].
- **B (UT Bot):** nLoss = 1 x ATR(10) (Wilder RMA). ATR trailing stop recursion exactly as the Pine source (src = close). buy = close > stop AND close crosses over stop (ema(src,1) = src); sell = mirror.
- **C (QQE):** RSI(14) Wilder; RsiMa = EMA(RSI, 5); AtrRsi = |RsiMa[1] - RsiMa|; dar = EMA(EMA(AtrRsi, 27), 27) x 4.238; bands and `trend` per the Pine source (`cross` = either direction); QQExlong/QQExshort counters; long signal on the first bar with FastAtrRsiTL < RsiMa, short on the first bar with FastAtrRsiTL > RsiMa.
Warm-up: signals ignored for the first 500 bars of each series.

## Exits (fixed set; one position at a time; opposite signals while in a trade are ignored)
Stop = k_sl x ATR14(M15) at the signal bar; target = k_tp x ATR14. Three fixed (k_sl, k_tp) pairs, nothing else tried: **P1 = (1.0, 1.5), P2 = (1.5, 3.0), P3 = (2.0, 2.0)**. Time exit at the close of the 48th M15 bar after entry. Stop-first when a bar touches both; checked from the entry bar; longs enter at ask (open + bar spread), shorts exit at ask.
Costs: bar spread; swap -0.5 price units per rollover night for longs; stress = spread x2 + $0.30 per fill. R = pnl / stop distance. No D1 gate, no session filter (kept simple on purpose).

## Splits (broker data, research/data/XAUUSDm_M15.npy) and decision rules
DEV 2022-08-01..2024-12-31 · VALIDATE 2025-01-01..2026-06-30 · HOLDOUT 2026-07-01..2026-10-13 (already read by earlier trials; can falsify, not prove).
- 9 trials (A/B/C x P1/P2/P3). All nine are reported on all periods (no hiding).
- Selection: for each strategy, the pair with the highest DEV expectancy (R) is carried to the pass/fail judgement; the other two are reported only. This is 3 selections, so DSR uses N = 645 + 9 = 654.
- **Pass (per strategy, carried pair):** DEV and VALIDATE each PF > 1.25 net of costs and expectancy > 0; >= 100 trades in DEV+VALIDATE; no quarter > 40% of net R; no trade > 15% of net R; max DD < 8% at 0.25% risk per trade (< 32 R); stress expectancy > 0; DSR >= 0.95; HOLDOUT PF > 1.0. Anything less: CLOSED. A pass only qualifies for a 90-day frozen forward test.
- Placebo: the carried pair is also compared with 2,000 random-entry runs (same number of entries per period, same exits and costs, entries at random bars, direction random); the real result must beat the 95th percentile of the placebo expectancy in DEV+VALIDATE.

## Robustness check (descriptive; not part of the pass rule)
The carried pair is re-run on the 22-year archive (research/data/kaggle_22yr/XAUUSDm_M15.npy, no spread data, so a flat $0.30 spread is assumed), reported by era (2004-2010, 2011-2018, 2019-2026-02), to show whether anything exists outside the 2022+ regime.
