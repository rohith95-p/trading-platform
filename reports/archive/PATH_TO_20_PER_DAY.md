# Path to $20/day — an honest growth model

**Date:** 2026-09-02
**Starting point:** the validated `portfolio_v4` result — PF 1.512, net **$703** over
~100 calendar days (69 trading days) on a **$105.74** start, fixed **0.01 lots**,
min balance **$106** (never dropped below start), max drawdown **35.0%**,
6%-daily-breaker tripped **11/69** trading days. End balance ≈ **$808.74**.
Source: `src/strategies/portfolio_v4.py`, `docs/research/PHASE3_FULL_SWEEP_RESULTS.md`.

**Method note, stated up front:** this report tried to rerun the engine at several
fixed lot sizes to get a fresh trade-by-trade sequence (`scripts/growth_path_sweep2.py`).
One single 100-day leg (`squeeze_ASIA`, 0.01 lots) took **723 seconds** of wall
time — a full 3-lot-size × 4-leg sweep would have run 2+ hours, outside this
session's budget, so it was aborted after confirming feasibility on one leg
(56 trades, consistent with the ~49 documented for this config). Instead this
report reasons from **(a)** the already-validated aggregate portfolio_v4 numbers
above, which are real backtest output, not invented, and **(b)** the engine's own
P&L/margin/commission formulas (read directly from `src/backtesting/engine.py`
and `src/backtesting/costs.py`), which make the lot-size scaling relationship
*provable algebraically*, not just empirically plausible. Where this matters,
it's flagged explicitly below.

---

## 1. Does $/day grow on its own at fixed 0.01 lots? — No, and this matters

`EngineConfig.sizing_mode="fixed"` means every trade risks the exact same
number of ounces regardless of balance. Three formulas confirm the dollar P&L
mechanics are **linear in lot size, with no dependency on balance**:

- Gross P&L: `(exit_price − entry_price) × direction × value_per_price_unit_per_lot × lots` — linear in `lots`, and `entry/exit_price` come from ATR-based stop/target distances that depend on market volatility, not account size.
- Commission: `commission_per_lot_roundtrip × lots` (`costs.py:86`) — linear in `lots`.
- Swap: `pts × point × value_per_price_unit_per_lot × lots × nights` (`costs.py:130`) — linear in `lots`.
- Margin: `contract_size × price × lots / leverage` (`engine.py:306`) — linear in `lots`.

None of these terms contain `balance`. So **at a fixed lot size, the expected
$/day does not grow as the account grows** — the edge is a property of the
market (ATR-scaled stop distances) and the entry rules, not of how much money
sits in the account. This directly contradicts the intuitive reading of "the
account grew $105.74 → $808 over the test, so it must be compounding": it
isn't compounding. It's **arithmetic accumulation of a roughly flat daily
edge**. $703 over 100 days looks like ~7.6x growth only because the *starting*
balance is tiny relative to the *absolute* dollar edge — the same $703 would
be a 0.7% move on a $100k account and would not read as "explosive growth" at
all.

**The one balance-dependent mechanism that does exist**: the 6% daily breaker
is `balance × 0.06` (`engine.py:820`) — a bigger balance means a bigger dollar
cushion before the breaker trips, so breach frequency should mildly *fall*
as the account grows even with $/day held flat. This is a second-order
effect; it does not change the core finding that fixed-lot trading is
linear-growth, not compound-growth.

**Consequence:** the only way $/day rises meaningfully is a **deliberate lot
step-up policy** — which is exactly what sections 2–4 model.

---

## 2. The lot-size scaling relationship (validated formulas, not guesses)

Because every $ term above is linear in `lots` and none depend on `balance`,
for a lot multiplier `m = lots / 0.01`:

| Quantity | Scaling |
|---|---|
| $/day (expected) | `$7.03/day × m` (calendar-day average) or `$10.19/day × m` (trading-day average) |
| Max drawdown, in % | **unchanged (~35%)** — % DD is peak-to-trough on balance, dimensionless, invariant to lot size *as long as margin doesn't bind* |
| Daily breach rate, in % of days | **unchanged (~15.9%, 11/69)** — the breaker compares `daily_pl` to `6% × balance`; both scale by `m` together, so the ratio is invariant *as long as margin doesn't bind* |
| Max drawdown, in $ | scales linearly with `m` (bigger balance → bigger $ swings at the same 35%) |
| Margin per position | `lots × $2,214` at $4,428 gold / 200:1 leverage (0.01 lot → $22.14) |

The margin-binding caveat is the one place this breaks down — see §4.

---

## 3. Three lot step-up policies, modeled to a $20/day threshold

All three assume the $7.03/day (calendar) base rate holds at every tier — the
single biggest assumption in this whole report, revisited honestly in §5.
Days-to-next-milestone = `Δbalance / current_rate`.

### Policy A — "Double lot size every time balance doubles"

Thresholds are powers of two from the $105.74 start: $105.74→$211.48→$422.96→
$845.92→...

