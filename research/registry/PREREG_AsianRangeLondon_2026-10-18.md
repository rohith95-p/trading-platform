# Pre-registration — Asian-range / London continuation on XAUUSDm (trial #641)

Frozen 2026-10-18 BEFORE any result was computed. No change after the first run; failure closes the hypothesis (no parameter rescue, no added filters).
Hypothesis: when gold breaks the quiet Asian range in the direction of the D1 trend during the London open, in a normal-width range and expanding intraday volatility, continuation has positive expectancy after costs.
Difference from HYP-070 (liquidity-sweep REVERSAL, rejected): this trades the breakout CONTINUATION with the D1 trend, not a fade of the sweep.

## Rules (exact; every ambiguity in the source advice is resolved here)
- Data: research/data/XAUUSDm_M15.npy (UTC, bar spread in points x 0.001) and XAUUSDm_D1.npy. H1 is built from M15 (UTC hour buckets, only complete buckets of 4 contiguous bars).
- **Asian range** for a UTC day: high/low of M15 bars with open time 00:00–06:45 (the 07:00 bar excluded). Requires >= 24 of 28 bars, else no trade that day. Weekdays only (no data on weekends anyway).
- **D1 bias** (last fully CLOSED D1 bar): D1 close > SMA200 of D1 closes -> LONG only; below -> SHORT only.
- **Volatility filter**: ATR14 (Wilder) on the last closed H1 bar > ATR14 of the H1 bar 5 H1-bars earlier.
- **Range-width filter**: today's Asian range width must lie within [25th, 75th] percentile (inclusive) of the Asian widths of the previous 60 valid trading days (today excluded; needs >= 30 prior values, else no trade).
- **Signal**: among M15 bars whose OPEN time is in [07:00, 10:00) UTC, the FIRST bar that CLOSES outside the Asian range (above the high or below the low). That bar consumes the day: if it closes against the D1 bias, or any filter fails, there is no trade that day.
- **Entry**: next M15 bar open (long at ask = open + bar spread; short at bid = open). The entry bar must be contiguous (15 min after the signal bar).
- **Stop**: 1.0 x ATR14(H1) at the signal bar (last closed H1). **Target**: 2.0 x risk. Broker minimum stop distance is far below this on XAUUSDm and is not modelled.
- **Time exit**: if neither is hit, exit at the close of the last M15 bar before 16:00 UTC (shorts pay the spread).
- **Intrabar**: stops/targets are checked from the entry bar onward on M15 high/low (shorts include the spread); when one bar touches both, the STOP fills first. (M1 refinement is NOT used so the rule is identical to #640.)
- One position, max one trade per day, no re-entry after a stop-out, no recovery sizing.
- **News exclusion**: no ENTRY within 30 min before or 60 min after any event in research/events/usd_high_impact_2022_2026.csv. Event-day trades (any such event that UTC day) are tagged and reported separately.
- **Costs**: bar spread at entry (long) and exit (short); swap per rollover night (long -0.5 price units per 0.01 lot per night, short 0); stress run = spread x2 plus $0.30 slippage per fill. Results in R (1R = the stop distance) and $ at 0.01 lot; reporting curve at 0.25% of a $5,000 account per trade.
- Atlas 3-minute minimum hold is respected by construction: entry is a bar open and the earliest evaluated exit is that bar's end (15 min).

## Splits (chronological)
DEV 2022-08-01..2024-12-31 · VALIDATE 2025-01-01..2026-06-30 · HOLDOUT 2026-07-01..end of data (2026-10-13).
Disclosure: the holdout window was already read for trial #640 and was observed live by the demo bot, so it is weaker than a virgin holdout; it can falsify but cannot by itself prove anything.

## Decision rule (falsification gates, not proof)
| Stage | Pass |
|---|---|
| DEV | PF > 1.15 net of costs, expectancy > 0, max DD < 5% of the $5,000 curve (< 20R at 0.25%/trade) |
| VALIDATE | same, plus no calendar quarter > 50% of net R |
| HOLDOUT | PF > 1.0 and expectancy > 0 -> proceed to a 90-day frozen forward test; otherwise CLOSE #641 |
| Sample | >= 100 trades across DEV+VALIDATE or the result is "inconclusive", not a pass |
| Stress | the 2x-spread/+$0.30 run must keep expectancy > 0 on DEV+VALIDATE for a pass to be called robust |

## Multiple testing
N = 641. Deflated Sharpe (Bailey & Lopez de Prado), same formula as #640, V = 1/T. If DSR < 0.95 the result is NOT claimed as an edge even when PF > 1.

## Report
As #640: per period trades, win rate, gross/net PF, expectancy R and $, max DD, losing streak, payoff, by year / quarter / session, event vs non-event days, long/short split, exits (SL/TP/TIME), stress run, DSR.
