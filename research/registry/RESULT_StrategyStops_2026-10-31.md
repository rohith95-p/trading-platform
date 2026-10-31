# RESULT: strategy-specific stops and targets (2026-10-31)

Pre-registration: `PREREG_StrategyStops_2026-10-31.md`. Script: `scripts/validation/strategy_stops_study.py`.
96 variants (each strategy's own range / breakout candle / London range / sweep wick for stops; measured moves,
London-range projections, previous-day extremes, London midpoint/far side, 2R and ATR for targets), in two sizing
modes. Candidate = best DEV+TEST net; four pre-set checks.

| Strategy | Mode | Candidate | DEV / TEST / RECENT (live) | WF-A | WF-B | DD | MC P | Result |
|---|---|---|---|---|---|---|---|---|
| Asian Range Filtered | fixed | range midpoint stop, 2R | +$99 / +$826 / +$638 (+$42 / +$603 / +$141) | fail | ok | fail ($262 vs $113) | 0.96 | fail |
| Asian Range Filtered | equal risk | 25% inside, 2R | +$76 / +$667 / +$108 | fail | fail | ok | 0.61 | fail |
| Asian Breakout | fixed | range midpoint, 2x measured move | +$139 / +$216 / −$64 (+$32 / +$92 / +$80) | ok | fail | ok | 0.68 | fail |
| Asian Breakout | equal risk | breakout candle, 2x measured move | +$257 / +$278 / −$19 | ok | fail | ok | 0.82 | fail |
| London Momentum Tight | fixed | far side of London range, 2R | −$83 / +$1,246 / +$279 (−$17 / +$122 / +$341) | ok | fail | ok | 0.96 | fail |
| London Momentum Tight | equal risk | far side of London range, 2R | −$58 / +$623 / +$186 | fail | fail | ok | 0.82 | fail |
| NY Session Reversal | fixed | wick + 0.5 ATR, 2R | +$91 / +$169 / +$22 (+$78 / +$319 / +$228) | fail | fail | ok | 0.13 | fail |
| NY Session Reversal | equal risk | wick, ATR target | +$44 / +$355 / +$175 | fail | fail | fail | 0.44 | fail |

Verdict: nothing passes. Strategy-specific levels win big in one period and lose in another (London: +$1,124 in
TEST, worse in DEV and RECENT; Asian Breakout: better 2022-26, loses on RECENT). The live ATR stops stay.