| Balance crossed | Lots | $/day (calendar) | Days in this stage | Cumulative days |
|---:|---:|---:|---:|---:|
| $105.74 | 0.01 | $7.03 | 15.0 | 0 |
| $211.48 | 0.02 | $14.06 | 15.0 | 15.0 |
| $422.96 | 0.04 | **$28.12** | 15.0 | **30.1** |
| $845.92 | 0.08 | $56.24 | 15.0 | 45.1 |

**$20/day is crossed inside the 3rd stage (0.04 lots), at ≈ day 30** — because
threshold and rate both double each stage, days-per-doubling is a *constant*
`105.74 / 7.03 ≈ 15.0 days`. That constancy is itself a red flag: it means
this policy is mathematically identical to **daily compounding at a fixed
~4.6%/day rate** — the same shape of exponential curve the user explicitly
asked to avoid ("not compounding risk percentage"), just re-derived through
lot-doubling instead of %-risk sizing.

Margin check: margin fraction = `22.14 × 2^k / (105.74 × 2^k) = 20.9%` at
**every** stage (constant, by construction, single position) — Policy A does
not create new margin risk beyond what already exists at $105.74.

### Policy B — Fixed dollar milestones (in the spirit of `.agents/rules/account_growth_rule.md`, which itself only specifies the first step to $200)

| Balance milestone | Lots | Margin fraction (1 pos) | $/day (calendar) | Days in stage | Cumulative days |
|---:|---:|---:|---:|---:|---:|
| $105.74 | 0.01 | 20.9% | $7.03 | 13.4 | 0 |
| $200 | 0.02 | 22.1% | $14.06 | 14.2 | 13.4 |
| $400 | 0.03 | 16.6% | **$21.09** | — | **27.6** |
| $800 | 0.05 | 13.8% | $35.15 | — | — |
| $1,600 | 0.08 | 11.1% | $56.24 | — | — |
| $3,200 | 0.15 | 10.4% | $105.45 | — | — |

**$20/day is crossed at the $400 milestone (0.03 lots), at ≈ day 28** — about
the same timeframe as Policy A, because both need roughly the same ~3x
multiplier and reach it at a similar balance. Policy B's margin fraction
*falls* over time (20.9% → 10.4%) rather than staying flat — more headroom
for concurrent positions as the account grows, the safer of the two discrete
policies.

### Policy C — Constant margin-fraction (~20% of balance always deployed)

`lots = balance × 0.20 / 2214`, recalculated continuously. Because this makes
`lots` track `balance` proportionally (not in discrete jumps), it collapses
to **exactly the exponential-growth differential equation** `dB/dt = k·B`
with `k = 7.03/105.74 = 0.0665/day` (≈6.65%/day compounding):

```
B(t) = 105.74 × e^(0.0665 t)
$20/day needs B ≈ $300.83  →  t = ln(300.83/105.74) / 0.0665 ≈ 15.7 days
```

**This reaches $20/day fastest (~16 days) — and that is the problem with it.**
Recalculated continuously, "constant margin fraction" is not actually a
different policy from percentage-risk sizing — it's the same math with a
margin constraint standing in for a risk-percent constraint. This is exactly
the `sizing_mode="live"` behavior the user has repeatedly rejected in favor
of fixed lots. **Recalculated only weekly or at discrete balance gates**, it
behaves like a smoother version of Policy B and lands in the same ~4-week
range. The continuous form is included here specifically as a warning case,
not a recommendation.

| Policy | Recalc cadence | Nominal days to $20/day | Character |
|---|---|---:|---|
| A. Double-on-double | discrete, ~every 15 days | ~30 | true step function, margin-flat |
| B. Fixed milestones | discrete, per milestone | ~28 | true step function, margin-improving |
| C. Constant margin % | continuous | ~16 | **reconstructs %-risk compounding — avoid at this cadence** |
| C, weekly-only variant | discrete, weekly | ~25-30 | acceptable, behaves like B |

---

## 4. Where the model breaks: margin, drawdown-in-dollars, and streak risk

**Margin.** At the balances and lot sizes in the tables above, a *single*
position's margin fraction stays in the 10-22% range for all three policies —
comfortable. The real constraint is **concurrency**: portfolio_v4 can open
up to 3 positions at once in the live engine's defaults, and two of its four
legs (`fvg_NY_tight`, `rangerejection_NY_tight`) share the same NY session
window, so they can be concurrent. At a 20% single-position margin fraction,
3 concurrent positions = ~60% of balance locked, 4 = ~84% — before any
floating loss is counted. **This is the one place the "%, not $" invariance
in §2 can fail**: if a step-up pushes the per-position margin fraction up
right as multiple legs fire together, `_margin_allows()` starts rejecting
entries the backtest never had to reject at 0.01 lots, silently cutting the
realized $/day below the linear projection — a failure mode the 100-day
validation window, run at a single fixed 0.01 lots throughout, never tested.
No lot tier modeled above crosses that line for a single position, but it has
not been checked for the concurrent case and should be, live, before trusting
the higher tiers.

