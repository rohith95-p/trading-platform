# Pre-registration: Access lifecycle engineering replay — 18 November 2026

## Question and scope

Can the existing four-leg portfolio complete a mechanically modeled $5,000 Access evaluation and then produce eligible hypothetical $100 trader-cash requests on later pre-explored data under the provisional public-rule ledger? This is an engineering replay, not a new strategy search or independent profitability test. The four-leg portfolio already failed its older evaluation. No strategy, parameter, production configuration or November holdout is changed.

## Fixed inputs and variants

One fixed portfolio lifecycle on July6 2026 inclusive–October30 exclusive (last date October29), using `load_master(M15,M1,D1)` with pre-start warmup. The real `BacktestEngine` runs unchanged strategy classes, fixed .02lot, max3 positions/direction, history7500, protector strategy off, D1 gate on, explicit causal minute-open proxy with entry_delay_sec0 and realistic_ecn modeled costs. Existing live-parity internal gates remain enabled; daily-loss mode uses existing balance_pct setting. Evaluation leverage100; funded leverage50. The experimental Access ledger is `src/research/access_rules_20261118.py`, public-access-2026-11-18-experimental. No old production Atlas wrapper or40% helper substitutes for it.

The only funded cashflow scenario assumes KYC is verified and explicitly supplies instantaneous approval/settlement for a valid $100 cash request at a known flat observation. Every such settlement is hypothetical; actual requests/approvals/receipts are zero. This timing assumption is favorable and cannot establish real payouts. Funded starts at a fresh$5,000 on the first strictly later M15 boundary after a flat evaluation pass; profits are not carried over. No activation fee/time delay is invented; these remain unknown external costs/blockers. No optimizer or alternative candidate is permitted.

## Data/clock and execution policy

M1 coverage is required for exposed intervals. The engine uses m1_policy skip for absent/partial M15 coverage only when already flat; missing blocks are explicit no-trade data-eligibility exclusions, not silently reconstructed prices. This retrospective whole-block coverage eligibility differs from live causal feed availability and must be reported as such. If any existing exposure enters an incomplete block or uncovered quote interval, halt as INDETERMINATE instead of inventing a path. Flat gaps can advance the ledger at every UTC midnight using unchanged realized balance; this is a proven-flat cash reset, not a fabricated quote.

An open position crossing midnight requires an actual aligned00:00 M1 opening observation. The23:59 candle close is not substituted for that quote. End-of-minute observations at midnight with exposure are deferred until the opening quote at that same timestamp; if no exact quote is available, halt indeterminate. Use book times from real engine closes; attribute each close to its UTC exit day. Mark floating equity with project modeled financing/commission reserves, clearly labeled net-liquidation approximation rather than actual broker bookkeeping.

Use opening/end quotes plus conservative M1 intraminute equity envelopes from exposed positions to identify potentially unobserved daily/trailing/Protector/margin triggers. If plausible rule intervention cannot be resolved by the bars/quotes (especially Protector liquidation), halt INDETERMINATE; do not manufacture a close fill or claim compliant survival. Do not present minute samples as continuous ticks. Simulated terminal END_OF_DATA liquidations after a halt are excluded from the rule ledger and separately disclosed.

## Account behavior

Start evaluation at$5,000. Track exact provisional daily and percentage peak-equity floors. Flat balance reaching3% target can pass if no detected breach/indeterminacy. Start a fresh funded ledger on later data. Funded uses20% lifetime-best-day consistency, three>=.5% qualifying days,28-day first/14-day later windows,90% normal split and explicit ledger rounding/re-anchoring. A first detected or potentially hidden Protector event halts indeterminate because broker liquidation fills/deductions are unavailable; no artificial strike-free continuation. Margin auto-close intervention similarly halts pending real execution evidence. News/short-trade/inactivity/deductions are not fully modeled: report the gap, do not certify complete rules.

## Outputs and failure conditions

Save reproducible runner, focused synthetic coupling tests, input hashes, exact configs/costs, protocol and source hashes, phase event traces, UTC reset evidence categories, closed trades, account-floor observations, pass/stop timestamps, payout eligibility/block reasons, opportunities/conditional settlements versus actual receipts, and limitation report. Reconcile engine realized cash with ledger cash before withdrawals and exclude diagnostic halt settlements. Report PF, trade cash, drawdown sampling and count/scope where meaningful; no acceptance threshold is used to rescue this known failed portfolio.

Success means honest mechanically reproducible lifecycle accounting, not passing evaluation or profitability. Missing quote paths, uncertain rollover equity, possible unobserved intervention, failed balance reconciliation or rule ambiguity must stop with a reason and retain partial results. A failed/indeterminate evaluation means no legitimate funded continuation. Do not start a standalone funded account merely to create a favorable output. Commit this protocol before loading outcomes or executing the historical lifecycle.
