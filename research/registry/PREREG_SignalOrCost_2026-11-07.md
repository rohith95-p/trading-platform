# PREREG: is there any signal to tune, or are these entries coin flips? (2026-11-07)

**Owner's question, 2026-11-07:** "why don't we tune the strategies in a way that
it should work in all conditions? ... It needs 38% and we got 35. It was just
falling by 3%."

That is a fair question and it has a precise answer, but only after one thing is
settled first.

## Why this test comes before any tuning

Tuning changes the **exit** (stop multiple, target multiple) and the **filter**
(when a signal is allowed through). Neither can create directional information
that the **entry** does not have. If the four legs' entries are coin flips, then
every stop/target pair loses by roughly the cost of trading, the surface is flat
and below 1.00 everywhere, and whichever cell happens to look best on the fitting
data is noise — which is exactly how the current portfolio was built.

So: is the 2.4-point gap between the 35.6% delivered and the 38.0% needed a
*costs* problem (fixable by tuning) or a *no-information* problem (not fixable by
tuning at all)?

The clean way to ask is to delete costs and compare against chance.

## Arms

All on **2004-07-01 .. 2022-08-01**, the same five eras as
`PREREG_EighteenYearHoldout_2026-11-07.md`, pooled; `BacktestEngine` with
`live_parity_preset`, `m1_policy="skip"`, 0.02 lots, 3 concurrent, 3 per
direction, Atlas rule engine off, and **`frictionless` costs — zero spread, zero
slippage, zero commission, zero swap**.

| arm | entries | direction | D1 gate |
|---|---|---|---|
| A | the live four legs | as emitted | **on** (as it trades) |
| B | the live four legs | as emitted | off |
| C | the live four legs | **every signal inverted** | off |
| D | the live four legs | **seeded coin flip**, seeds 1, 2, 3 | off |

B, C and D share the same entry *timing* and differ only in direction, so they
isolate directional information. A is included for continuity with the 18-year
result. Arm D is the chance baseline: three seeds give a band, not a point.

Reported per arm: trades, net, profit factor, win rate, average win, average
loss. Trade counts are reported because the concurrency caps mean arms can
occupy position slots differently, so the entry schedules are near-identical but
not bit-identical — a limitation stated here, before the run.

**Frictionless is a diagnostic, not a tradeable result.** No arm here is a
proposal. Nobody trades at zero spread.

## Interpretation, fixed now

The signal test is **B against the D band** — same entries, only direction
differs.

1. **Signal exists:** B's PF >= 1.10 **and** B above all three D arms. The
   entries carry directional information and costs are the binding constraint.
   Tuning stops, targets and filters is then a real lever and worth doing
   properly.
2. **No signal:** B's PF falls inside the band spanned by the D arms. The entries
   are coin flips. No stop, target or filter tuning on any data, in any amount,
   can manufacture an edge, because there is no information to extract.
3. **Anti-signal:** C exceeds B by >= 0.10 PF. Direction carries inverted
   information, which is itself a finding.

## Pre-committed consequences

- **Outcome 2 means the tuning plan is abandoned, and no sweep is run on it.**
  Running a 60-cell stop/target sweep over signals with no information is how a
  false positive is manufactured; it would produce a best cell, that cell would
  look good, and it would mean nothing. The only honest path from outcome 2 is a
  search for different entry logic.
- **Outcome 1** means a stop/target/filter sweep gets its own pre-registration,
  fitted **only** on 2004-2022 and judged **only** on 2022-2026, with this
  limitation stated up front: 2022-2026 has already been used once to select
  these four legs, so it is a weakened holdout, not a clean one.
- Either way, Atlas constraints are applied **after** an edge is demonstrated,
  never as part of the tuning. Atlas's daily-loss and drawdown limits only ever
  make a system harder to survive; they cannot create an edge and they are not a
  tuning knob.

## The trap this test is built to avoid

"Tune it so it works in all conditions" is only meaningful if the tuning data and
the judging data are different. Tuning on 2004-2022 until all five eras look good
and then reporting those five eras is the same mistake that produced PF 1.40 and
1.81 — a number that describes a search, not a strategy. The fitting set and the
judging set are therefore named in advance, above, and the judging set is not
touched until the fitting is frozen.

Run: `python -I scripts/validation/signal_or_cost.py`
