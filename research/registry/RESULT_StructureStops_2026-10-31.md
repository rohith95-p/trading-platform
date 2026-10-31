# RESULT: structure-based stops and targets (2026-10-31)

Pre-registration: `PREREG_StructureStops_2026-10-31.md`. Script: `scripts/validation/structure_stops_study.py`.
Live 4-leg entries, M1 replay with engine costs, 0.02 lots. Best DEV+TEST variant per strategy vs live ATR stops:

| Strategy | Live: DEV+TEST / RECENT / worst DD | Best structure variant | DEV+TEST / RECENT / worst DD | Pass bar |
|---|---|---|---|---|
| Asian Range Filtered | +$645 / +$141 / $113 | swing8, target 2R | +$1,030 / +$469 / $222 | **fail**: drawdown 2.0x live (bar 1.2x) |
| Asian Breakout | +$124 / +$80 / $56 | swing8, target 3R | +$314 / −$64 / $48 | **fail**: worse on RECENT |
| London Momentum Tight | +$106 / +$341 / $226 | swing16, target 2R | +$1,133 / +$227 / $194 | **fail**: worse on RECENT |
| NY Session Reversal | +$396 / +$228 / $161 | swing8, target 2R | +$232 / +$113 / $187 | **fail**: worse everywhere |

Verdict: no strategy passes; the live ATR stops stay. Asian Range Filtered with swing stops made more money in
every window including the unseen one, but with fixed 0.02 lots its wider stops doubled the worst drawdown. A
follow-up worth pre-registering: the same swing stop with the lot size scaled so each trade risks the same dollars.
