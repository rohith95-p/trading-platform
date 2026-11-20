# VWAP / EMA gold: real-bar screening protocol

Written before runner execution, not an independently committed preregistration.
Paper: https://ssrn.com/abstract=6650958 ; full-text mirror of the paper:
https://www.scribd.com/document/1063631287/ssrn-6650958 .
The author's Section 6.1 describes probability-parameterised trade simulation;
Section 7.2 distinguishes it from historical bar replay. PF 1.76 is not independently verified market evidence.
GitHub adaptation: https://github.com/mrZtrader68/gc-strategies/blob/main/vwap_regime_strategy.py

Two fixed arms, independently implemented, XAUUSD only, M15 through 2025.
Common EMA50/200, typical-price VWAP weighted by tick_volume, next-adjacent-open fills,
hard intrabar stop, EMA adverse-close exit at next open. Commission/spread/slippage/swap use
realistic_ecn, fixed .02 lots, no tuning. Three inspected eras 2005–11, 2012–18, 2019–25.
Warmup >=200 bars; stop-first ambiguous bars; gap-aware bid/ask execution.

Arm github_core: calendar-UTC daily VWAP, EMA regime and VWAP direction, previous bar
touches its EMA50 and current directional candle closes beyond EMA50. Initial stop 1.5
simple-mean ATR14 from executable entry; no target, following the public script's core.
Unlike the source, executable next-open fills and costs, fixed size and final liquidation are explicit.

Arm paper_core: fixed 13:30–20:00 UTC session VWAP; exclude EMA200 distance <=.1%;
touch EMA50 within current/prior bar; directional pin or body engulfing; tick volume >1.1
times inclusive SMA20; range >=.8 Wilder ATR14. Signal low/high plus .5ATR buffer stop,
3R target; adverse close EMA50 exit, EMA20 when closing floating profit >=2.5R.
Fixed-UTC session deliberately follows paper's stated UTC hours, not DST-adjusted NY hours.
Flat first observed open at/after20UTC, skip nonadjacent entries. No same-bar exit/reentry.

Limitations: this is a test of core mechanisms, not a full paper replication. News exclusions
and manual news stop overrides lack an executable complete specification/input here;
VWAP compressed-approach partial exits also omitted rather than invented. No paper
Kelly/ATR sizing, no daily-cap rule: fixed .02 lot makes raw signal P&L comparable, while
paper risk formula does not account for full entry-to-stop distance. Any survivor must
receive those account-level tests before promotion. Broker tick volume is not consolidated
trade volume; results may depend on historical source changes.

Save all arms, dated P&L, PF/win rate/expectancy/DD/Sortino/Omega/Calmar/recovery,
best/worst trade ablation and trade-order Monte Carlo. Require PF >=1.3 every era before
advancing. November holdout excluded. Every arm counts toward search multiplicity.
