# USD high-impact events, 2022-07-01 to 2026-10-16

File: `usd_high_impact_2022_2026.csv` (220 rows). Columns: event_id, category, name, scheduled_utc, local_time_et, source_url, verified, notes.
Window ends 2026-10-16: the Oct 27-28 and Dec 8-9 2026 FOMC meetings, the Oct 29 2026 PCE and the Nov 6 2026 NFP are after the cutoff and not included.

## Sources (all fetched 2026-10-18)
- NFP / CPI: BLS release archive pages https://www.bls.gov/bls/news-release/empsit.htm and cpi.htm. The pages list archived releases by file name (empsit_MMDDYYYY); dates are read from those file names. Embargo 08:30 ET confirmed directly on archived releases for 2025-12-16 NFP, 2026-02-11 NFP, 2025-12-18 CPI. BLS lists Oct 2025 as "not published" for both (funding lapse).
- FOMC: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm (meeting list + press conference flag). Statement 14:00 ET on the second day; press conference 14:30 ET (standard; start time not checked per meeting).
- PCE: BEA archive (https://www.bea.gov/news/archive, title "Personal Income and Outlays") for 2022-2025, and https://www.bea.gov/news/schedule/full (2026), /news/schedule/full-2025 (2025 times). Release pages spot-checked: 2022-07-29 (8:30 EDT), 2025-12-05 (10:00 EST).
- UTC conversion: EDT (UTC-4) from 2nd Sunday of March to 1st Sunday of November, else EST (UTC-5), computed by hand in the generator and cross-checked against Python zoneinfo America/New_York: 0 mismatches over all 220 rows.

## Counts (rows) per year
| Year | NFP | CPI | FOMC_STATEMENT | FOMC_PRESSER | PCE |
|---|---|---|---|---|---|
| 2022 (Jul-Dec) | 6 | 6 | 4 | 4 | 6 |
| 2023 | 12 | 12 | 8 | 8 | 12 |
| 2024 | 12 | 12 | 8 | 8 | 12 |
| 2025 | 11 | 11 | 8 | 8 | 10 |
| 2026 (to Oct 16) | 10 | 10 | 6 | 6 | 10 |

Deviations:
- 2022: half year by design (Jul 8 NFP onward).
- 2025 NFP/CPI 11: October 2025 reports never published (funding lapse). The Jan-2025 NFP is Feb 7 2025; Dec 2025 data is released in 2026. 2025 PCE 10: Oct 2025 PCE released only as a combined Oct+Nov release on 2026-01-22; Dec 2024 data released 2025-01-31; BEA also issued a "Data Update" for Sep 2025 on 2025-12-23 (not tabulated).
- 2026 counts: NFP covers Dec-2025 data (Jan 9) through Sep-2026 data (Oct 2); CPI covers Dec-2025 data (Jan 13) through Sep (Oct 14); PCE covers Jan 22 (combined Oct+Nov 2025) through Sep 30; FOMC through Sep 15-16.
- FOMC: 8 scheduled meetings per year = 16 rows. No unscheduled FOMC meeting with a statement occurred in 2022-2026 per the Fed page. The only unscheduled item is 2025-08-22, a notation vote adopting the longer-run-goals statement (no 14:00 policy statement, no press conference); it is NOT in the CSV.

## Sanity checks
- No duplicate event_ids (asserted in generator; one event per category per date).
- NFP on a Friday except (all documented in notes): 2025-07-03 Thu (Jul 4 holiday), 2025-11-20 Thu (post-shutdown delay, Sep data), 2025-12-16 Tue (post-shutdown, Nov data), 2026-02-11 Wed (delayed; BLS page gives no reason, early-2026 appropriations lapse inferred), 2026-07-02 Thu (Jul 3 observed holiday).
- FOMC dates equal the Fed's own list (statement date = meeting end date).
- DST examples (UTC from ET): 2023-03-10 NFP 08:30 EST = 13:30Z (day before US DST start of Mar 12); 2023-11-03 NFP 08:30 EDT = 12:30Z (before Nov 5 end); 2022-11-10 CPI 08:30 EST = 13:30Z (after Nov 6 end); summer 2022-07-27 FOMC 14:00 EDT = 18:00Z; 2025-03-07 NFP 13:30Z (before Mar 9 start).

## Verification status
All 220 rows are marked `yes` for the date. Caveats to be aware of:
1. BLS archive pages encode dates only in file names, not visible text; I treated those as official. Scheduled-vs-actual: these are the actual release dates for past events.
2. PCE time of 08:30 ET for 2022-2024 and the 2025/2026 8:30 entries come from the standard embargo/BEA schedule; only 2022-07-29 was checked on an individual release page. For 2025-2026, BEA schedule pages show the times, including three 10:00 ET releases (2025-04-30, 2025-12-05, 2026-01-22).
3. FOMC press-conference start time (14:30 ET) is the standard time and was not verified per meeting; the Fed page confirms a press conference was held at every meeting listed.
4. 2026-02-11 NFP delay reason not stated on the fetched page.
5. The BEA archive listing was cached through Jul-2026 data; the 2026-09-30 PCE comes from the BEA schedule and PCE data page ("current release Sept 30 2026").
6. Pre-shutdown originally-scheduled dates for the delayed releases were not recorded (only actual dates).
