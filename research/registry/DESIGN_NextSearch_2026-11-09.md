# Design — the next search, and what our own data can and cannot contain

Owner, 2026-11-09: design the search first; judge on 2–3 recent years if possible;
run every metric; find an edge.

This document is the design, derived from measurement rather than preference. It
is **not** a pre-registration yet — the final section states what still has to be
decided before one can be written.

## 1. The sample-size spec, derived

A judging window is only useful if the chance band is narrower than the edge
being looked for. Simulated: a system with **exactly zero** edge at reward/risk
1.63, and the profit factor it prints by luck alone:

| window at 12 trades/month | trades | PF a zero-edge system shows (5th–95th) |
|---|---|---|
| 2 years | 283 | 0.81 – **1.22** |
| 3 years | 424 | 0.85 – **1.18** |
| 4 years | 566 | 0.86 – 1.15 |
| 18 years | 2,548 | 0.93 – 1.07 |

At the current trade rate, a 2–3 year window routinely prints **PF 1.18–1.22 on
no edge at all**. That is where the 1.41 came from. So the owner's preference for
recent data is achievable only by raising the trade rate, not by shortening the
test.

**Spec: ≥ 1,000 trades in the judging window.** At 2.5 years that is
**≥ 33 trades/month**, about 1.6 per trading day.

## 2. The cost spec, derived

Cost is $0.51 per round trip at 0.02 lots and is **invariant to position size**
(every component is per-lot). What matters is cost ÷ average win:

| avg win | cost as % of win | win-rate edge needed for net PF 1.15 |
|---|---|---|
| $13 (the live legs) | 3.94% | 6.4 pts |
| $26 | 2.0% | 4.9 pts |
| $39 | 1.3% | 4.3 pts |

**Spec: average win ≥ $25**, i.e. targets around 10 × ATR(M15), not 3–5.

## 3. The concurrency constraint, which couples the two

Signal frequency and hold time are not independent once positions occupy slots:

    trades/month × avg hold (days) ≤ max_concurrent × ~21 trading days

At 33 trades/month with 3 slots, holds must average **under ~2 days**. The
measured DONCH 6/10 arms held 19–24 hours with average wins of $28 — so the spec
is feasible, but `max_concurrent` should rise to **5** (0.10 lots gross, ~$85 at
risk on $5,000 = 1.7%, inside any plausible Atlas daily limit).

**Spec: ~33 trades/month, ~10×ATR targets, holds ≤ 2 days, 5 concurrent.**

## 4. What information our data actually contains

Every one of the ~70 variants tested here predicted direction from **price
alone**. The bars carry two more fields. Measured on 113,465 M15 bars, 2022–2026:

| relationship | correlation |
|---|---|
| volume → same-bar range | **+0.823** |
| volume → **next**-bar range | **+0.695** |
| volume → \|next-bar return\| | **+0.518** |
| volume → **signed** next return | **−0.002** |
| spread → next-bar range | +0.149 |

**This is the most important measurement in the document.** Volume predicts *how
big* the next move will be, strongly and reliably. It predicts *which way*
with a correlation of **minus two thousandths**.

And that is the whole problem restated in new data: we can forecast magnitude and
we cannot forecast direction.

**Magnitude alone cannot be monetised on a spot account.** If direction is a coin
flip, knowing the move will be large scales the wins *and* the losses equally;
expectancy stays at zero minus costs. Monetising volatility without direction
needs options or a straddle, which an MT5 spot account cannot express.

What volume *can* legitimately do is improve the **cost ratio**: trade only when
the expected move is large, and $0.51 becomes 1.5% of the average win instead of
3.94%. By the table in §2 that is worth roughly **+0.07 of profit factor** —
taking 0.90 toward 0.97. Real, worth having, and **not an edge**. It is the same
arithmetic as the raw-spread account: it reduces the drag and cannot create what
is not there.

Two data traps to record now:
- **Volume scale is not comparable across eras** — median tick_volume is 14 in
  2004–2008, 779 in 2012–2016, 909 in 2020–2022, 1,452 in 2022–2026. Any absolute
  volume threshold is meaningless over 18 years. It must be a rolling percentile.
- **Spread is unusable before 2022** — all zero in 2004–2016, 0.9% populated in
  2020–2022, 89% in 2022–2026. Spread-based signals can only be tested on the
  contaminated window, so they cannot be validated.

## 5. The one hypothesis this leaves open

A correlation of −0.002 is **linear and unconditional**. It does not rule out a
*conditional* relationship: direction predictable given volume regime **and**
price structure together, an interaction a single correlation cannot see.

That is the only remaining hypothesis our own data can support, and it should be
stated with its honest prior: **low**. Seventy variants of price structure have
failed; adding a magnitude-only variable to a structure that has no directional
information is not obviously rescued by interacting them.

## 6. Trial discipline — the part that was missing all along

Per Bailey & López de Prado (2014), and the gap found today:

1. **Every variant's per-trade return series must be saved.** Without them,
   `k_eff` cannot be computed and the DSR is either far too harsh (raw N) or
   flatteringly wrong (too few series — the trap caught in `7eab239`).
2. **A trial ledger**, appended on every backtest: configuration, window, metric.
   N must be a query, not a recollection. It is currently "a few hundred, I
   think."
3. **A declared trial cap via the 1/e rule**: sample ~37% of the justifiable
   configurations at random, then take the first that beats all previous, and
   stop.
4. **Holdout windows are single-use and tracked.** 2016–2022 has now been spent
   three times; the paper's §p.6 argument says that alone makes false positives
   expected.

## 7. Windows — and the problem that we are running out of clean data

| window | state |
|---|---|
| 2004–2016 | used once (entry-search SELECT) |
| 2016–2022 | **spent three times** |
| 2022–2026 | selection set for most of this project |
| **2026-11-01 onward** | **untouched, and enforced by `HOLDOUT_FROM`** |

There is no clean recent window left. The only uncontaminated data is **data that
does not exist yet**.

So the honest structure is: search history with DSR + k_eff + a declared trial
cap to produce *at most one* candidate, then **the real verdict is forward**, on
the live demo, on bars nobody has seen. That is also the evidence the owner
actually trusts.

**Gates for a candidate to reach forward testing:** ≥1,000 trades, net PF ≥ 1.15
after `realistic_ecn`, above its own coin-flip band, and **DSR ≥ 0.95 computed on
k_eff** with one return series per trial. Atlas survivability is tested only
after that, never as part of the search.

## 8. What must be decided before this can be pre-registered

1. **Is a low-prior search worth the compute?** §4 says our data's only unused
   information is non-directional. I would not fund this search on its prior
   alone, and say so plainly.
2. **Or spend the effort on the infrastructure instead** — trial ledger, holdout
   ledger, saved variant series — so that *whatever* is tested next is tested
   honestly, and the forward window is spent well rather than quickly.
3. **Or acquire information we do not have**: real traded volume and depth,
   correlated instruments, scheduled-release data, options-implied volatility.
   A directional edge, if one is reachable at all, is most likely to come from
   outside this dataset rather than from a seventy-first cut of the same prices.
