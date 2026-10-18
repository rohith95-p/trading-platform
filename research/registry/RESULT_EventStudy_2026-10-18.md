# Result — gold event study around scheduled USD releases (descriptive; protocol 30f29a9, script committed before the run)

218 events with a trusted calendar row, 212 usable (6 dropped for bar gaps). M15 bars, 2022-07..2026-10-13. No surprise (actual vs consensus) data exists in the calendar, so surprise splits were NOT done.
Multiple-testing: 20 pre-declared tests, Benjamini-Hochberg. t-tests use a normal approximation (scipy is not installed), which is slightly anti-conservative.

| Event | n | Median range ratio, first hour vs prior 2 h | Mean move in first 15 min | Mean drift 15->120 min | Reversal rate |
|---|---|---|---|---|---|
| NFP | 47 | **3.8x** | -0.31 A | +0.24 A | 53% |
| CPI | 48 | **4.1x** | +1.60 A | -0.78 A | 58% |
| PCE | 49 | 2.1x | +0.58 A | -0.24 A | 44% |
| FOMC statement | 34 | **3.6x** | +0.02 A | -0.56 A | 38% |
| FOMC press conf. | 34 | 2.3x | +0.47 A | -0.68 A | 38% |
(A = average pre-event 15-minute true range, about $2.6-3.0 for the median event.)

## What is real
- Volatility: every category expands range, 96-100% of events, BH p < 0.001. NFP, CPI and FOMC statements run 3.5-4x normal for the first hour. This is a robust, economically obvious fact.

## What is not
- No directional or reversal pattern survives correction. The best raw results (CPI and PCE mean first-15-minute move, raw p 0.03) have BH-adjusted p = 0.098, driven by a few large events. Drift after 15 minutes: all BH p >= 0.38. Reversal vs continuation: all BH p >= 0.38 (FOMC reversal rate of 38% is the closest, still not significant, n=34).
- Spread: the stored M15 bar spread is a snapshot at the bar open and shows no widening (x1.0), which is not credible for a news minute. This study cannot say whether a post-release entry is affordable. Do not trust the spread row.

## Verdict
- Volatility facts: usable for risk (the live news filter blackout and wider stops), already consistent with the existing ±15 minute blackout and the ±30/60 minute rule used in #640/#641.
- Trial #642 as proposed (direction from the post-release M5 close, entry after 15 minutes) has NO supporting evidence: there is no drift or reversal to harvest in the data we hold. Not pre-registered. To reopen, it would need tick-level spread and release-surprise data, which we do not have.
- This family (scheduled-release trading) is parked.
