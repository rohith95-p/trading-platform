# Working in this repository

Ultra Core trades XAUUSD on one account, with real money next. Nothing here is a
sandbox: a change to `src/core/` or `src/strategies/` changes what gets sent to a
broker. Read this before touching either.

## What is live right now

Four legs, in `src/strategies/portfolio_atlas.py`, 0.02 lots each, the Atlas rule
engine in front of every order:

| Leg | Magic | Stop / target (x ATR) | Entry, IST |
|---|---|---|---|
| AsianRangeFilteredV6 | 7320 | 2.5 / 3.5 | 12:45 |
| AsianBreakoutV6 | 7311 | 3.0 / 5.0 | 12:45 |
| LondonMomentumTightV6 | 7324 | 2.0 / 4.0 | 17:45 |
| NYSessionReversalV6 | 7313 | 2.5 / 4.5 | 17:45-21:30 |

The D1 EMA20 direction gate is ON for all four. Trailing and pyramiding are OFF
and their code has been removed -- both measured net-negative. At most 3
positions, 0.06 lots in total.

## The order of work

1. **A question becomes a pre-registration.** Write
   `research/registry/PREREG_<Name>_<date>.md` saying what will be tested and
   what would count as a pass, and **commit it before running anything**.
   `scripts/validation/prereg_check.py` checks this, and CI fails without it.
2. **The test runs through the real engine:**
   `src.backtesting.engine.BacktestEngine`, on bars from
   `src.backtesting.master.load_master()`. No scratch simulators.
3. **The result gets written down**, pass or fail, in `RESULT_<Name>_<date>.md`.
4. **Only then** may live code change, and every live change gets a line in
   `research/DECISIONS.md`.

## Hard rules

- **Never change a live number without being asked.** Lot size, stops, targets,
  session times, the direction gate, the Atlas limits: propose it, show the
  evidence, wait for the owner's answer.
- **Never trade the holdout.** Bars from 2026-11-01 onward judge a decision and
  never choose one. `load_master()` cuts them off unless a caller passes
  `allow_holdout=True`.
- **Never resolve an exit on a 15-minute candle.** `m1_policy` defaults to
  `"require"`; `"coarse"` exists only to reproduce old runs, and its numbers are
  not comparable to anything.
- **Never place or force a trade by hand**, and never print secrets from
  `.env.local`.

## Where things are

| Need | Go to |
|---|---|
| the live loop | `src/core/main_loop.py` |
| Atlas state and limits | `src/core/atlas_bridge.py`, `src/atlas/rules.py` |
| what the broker actually is | `src/core/broker_probe.py` |
| status, heartbeat, alerts | `src/core/live_status.py`, `src/core/trade_alerts.py` |
| bars, and where they came from | `src/backtesting/master.py` |
| data coverage and quality | `scripts/validation/data_check.py` |
| the headline backtest numbers | `scripts/validation/audit_stats.py` |
| every live change ever made | `research/DECISIONS.md` |
