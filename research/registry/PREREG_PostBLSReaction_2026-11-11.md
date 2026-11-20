# Post-release gold reaction: fixed public-data experiment

Written before examining outcomes of this runner; old event study results and recent eras
already inspected. Not pristine out-of-sample. Economic motivation, not a claimed exact
published strategy: https://doi.org/10.1016/S0148-6195(00)00029-1 and
https://www.sciencedirect.com/science/article/pii/S1057521924004186 . Announcements can
move gold; neither observation proves that chasing the first move is profitable.

Official CPI/NFP archive links resolved 2026-11-11, data reference years 2019–2025 plus
December2018 releases. Parse actual release dates from filename, only actual years2019–25.
Assume 08:30 America/New_York with DST; direct archived 2024 CPI/NFP embargo spot checks.
Original prior-announcement schedule vintages unavailable: known actual release-day labels
do not establish that rescheduling was available to a trader at an earlier time. No revised
economic values or consensus data enter signal. Preserve links and hash them in output.

XAUUSD M1 only. Require continuous event minute0 through60, with coverage attrition reported
explicitly (retrospective availability filter). Signal = close of minute14 minus open0.
Enter at minute16 opening quote, after the initial fifteen minutes have fully closed.
Two fixed arms: follow sign and opposite sign. Stop one initial15-minute high-low range
from actual executable entry; no profit target. Exit at minute60 open if not stopped.
Do not inspect minute60 high/low for stop. No exposure on first release minute, no positions
overnight. One .02 lot position per event, overlapping/doubled events rejected.

Base realistic_ecn bid/ask, $.02 adverse slippage each market/stop fill, $.07 commission.
Stress: spread2x and slippage3x; diagnostic frictionless counterfactual independently replayed
(stop level therefore may differ). Intraminute spread spikes/latency unknown; not tick replay.
Entry minute16 is beyond source event +/-5-minute window but other news restrictions and
the full Atlas account path remain unverified. This is sparse event component, not daily trading.

Fixed chronological eras 2019–21,2022–23,2024–25. Require trade PF>=1.3 and >=30 trades in
each era to advance; gross before-cost returns alone do not qualify. Report categories without
selecting a winning subset, raw/count attrition, costs, win rate/risk ratios, bootstrap monthly
mean CI, trade-order MC, ablation and same-era randomized signal direction with Bonferroni
adjustment for the six base arm/era tests. Preserve all cost scenarios. No threshold tuning.
Do not spend November2026 holdout. Calendar horizon ends2025, no monetary policy/shutdown
surprise assumptions added to fill gaps. Full Atlas/payout simulation only for a survivor.
