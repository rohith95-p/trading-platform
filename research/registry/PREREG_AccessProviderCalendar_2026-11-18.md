# Pre-registration: provider-calendar Access lifecycle sensitivity — 18 November2026

## New external evidence and scope

Preserve the primary AccessLifecycle result unchanged: it stopped at the first exposed partial M1 block. A separate official Exness schedule notice updated3 November2026 distinguishes scheduled XAUUSD closure from active-session missing data. Source: https://get.exness.help/hc/en-us/articles/31342732737180-Trading-Hours-Update-End-of-US-Daylight-Saving-Time-01-Nov-2026 . This notice describes the then-current summer schedule and the November change; treating it as the July–October historical contract schedule is an explicitly **unverified historical-calendar assumption**. It is not Atlas trading hours or a point-in-time alpha feature.

The sensitivity is a fixed engineering scenario on the same pre-explored July6–October29 master data and four-leg portfolio, not a strategy/parameter rescue. No primary output is overwritten, no production/default execution change and no November price data consumed.

## Calendar and quote handling

Use the notice's ordinary XAUUSD summer UTC schedule for the complete window (all dates precede US DST end): Mon–Thu open before20:58, closed20:58–22:00:30, close-only22:00:30–22:02, fully open thereafter; Friday closed from20:58 until Sunday close-only22:01:30–22:05, then open. Saturday closed. Do not apply the separate XAUUSD247 schedule. A minute can contain a quote when any part intersects an open/close-only interval; it cannot authorize a new entry until its integer opening timestamp is wholly in full-open mode. Subminute reopening timestamps remain interval uncertainty, not invented exact quote times.

Verify broker-cache manifest server/symbol/timeframe, content hashes and timestamp coverage; save provenance and label clocks as source-declared UTC without a live-terminal certificate. Confirm the raw M1 observations against this assumed calendar. Process actual13 observed minutes in a closure-boundary15-minute block. Use real engine m1_policy coarse only as an internal permission to process partial arrays: the scenario subclass must never provide a synthetic M15 fallback, interpolate missing quotes or walk a coarse15-minute price bar. Return empty actual M1 arrays for fully scheduled-closed blocks.

Every missing minute outside scheduled closure aborts as INDETERMINATE, including unverified holidays, unexpected gaps and missing partial close-only reopening minutes. Observations that contradict scheduled closure also abort. Whole M15 gaps with open exposure are traversable only if every unobserved quote minute belongs to this explicitly assumed closure calendar. No entry is allowed in close-only or closed intervals. Existing orders retain stops and are marked/checked on the next actual quote; adverse reopening stop gaps use the engine's real quote-open fill convention. Do not invent a smooth price path while the market is closed.

## Account path, constants and uncertainty

All other primary lifecycle settings stay fixed: real BacktestEngine, existing .02lot portfolio/internal gates, causal minute-open proxy, modeled ECN costs, eval/funded leverage100/50, provisional public-rule ledger, flat3% evaluation pass then fresh$5,000 funded account on strictly later M15 boundary, eligibility-gated hypothetical$100 trader cash with explicit favorable instant approval scenario. Payout requests/receipts remain hypothetical; no actual payments are claimed. Exact00UTC quote or proven-flat cash remains required for UTC reset; a scheduled market closure alone does not provide unknown floating midnight equity. Conservative OHLC rule envelopes continue to halt unresolved Protector/margin/floor intervention without invented liquidation.

## Comparisons and outputs

Exactly one added calendar scenario, compared descriptively with the preserved primary indeterminate result. No schedule boundaries, cost values, entry rules or acceptance conditions may be retuned after outcomes. Save full config/hash/provenance, source retrieval dates and assumptions, observed minute checks, scheduled closure traversals, close-only entry blocks, phase/account/payout events and status. A result can remain indeterminate. Calendar-assumed completion is not continuous-tick verification, actual Atlas qualification or independent strategy acceptance. Unknown financing/contracts, rule deductions, fees and real approval delays retain primary limitations.
