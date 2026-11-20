# Fixed gold clock windows: no promotion

Source ideas: https://scholarworks.gvsu.edu/fsdg/975/ and
https://research.cbs.dk/en/studentProjects/gold-price-dynamics-around-the-clock/ .
These describe historical return patterns; they do not supply execution guarantees.
The tested windows are independent fixed XAUUSD adaptations, not original futures or
fixing-price trades. The prior portfolio-hour filter study tested a different question.

Base .02lot, observed/fallback spread, $.02 slippage each fill, $.07 commission and
configured financing. Weekday entry, scheduled exits use first available opening quote;
positions persist through missing exits/closures. No price stops at this screening stage.

| Window / direction | Period | Trades | Win % | PF | Net USD |
|---|---|---:|---:|---:|---:|
| 00:15–08:00 UTC long | 2005–11 | 1709 | 49.9 | 1.014 | 84.95 |
| 00:15–08:00 UTC long | 2012–18 | 1779 | 47.0 | .868 | -932.75 |
| 00:15–08:00 UTC long | 2019–25 | 1804 | 52.5 | 1.096 | 1130.07 |
| London15:15–next weekday10:30 long | 2005–11 | 1760 | 47.3 | .960 | -459.04 |
| London15:15–next weekday10:30 long | 2012–18 | 1789 | 42.3 | .679 | -4537.05 |
| London15:15–next weekday10:30 long | 2019–25 | 1806 | 50.3 | 1.104 | 2025.78 |
| London10:45–14:45 short | 2005–11 | 1733 | 46.0 | .942 | -533.67 |
| London10:45–14:45 short | 2012–18 | 1790 | 47.5 | .877 | -1012.32 |
| London10:45–14:45 short | 2019–25 | 1807 | 46.6 | .921 | -1142.77 |

All nine base window/era cases fail PF>=1.3. London overnight financing totals approximately
$2580/$2598/$2614 paid across the eras. Without any cost or financing its PF is
1.342/.939/1.323: a pre-cost positive pattern does not survive the configured CFD costs
consistently. Asia frictionless PF1.224/1.041/1.196 also never reaches1.3. Latest base
Asia and London-overnight month-block net intervals include zero, and middle-era results
are negative. No winning hour, weekday, direction or date was selected after this run.

The stop-free clock decomposition cannot demonstrate Atlas equity safety. Fixed current
financing is not historical Atlas/broker swap evidence. Missing exits can produce multi-day
exposure: the largest recorded delay was331200 seconds. Retaining it is more realistic
than retrospectively dropping those trades, but does not prove the quotes were executable.
M15 endpoints do not resolve floating drawdown or news rules; those would be required for
a survivor. Final in-sample positions are explicitly liquidated at the last available close.

Full base/stress/frictionless results: gold_clock_windows.json. Base dated cash P&L joins
the aligned matrix, now26 recovered candidate/execution versions including superseded
earlier sweep fills. This is not the total historical search count or26 independent families.
Order randomization describes path sensitivity, not future profit probability. Original
prices were previously inspected; November2026 holdout remains unused. No live changes.

Tests verify the UK spring DST change across a Friday-to-Monday deadline and retention
of a position through a missing scheduled exit, including its financing charge.