**Drawdown in dollars.** The 35% max DD is validated as a %, and by the
argument in §2 it should hold in % terms at any lot tier absent margin
binding. In dollars it does **not** stay small:

| Tier | Balance at tier | 35% DD in $ |
|---|---:|---:|
| 0.01 lots (validated) | $105.74 | $37 |
| 0.03 lots (Policy B, $20/day crossed) | $400 | $140 |
| 0.08 lots (Policy A, $845.92) | $846 | $296 |
| 0.15 lots (Policy B, $3,200) | $3,200 | $1,120 |

Same risk in relative terms, real money in absolute terms — the account
would need to sit through a $140–$1,120 pullback exactly as calmly as it sat
through the original $37 one, at each successive stage, for the % invariance
to actually hold in practice.

**Streak / sequencing risk (not visible in an averaged $/day figure).**
Every table above assumes the $7.03/day base rate is realized smoothly. The
underlying data says otherwise: 11 of 69 trading days already tripped the 6%
breaker at 0.01 lots. Nothing in the step-up policies prevents a losing
streak from landing **immediately after** a lot-size increase — the exact
moment the account is carrying the most risk per trade it has ever carried,
on a strategy validated over a single ~100-day window with no holdout. A
losing streak that would have cost $20 at 0.01 lots costs $60-80 at 0.03-0.04
lots; several such days in a row is how an account that "should" be
compounding toward $20/day instead gets cut in half.

---

## 5. The honest answer

**Arithmetically**, using only the validated $7.03/day base edge and a
disciplined step-up policy (A or B), the account's *nominal* $/day crosses
$20 in **roughly 4 weeks** (28-30 days), once balance reaches ~$400-450 and
lot size reaches ~0.03-0.04.

**That number should not be operated on.** Three independent reasons, none
of them hand-waved:

1. **No holdout.** The entire $7.03/day figure comes from one ~100-day
   window (`2026-05-21` → `2026-08-29`). Every lot-tier projection above
   compounds that single-sample estimate forward in time *and* up in size —
   an extrapolation on top of an extrapolation.
2. **The base edge is already implausible by external benchmarks.**
   Per ledger HYP-039, ~6.6%/day at $105 balance is already 17-24x above the
   best documented sustained real-world day-trading performance (Barber/Odean
   Taiwan study, elite top 0.1-0.5% of day traders: 0.28-0.38%/day). Trusting
   it to hold *unchanged* as position size quadruples is asking an
   already-extraordinary claim to keep being true at larger stakes, where
   execution slippage and market impact — not modeled at all in this
   backtest — bite harder, not softer.
3. **Nothing has been live-tested above 0.01 lots.** All three policies
   assume the backtest edge transfers to real fills at 2-4x the position
   size with zero degradation. That assumption is untested by anything in
   this repository.

**A realistic, defensible timeline** treats each step-up as a hypothesis to
be confirmed live, not a lookup-table entry:

- Trade portfolio_v4 live at 0.01 lots for long enough to get a genuine
  out-of-sample read on whether the backtest edge shows up in real fills
  (weeks, not days — the validated window itself is ~100 days).
- Step up only after that confirmation, one broker-lot-step (0.01) at a
  time, not by 2-4x at once as the tables above do for speed of arithmetic.
- Expect each step to need its own confirmation period before the next.

Under that discipline, a **realistic timeline to a trustworthy $20/day
natural run-rate is 3-6+ months**, not 4 weeks — and it is contingent on live
trading actually reproducing a meaningful fraction of the backtest edge at
all, which is not yet established. If live performance comes in at, say,
half the backtest rate (a plausible haircut given HYP-039's benchmark gap),
the same arithmetic pushes the nominal-crossing point out to 8-12 weeks and
the trustworthy timeline correspondingly further.

**Bottom line:** the fast number (~1 month) is real arithmetic, not a lie —
but it is arithmetic performed on an assumption (edge holds unchanged at
3-4x size, live, forever) that nothing in this research has tested. The
honest timeline is **months**, gated by live confirmation at each step, not
weeks gated by a spreadsheet formula.

---

## 6. Biggest risk, stated plainly

Stepping lot size up to chase $/day makes the account's drawdowns bigger in
dollars at the *same* relative risk — that's expected and, per §2, roughly
safe in % terms. The risk that isn't automatically safe is **margin
concurrency**: this portfolio can fire multiple legs at once (two legs share
the NY session), and margin usage per position (10-22% across the modeled
tiers) multiplies with concurrency in a way the 100-day validation — run at
a single fixed lot size the whole time — never had to absorb. Combined with
zero holdout validation and an edge that's already 17-24x above the best
documented real-world benchmark, the honest framing is: **the fast
arithmetic path to $20/day is real math on an unproven assumption, and the
account should be sized up only as fast as live results actually confirm
the edge, not as fast as the formula allows.**
