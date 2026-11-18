# Execution reality engineering audit, 2026-11-18

Scope: synthetic regression tests of the existing BacktestEngine, not a strategy search.
No production settings, live orders, broker connections, or November holdout data.

Acceptance criteria fixed before running synthetic tests (the first draft of
engine edits existed uncommitted when this protocol was committed; therefore
this is not represented as a pre-implementation Git commitment):

1. M1 OHLC must not manufacture a subminute executable quote. Nonzero delay
   requests fail closed unless explicitly marked legacy reproduction. The legacy
   interpolation remains identified as noncausal and unusable as validation evidence.
2. Default stop-market gaps fill at the adverse observed opening side plus modeled
   slippage. Explicit old level-fill mode remains for reproducing old experiments.
3. `m1_policy=require` rejects partial and wholly absent minute coverage. Exact
   grid timestamps, not row count alone, determine completeness. `skip` skips the
   incomplete execution interval and records unchecked position intervals.
4. Tests verify both directions, invariance/rejection of future-dependent delay,
   partial/duplicate minute coverage, and explicit legacy reproduction.

No profitability threshold or strategy parameter is selected here. Existing
historical outputs remain historical; changes require new versioned evaluations.
Known limitations (OHLC path order, reconstructed Ask, partial entry-bar handling,
floating equity granularity, broker financing/margin assumptions, demo parity)
must be reported rather than silently described as realistic.
