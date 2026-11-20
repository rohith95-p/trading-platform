# Fixed gold clock-window effects

Recorded before runner outcomes; historical eras already inspected in other studies.
Primary sources: https://scholarworks.gvsu.edu/fsdg/975/ (Blose/Gondhalekar, futures
overnight anomaly, not an executable spot rule); https://research.cbs.dk/en/studentProjects/gold-price-dynamics-around-the-clock/
(2019 thesis, costs weaken the historical seasonal pattern); SSRN7257240 (Asia00–08UTC,
limited recent sample). No claim that descriptive seasonality proves a tradable edge.

Three fixed XAUUSD adaptations, .02 lot (2oz), no clock/weekday/parameter optimization:
1. asia_long: enter00:15 UTC, exit08:00 UTC, weekday entries. Independent of prior US
direction, unlike the earlier conditional US/Asia study. Fifteen-minute opening delay.
2. london_overnight_long: enter15:15 Europe/London, exit10:30 next weekday, including
Friday-to-Monday exposure. London clock adjusts DST. These opening quotes are not the
PM/AM auction fixing prices, whose timing/executability differs.
3. london_intraday_short: enter10:45 Europe/London, exit14:45 same date, weekdays.

Use actual M15 opening quotes; scheduled exit at first available quote at/after deadline,
not a retrospective complete-window filter. If exit is delayed by market closure/data gap,
retain the position, report delay, charge all calendar funding rollovers. One position per
arm, skip any overlapping scheduled entry. Final positions close at last in-sample close.
No price-dependent exit, hence M15 suffices for endpoints but not intra-trade risk. No hard
stop in this initial decomposition: it is a timing-edge screen, not a deployable account.
Broker quote availability/historical source changes remain limitations. Financing uses
current configured long swap across history; model is not a point-in-time financing series.

Base: realistic_ecn bid/ask, $.02 adverse market-fill slippage, $.07 commission; independent
stress2x spread,3x slippage; frictionless no fees/spread/slippage/funding, clearly labelled.
Fixed eras2005–11,2012–18,2019–25; fixed size, separate reset at era boundaries. Report
PF, individual win rate, net/expectancy/risk ratios, swap totals, delayed exits, ablation,
trade-order MC and month-block total-net bootstrap CI. Base dated P&L for aligned trials.
Require PF>=1.3 and net positive every era before stop/news/Atlas/payout replay. A positive
aggregate clock return or recent-only result does not qualify. November2026 untouched.
