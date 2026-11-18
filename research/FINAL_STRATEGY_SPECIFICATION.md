# Final strategy specification — 18 November 2026

## Selection status

**NO QUALIFIED STRATEGY SELECTED from the recovered evidence.** This is a valid research conclusion, not a claim that no gold edge can exist. The previous four-leg portfolio, Genesis rules, Chandelier/ZLSMA and isolated modern-period winners do not meet the complete evidence standard. New finalization results may update this document only with a named frozen protocol, exact implementation, full comparison matrix and independent acceptance evidence.

## Current experimental release behavior

The selected research policy is **abstain**. For every observation timestamp t, the proposed release's authorized order set is O(t)=empty. Its proposed risk allocation is zero. This is a specification only: no production file, running process, account setting, lot, stop, target, session time, holdout flag or portfolio constant has been changed to implement it.

The existing production portfolio remains its existing code. Leaving that code unchanged is not an endorsement to start it. Measurement-only collection may be useful once an isolated demo terminal/account and no-order mode have been verified; setting `ULTRA_DEMO_MODE=1` alone is not no-order mode and relaxes some internal controls. No process was started by this research.

## Mathematical gate for future selection

For frozen features X_t available by decision time t and executable outcome Y_t under a fully declared policy pi, estimate:

V_pi(X_t)=E[realized price cashflow - spread - commission - slippage - financing - applicable program deductions | X_t, pi].

Entry at t cannot use a high, low, close, event value or feature published after t. Historical signal availability, submission delay, quote-side execution, liquidation and period-boundary rules must be explicit. Raw predictive association is insufficient unless executable V_pi is positive with predeclared uncertainty and selection correction.

The specification of a future candidate must include all of:

| Field | Required content |
|---|---|
| Identity | Name, hypothesis, mechanism, protocol commit, code/data hashes |
| Domain | XAUUSD/XAUUSDm, broker/source point units, contract and currency |
| Features | Equations, lookbacks, aggregation alignment, warmup and publication lags |
| Decision | Exact closed-bar/event clock and knowledge boundary |
| Entry | Side, next available bid/ask, submission delay, stale/missing quote refusal |
| Exits | Initial SL, TP, invalidation, timeout, gap fills, within-minute ambiguity policy |
| Risk | Initial cash risk, minimum lot/step, margin preflight, total simultaneous stop risk |
| Constraints | Market hours, news, phase-specific external rules and separate tighter internal reserves |
| State | Restart deduplication, order-intent reconciliation, account-bound durable state |
| Evaluation | Fixed chronological windows, already-explored dates labeled, comparison family and pass/fail |
| Metrics | Full validation table, floating equity, sample limits, complete rejection evidence |
| Deployment | Demo-only identity and verified environment, no real-money permission implied |

## Account scenarios

Small personal account: no minimum-lot feasibility has been established for a selected strategy. The historical sizing ladder is an implementation fact, not proof that a $50/$100 account can withstand its stops. For a100oz/lot gold contract, .01lot is1oz: a$10 gold stop already risks about$10 before additional charges. Actual broker contract and margin specifications must be measured before concluding feasibility.

$5,000 Atlas-style account: no selected strategy is certified for evaluation, funded rules or recurring $100 net payouts. Exact official rules must match the purchased plan, agreement and phase. New current-rule research is documented separately in `../docs/ATLAS_RULES_VERIFICATION.md` when available.

## Promotion and freeze

A newly passing research candidate remains experimental until a precise release hash, no-order/demo isolation, real quote/fill reconciliation, fault handling, current rules and adequate prospective evidence are established. Production strategy changes require the owner's explicit authorization under `.agents/AGENTS.md`; this mission authorizes experimental development while explicitly preserving current production safety settings. Real-money trading, funded-account purchases and changes to funded execution require separate approval.

## Current evidence links

- `PROJECT_RECOVERY_2026-11-18.md`: recovered failures, source code checks and historical scope.
- `STRATEGY_VALIDATION_REPORT.md`: current verdict, required metric coverage and acceptance procedure.
- `results/requested_periods_2026-11-11/REPORT.md`: era-specific positive samples and limitations.
- `../docs/DEPLOYMENT_READINESS.md`: operational blockers and exact next verification steps.
- `../docs/FINALIZATION_STATUS.md`: current execution checkpoint, tests and commits.
