# Pre-registration — DXY / yield confirmation of gold trend (trial #645, stage 1: daily mechanism test)

Frozen 2026-10-18 BEFORE any result was computed. Question: does the dollar and the 10-year yield add information beyond gold's own trend?
Stage 1 tests that on the long daily history (2000-08-30 .. 2026-09-03; research/data/d1_study/master.csv: gold futures, DXY, US 10-year yield). Stage 2 (the intraday H4-pullback / M15 trade on broker data) is built ONLY if stage 1 passes; otherwise #645 is closed. Gold here is a futures series, a proxy for XAUUSDm, and costs are modelled as a flat per-switch charge.

## States (computed on day t closes only; applied to the NEXT day t+1 return, i.e. one-day lag so cross-market close times cannot leak)
- Trend direction s_t = +1 if gold close > SMA100(gold), -1 if below. (Needs 100 days of history.)
- Confirmed-long: s=+1 AND DXY close < SMA50(DXY) AND y10 close - y10 close 20 trading days earlier <= 0 (yield momentum non-rising).
- Confirmed-short: s=-1 AND DXY close > SMA50(DXY) AND y10 20-day change >= 0.
- Group C = days that are confirmed (long or short). Group U = days where gold is trending (s=+1 or -1) but NOT confirmed. (C and U partition all days.)
- Signed return x_{t+1} = s_t * (gold close_{t+1} / gold close_t - 1) in %, for t in C or U.

## Primary test (the only pass/fail test)
Welch t-test (normal approximation; n is in the thousands) of mean(x | C) vs mean(x | U), one-sided: C > U. alpha = 0.05. Tests whether confirmation improves the trend signal.
## Stability requirements (all required)
1. mean(x | C) > mean(x | U) in EACH of three eras: 2000-08..2010-12, 2011-01..2018-12, 2019-01..2026-09.
2. mean(x | C) > 0 overall and in at least 2 of 3 eras.
3. The confirmed-only strategy (position = s_t on C days, flat on U days; cost 0.02% per position change) has a positive net annualised return in at least 2 of 3 eras and a max drawdown no worse than the always-in-market SMA100 baseline (position = s_t every day, same cost) over the full sample.
Reported only (no gate): C/U day counts, annualised Sharpe of confirmed strategy vs baseline, long vs short split.

## Decision
All of: primary test passes, stability 1-3 hold -> stage 2 may be pre-registered. Anything less -> #645 CLOSED, no variants (no other SMA lengths, no other yield windows).
Multiple testing: this is one pre-registered test; trial counter becomes 645 for any later deflation.
