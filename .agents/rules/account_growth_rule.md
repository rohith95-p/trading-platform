# Sizing rule

Current as of 2026-11-01. The account is the Atlas 1-Step $5,000 evaluation,
rehearsed on an Exness MT5 demo of the same size.

- **Every order is 0.02 lots**, enforced in `ExecutionHandler.send_order` through
  `FIXED_LOT_SIZE` -- one chokepoint, no dynamic sizing anywhere in the live
  path. `RiskManager.calculate_dynamic_lot_size` still exists and is not called.
- **At most 3 open positions, 0.06 lots in total**, 3 in one direction.
- **Do not change either number without an explicit instruction from the owner.**
  They are the owner's limits, not tunables. The owner declined a cut to 0.01 on
  2026-10-30: "we need profit, we are on offence".

Why 0.02 and not more: the evaluation fails at a $500 trailing drawdown. The
6-month Monte Carlo at 0.02 lots puts the chance of a $500 drawdown near 0.4%
and the chance of reaching the $150 target first at about 74%
(`research/registry/RESULT_StopRobustness_2026-11-01.md`). Doubling the lot
roughly doubles the drawdown, and the target does not move.

Any change is a proposal to the owner first, backtested on DEV and TEST, then
checked -- not chosen -- on data the study never saw.
