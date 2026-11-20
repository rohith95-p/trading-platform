# Public gold sweep / imbalance: no qualifying edge

Source: https://github.com/baturdenada/gold-sweep-backtester
Source timing review: src/sweepbt/imbalance.py (OB recognition), simulate.py (entry
availability and intrabar outcomes), trend.py (entry-index close used in filter).
Source is reviewed, not executed or copied. The independent adaptation adds causal
confirmation, completed-bar EMA, bid/ask costs, conservative entry-bar target handling,
one-position exposure and explicit session/gap liquidation.

Corrected executable-opening-price results:

| Arm | Era | Trades | Win % | PF | Net USD | Closed-balance max DD |
|---|---|---:|---:|---:|---:|---:|
| Raw | 2005–11 | 3170 | 33.4 | .887 | -1080.32 | 24.69% |
| Raw | 2012–18 | 5080 | 30.5 | .773 | -3182.00 | 63.79% |
| Raw | 2019–25 | 5366 | 31.4 | .831 | -3709.50 | 78.72% |
| EMA | 2005–11 | 1202 | 36.3 | .980 | -79.99 | 6.73% |
| EMA | 2012–18 | 1922 | 32.4 | .775 | -1360.35 | 28.92% |
| EMA | 2019–25 | 1914 | 35.1 | .988 | -106.49 | 15.71% |

Every era fails the >=1.3 trade-PF threshold. No Atlas pass/payout claim; no promotion.
These are already-inspected development data. November forward holdout untouched.

The first fill version deliberately denied favorable opening-price improvement to resting
limits. Review found this too pessimistic for a realistic fill comparison; the rerun gives
marketable limits the better opening quote and recalculates target risk from that fill.
Corrected output: public_sweep_executable_open.json, dated arms suffixed _executable_open.
Original public_sweep.json and unsuffixed dated arms remain as superseded fill diagnostics.
The recovered matrix now retains 20 candidate/execution versions, including those two
superseded versions; this is not twenty distinct strategy families or the complete search count.

One remaining screen assumption rejects pending activation if the opening quote puts the
attached stop on the invalid side. Broker behavior across those gaps needs confirmation
before any successful candidate is promoted. M15 data cannot resolve all intrabar ordering.
These results assess the documented adaptation, not every possible sweep formulation.

During the first uncapped diagnostic, hypothetical losses exceeded reference capital.
The ratios helper previously produced invalid annualized-return values after exhaustion.
It now flags nonpositive closed balance, records the first affected trade, and omits CAGR
and Calmar after exhaustion, even if a later hypothetical recovery lifts balance above zero.
Uncapped signal P&L beyond that point is not a feasible account trading path. Exact
floating-equity liquidation and Atlas floors belong in a later account-level replay.

Tests cover pivot confirmation delay, OB recognition timing, excluding pre-entry favorable
extremes, opening quote improvement on both sides, prefix invariance of completed trades,
and finite JSON/null compound metrics for exhausted and empty paths. The previous monthly
selection experiment now also preserves a content-addressed copy of its exact input CSV
before that recovered matrix changes. Full ratios, ablations and Monte Carlo outputs are
stored with each run; trade-order shuffles do not establish future profitability.
