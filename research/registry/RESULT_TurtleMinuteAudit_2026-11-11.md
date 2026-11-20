# Turtle minute replay and cash-flow feasibility: not qualified

User confirmed researching before buying. No Atlas account credentials/contracts were
available or purchased; no paid data, external messages or live orders used. Cost inputs
remain project ECN assumptions rather than verified Atlas specifications.

Fixed daily M15-derived channels/N joined to actual M1 execution prices; no parameter
tuning. Unit-level fills retained. Equity independently reconstructed at observed minute
opens, including entry-side commission and accrued financing. Closed baskets reconcile
to final cash. This is sampled equity, not complete tick-path verification.

| Unit count (.02lot each) | Era | Baskets | M1 PF | Net USD | Sampled equity DD |
|---|---|---:|---:|---:|---:|
| 1 | 2005–11 | 35 | .605 | -586.74 | 19.03% |
| up to4 | 2005–11 | 37 | .681 | -1309.27 | 43.67% |
| 1 | 2012–18 | 39 | .768 | -421.81 | 22.66% |
| up to4 | 2012–18 | 42 | .907 | -470.89 | 49.73% |
| 1 | 2019–25 | 28 | 3.291 | 2493.47 | 16.47% |
| up to4 | 2019–25 | 33 | 2.502 | 7610.99 | 71.46% |

The recent single-unit PF largely survives M1 refinement. Closed-basket M15 DD9.97%
understates the observed minute-opening equity drawdown16.47%. A profitable total
therefore does not establish trailing-loss compatibility. Four-unit risk remains extreme.

Limited linked evaluation-to-funded scenarios, starting each era with$5000:

| Units | Era | .02lot result after evaluation | Assumed .01lot result after evaluation |
|---|---|---|---|
| 1 | 2005–11 | Evaluation did not pass | Evaluation did not pass before sample end |
| up to4 | 2005–11 | Evaluation did not pass | Evaluation did not pass |
| 1 | 2012–18 | Funded protector intervention2013-09-10 | Funded sampled breach2015-05-26 |
| up to4 | 2012–18 | Evaluation did not pass | Evaluation did not pass |
| 1 | 2019–25 | Funded sampled breach2020-02-28 | Funded sampled breach2025-10-21 |
| up to4 | 2019–25 | Evaluation did not pass | Evaluation did not pass |

Every linked and independent funded scenario produced $0 eligible hypothetical cash
withdrawal before stopping. Requested $100cash was modeled as $111.11 gross at90%split,
with waiting period, qualifying closed-profit days, consistency and withdrawal reanchoring
from the existing AccessAccount helper. Evaluation profits are discarded at funded start.
Linked activation assumes instant fresh funding with no fee/delay, an optimistic assumption.
.01lot prices/fills are unchanged; all linear cash costs scale by.5, with no verified Atlas
minimum-lot assertion. These are conditional scenario outcomes, not pass/payout probabilities.

Critical limitations:
- Stop at first sampled2%-anchor floating loss requiring protector liquidation; do not
  reuse the unmodified strategy path afterward. This is not a full first/second-strike or
  reduced-split simulation. Hard drawdown breaches take precedence at a coincident sample.
- News and short-hold profit deductions, weekend entry restrictions, margin constraints,
  activation fees, issuance delay, and full lifecycle rule differences are not enforced.
- Missing observations and first-available-quote daily resets cannot establish exact
  midnight equity floors. Intraminute equity/quote spikes remain unseen.
- Coverage2005–11:1833343 bars,180521 gaps>1minute,max393600seconds;
  2012–18:2422700 bars,4481 gaps,max292680seconds;
  2019–25:2434927 bars,2297 gaps,max2794320seconds. Counts include normal closures,
  sparse/no-tick intervals and missing history; they are not all data errors. The latest
  max gap exceeds32days. No interpolation or complete-data certification was performed.
- Higher-timeframe and minute histories can use different feeds. Data/content hashes are
  preserved, and risk-only reruns reject changed execution inputs.

Artifacts: turtle_minute_audit.json (all baskets/fills, raw metrics, coverage, independent
and linked phase diagnostics, both sizes). Initial risk report retained separately.
Current risk runner fixes hard-floor/protector precedence and adds phase/size diagnostics
without rewriting immutable execution-return records. Recovered comparison contains30
candidate/execution versions, including superseded earlier fill diagnostics; total historical
trial count remains incomplete. November2026 holdout unused; no live configuration changes.

Tests cover minute timestamps, long/short entry-fee equity marks, exact final cash
reconciliation, hard-floor precedence, stopping before protector-altered paths, and funded
cash reset excluding evaluation profits. Decision: retain research evidence; no activation.
