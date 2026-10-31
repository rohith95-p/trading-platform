# Rule: one strategy, one session

Architectural guardrails for building, changing or auditing XAUUSD strategies.

## 1. No strategy runs all day

Market behaviour differs by session, so each leg owns a window. The live
portfolio (`src/strategies/portfolio_atlas.py`):

| Leg | Entry window, IST | Family |
|---|---|---|
| AsianRangeFilteredV6 | 12:45 | range breakout, with a range-size filter |
| AsianBreakoutV6 | 12:45 | range breakout, unfiltered (rare: ~6 trades a year) |
| LondonMomentumTightV6 | 17:45 | trend continuation |
| NYSessionReversalV6 | 17:45-21:30 | sweep reversal |

Session times are checked against `bar_time % 86400`, which is **broker server
time, not UTC**. `src/core/broker_probe.py` measures the server's offset at
startup and alerts when it differs from the profile the configuration was
validated against. A new broker can shift every entry by hours, so check it
before trading.

## 2. The orchestrator pattern

- A new leg is a class in `src/strategies/`, added to `PORTFOLIO` in
  `portfolio_atlas.py`, with its magic registered in `config/ultra_magics.json`.
  `main_loop` refuses to start if a leg's magic is missing.
- A leg decides **direction only**. Stops, targets, sizing, caps, the Atlas gate
  and the kill switch all live outside it.
- A leg reads closed bars only: `rates[-1]` is the forming candle, so use
  `rates[-2]`. `tests/test_no_lookahead.py` enforces this.

## 3. Retiring a leg

Archive it to `src/strategies/archive/` together with the result that condemned
it, and record the removal in `research/DECISIONS.md`. Do not delete the file:
the next search for an edge should be able to see what has already failed.
