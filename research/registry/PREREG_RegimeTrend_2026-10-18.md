# Pre-registration — Regime-conditional trend on XAUUSDm (trial #640)

Frozen 2026-10-18 BEFORE any result was computed. Any change after the first run is forbidden; failure closes the hypothesis.
Hypothesis: gold trend continuation has positive expectancy only after a measurable higher-timeframe trend plus volatility-expansion regime is established.

## Rules (exact)
- Data: broker bars XAUUSDm (UTC timestamps). D1 and H4 derived from M15 (H4 = UTC 00,04,08,... buckets; D1 = UTC day).
- **Bias** (evaluated on the last CLOSED D1 bar): LONG-only if D1 close > SMA(200) of D1 closes; SHORT-only if below.
- **Volatility regime** (last closed D1 bar): ATR14_D1 > ATR14_D1[5 days earlier] AND ATR14_D1 / ATR14_D1[20 days earlier] > 1.05. ATR = Wilder, 14.
- **Pullback hold at H4 EMA(20)** (last closed H4 bar): LONG: bar low <= EMA20_H4 and bar close > EMA20_H4. SHORT mirrored (high >= EMA, close < EMA). This ARMS the setup for the next 16 M15 bars (one H4 period).
- **M15 confirmation / entry**: during the armed window, the first closed M15 bar that closes beyond EMA20_H4 in the trade direction (above for longs, below for shorts) AND closes in the trade direction (close > open for longs). Enter at the NEXT M15 bar open (long at ask = bid + bar spread, short at bid). One entry per armed window.
- **Exits**: stop 1.0 x ATR14(M15) at the signal bar; target 2.0 x ATR14(M15); time exit at the close of the 48th M15 bar after entry if neither is hit (shorts exit at ask). Stop-first when one bar touches both. Stops/targets checked starting from the entry bar.
- **Position**: one position at a time; no recovery sizing; no pyramiding.
- **News exclusion**: no ENTRY within 30 minutes before or 60 minutes after any event in research/events/usd_high_impact_2022_2026.csv (NFP, CPI, FOMC statement/presser, PCE). Event-day trades are not blended into the baseline; a separate report tags event-day (any such event that UTC day) vs normal days.
- **Costs**: bar spread at entry (long) and at exit (short), swap per rollover night (gold long -500 points x 0.001 per 0.01 lot per night, short 0), plus stress: spread x2 and +$0.30 slippage per fill. Results in R (risk = 1 x ATR stop) and in $ at 0.01 lot.
- **Risk sizing for reporting**: 0.25% of equity per trade on a $5,000 account (R-based curve); also raw 0.01 lot.

## Splits (chronological, no peeking)
DEV 2022-08-01..2024-12-31 · VALIDATE 2025-01-01..2026-06-30 · HOLDOUT 2026-07-01..2026-10-16 (read once).

## Decision rule (falsification gates, not proof)
| Stage | Pass |
|---|---|
| DEV | positive expectancy after costs; not obviously dead (PF >= 1.0) |
| VALIDATE | PF > 1.0, positive expectancy, max DD acceptable (< 15R), performance not confined to a single quarter (no quarter > 50% of net) |
| HOLDOUT | PF > 1.0, positive expectancy, max DD < 5% of the $5,000 curve at 0.25%/trade, >= 10 trades, no single trade or month > 50% of net |
| Then | begin a 90-day forward test with frozen rules; otherwise CLOSE the hypothesis, no retuning |

## Multiple testing
Trial count N = 640 (about 500 gold tests + 139 cross-market tests + this one). Deflated Sharpe Ratio (Bailey & Lopez de Prado): SR0 = sqrt(V)*((1-g)*Z(1-1/N) + g*Z(1-1/(N*e))), g = Euler-Mascheroni; V = 1/T under the null (T = number of trades). Report DSR probability for DEV+VALIDATE and for HOLDOUT; if DSR < 0.95 the result is NOT claimed as an edge even when PF > 1.

## Report
Per period: trades, wins/losses, win rate, gross and net PF, expectancy (R and $), max DD, longest losing streak, avg win/loss and payoff, trades and PF by year, month, session (UTC: Asia 00-07, London 07-12, overlap 12-16, NY-late 16-21), event vs non-event days, exposure (avg holding time, long/short split, days flat), the 2x-spread/+$0.30 stress, DSR.
