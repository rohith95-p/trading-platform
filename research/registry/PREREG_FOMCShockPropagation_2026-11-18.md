# FOMC normalized shock propagation — fixed experimental strategy

Commit before reading XAUUSD event outcomes. This is a new project hypothesis, not a claim of world-first novelty or profitability. Official SF Fed USMPD calendar metadata is public; its retrospective rate/dollar surprise series is **not** a historically published trading input. Use only Statements date/time and scheduled status, with Eastern Time localized using America/New_York; restrict2016–2025 and scheduled14:00 statements. Original source: https://www.frbsf.org/research-and-insights/data-and-indicators/us-monetary-policy-event-study-database/ . January2016 release timing is independently confirmed by https://www.federalreserve.gov/newsevents/pressreleases/monetary20160127a.htm . No textual sentiment, revised macro values, full-window PCA or consensus data is used.

## Falsifiable mechanism and rules

An initial information shock unusually large relative to pre-statement risk may propagate into the subsequent communication window. Predict direction only after observing the initial gold response; never pretend the decision/surprise was known in advance. One deterministic candidate:

- Pre-statement risk: sixty complete M1 bars13:00–13:59 ET; minute log(close/open) RMS, expected30-minute scale `sqrt(30)*RMS60`.
- Shock: log(close14:29/open14:00), from complete14:00–14:29 ET minutes.
- Gate: absolute shock strictly exceeds2 times the expected30-minute pre-risk scale; pre-risk positive and finite. Direction follows shock.
- Entry14:45 ET first exact observed opening quote;15-minute deliberate information/execution delay after feature freeze14:30, outside statement and standard14:30pressconference-start±5min windows. This does not certify the actual funded news calendar.
- Stop2 times production ATR14 on closed M15 history as of entry; target4 times that ATR; static geometry, no trailing, break-even, partial or consolidation exit. Time exit15:45 ET opening quote, or earlier protective stop/target through BacktestEngine's strict M1 handling. Fixed0.02lots, maximum1position, start$5000perera, carry ending cash between event replays; no risk compounding or Atlas qualification.
- Price source exclusively `load_master(M15,M1)` before2026-01-01. Full exact minute coverage required from13:00through15:59ET for features and execution. Missing windows are excluded and logged, never filled or reconstructed. Master-source gaps and mixed M15/M1 provenance remain limitations. No November2026 bars accessed.

## Comparisons and predeclared limits

Two fixed eras2016–2021 and2022–2025; neither is untouched after previous project research. All runs use identical rules. Controls: unfiltered shock-following on all eligible scheduled events, plus always-buy and always-sell on the candidate's eligible timestamps with identical exits and costs. A balanced random-direction benchmark samples these two direction-control results; no winning control may be relabeled as the candidate after seeing outcomes.

Three execution scenarios, all reported: base repository realistic_ecn; stress2xspread/60point adverse slippage; 60second additional entry delay at14:46 via minute scan clock (no interpolation). Hold ends15:45 unchanged, geometry recomputed causally at actual entry by engine. Costs are declared scenarios, not Atlas-calibrated actual fills. No parameter sweep or strategy rescue after outcomes.

Acceptance for further confirmation (not deployment): at least30candidate trades in **each** era; positive after-cost net and PF>=1.20 in both; positive pooled mean with95% calendar-quarter block bootstrap interval above0 and superiority to balanced direction control under Bonferroni4 correction(twoeras×net/controlcontrasts); stress and delay retain positive pooled net; sampled MTM DD<3.6% of initial$5000; drop-besttrade leaves positive net. Any failed criterion means no promotion. Report full24risk/uncertainty metrics where identifiable; do not invent meaningful Sharpe/DSR/PBO from incomplete trial histories. Count one candidate, threeexecution scenarios and threecontrols; complete projectwide effective trial count is unknown.

Run through BacktestEngine only, actual RiskManager stop geometry, minute protective execution and costs. Time exit uses a narrowly scoped experimental account-policy hook calling engine._close at the known opening quote with adverse exit slippage. Save every signal feature, event inclusion/exclusion, trade, sampled equity, scenario, input/code/protocol hash and diagnostics; do not alter production modules/settings. Synthetic causality/clock/timed-exit tests precede empirical evaluation. No real/demo broker access, deployment or capital purchase.

## Implementation clarification before any price evaluation

The engine's ordinary ATR call includes a synthetic flat forming bar, while this protocol specifies closed-bar ATR. A research-only BacktestEngine subclass will pass `m15_view[:-1]` into the original RiskManager.calculate_atr_stops, preserving its actual seeded ATR14, rounding and2/4multipliers. It does not implement a separate stop formula. A minute-clock policy reads only engine equity samples tagged `open`, because the policy also receives prior interval-end callbacks at the same timestamp; that end callback must not submit an entry or time-exit before the new opening quote exists. A synthetic test must distinguish the previous close from the next open across a gap.
