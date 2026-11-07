# Result — the entries are coin flips, so there is nothing to tune

Pre-registered in `PREREG_SignalOrCost_2026-11-07.md`, committed in `21ff876`
before the test ran. Arms, chance baseline and the consequence of each outcome
were all fixed in advance.

**Verdict: NO SIGNAL.**

## What ran

The live four legs over 2004-07 .. 2022-08, five eras pooled, `live_parity_preset`,
`m1_policy="skip"`, 0.02 lots, 3 concurrent, Atlas off, and **`frictionless`
costs — zero spread, zero slippage, zero commission, zero swap**. Arms B, C and D
share entry timing and differ only in direction.

| arm | trades | net $ | PF | win % | avg win | avg loss |
|---|---|---|---|---|---|---|
| A real, D1 gate on | 2,561 | +257.94 | **1.02** | 38.2 | 13.0 | −7.9 |
| B real, gate off | 4,239 | +455.35 | **1.02** | 37.5 | 13.5 | −7.9 |
| C **inverted** | 4,250 | −191.35 | **0.99** | 37.1 | 13.3 | −7.9 |
| D control, seed 1 | 4,247 | −1,995.06 | **0.91** | 35.8 | 13.0 | −8.0 |
| D control, seed 2 | 4,268 | +454.63 | **1.02** | 37.7 | 13.4 | −7.9 |
| D control, seed 3 | 4,252 | +749.86 | **1.04** | 37.9 | 13.4 | −7.9 |

Chance band from the coin-flip controls: **PF 0.91 to 1.04**.
The real entries, same timing, same caps: **PF 1.02** — inside it.

Arm A's 2,561 trades against the 18-year holdout's 2,556 confirm that nothing
changed here except the cost model.

## What it means

**1. The entries carry no directional information.** The real direction (1.02)
sits in the middle of the chance band, the inverted direction (0.99) is no worse,
and one coin flip (1.04) beat the real signals outright. If there were
information, inverting it would hurt. It doesn't.

**2. At zero cost the system is exactly a random walk.** For a reward-to-risk of
13.0/7.85, geometry says a directionless entry touches its target before its stop
**37.8%** of the time. Observed frictionless win rate: **38.2%**. That is not an
approximation of an edge; it is the signature of no edge. A coin flip with these
stops produces precisely this.

**3. The whole loss is the spread.** Frictionless net is **+$258**; the same
configuration with `realistic_ecn` is **−$1,311**. The difference is **$1,569
over ~2,558 trades = $0.613 per trade** — which matches the modelled cost from
first principles (≈$0.52 spread + $0.04 slippage + $0.07 commission at 0.02
lots). The 18-year PF of 0.90 is a coin flip paying the spread, to the cent.

**4. So the "only 2.4 points short" gap cannot be tuned away.** Breakeven is not a
property of gold; it is `1/(1+RR)`, set by the stop and target *we* chose. Tighten
the target and the win rate rises — and the breakeven rises with it. For an entry
with no information the achieved and required win rates are the same number at
**every** stop/target pair, so the surface is flat at PF 1.00 and costs push the
entire sheet below it. The 2.4 points *are* the spread, and they are invariant to
tuning. This is why no sweep is run.

**5. The D1 EMA20 gate adds no information either.** PF 1.02 with it (2,561
trades) and 1.02 without (4,239). It halves the trade count and changes nothing
else.

**6. Calibration for every past number in this project.** Three coin flips on
~4,250 trades each returned PF 0.91, 1.02 and 1.04 — a spread of **0.13 PF from
chance alone, on four thousand trades**. Every historical result in this repo was
measured on a few hundred. PF 1.40 on TEST is comfortably inside the noise of a
coin flip at that sample size.

## What a candidate would have to clear

Taking the measured cost of $0.613 per trade at this geometry:

| | win rate |
|---|---|
| chance / gross breakeven | 37.8% |
| net breakeven after costs | **40.7%** |
| needed for net PF 1.15 | **44.1%** |

So a usable candidate must beat chance by about **6.4 percentage points** of win
rate. That is the bar, stated in the only units that matter. It is a large edge
for session-breakout logic on gold, and it should be assumed hard to find rather
than likely.

## Consequences, as pre-committed

1. **The tuning plan is abandoned. No stop/target/filter sweep is run on these
   legs.** A 60-cell sweep over directionless entries would return a best cell,
   that cell would look good, and it would mean nothing — it is the exact
   mechanism that produced PF 1.40 and 1.81.
2. These four legs are finished as a profit proposal. Not re-tuned, not
   re-filtered, not partially kept.
3. Any future search must carry a chance-baseline arm **from the start**.
   `scripts/validation/signal_or_cost.py` is now that tool: a seeded coin-flip
   control on identical entry timing.
4. Atlas rules are applied only after an edge clears the bar above. They cannot
   create one.

## Side findings worth keeping

Two silent failure modes in the research harness, both now documented in
`scripts/validation/signal_or_cost.py`:

- `BacktestEngine._patch_strategy_mt5` installs its clock stub by
  `s.__module__`, so a strategy subclass defined in another module leaves the real
  leg on the live MT5 clock; every session-time check then misses.
- The engine calls `s.evaluate(m15_view, m5_view)` while `BaseStrategy` documents
  `evaluate(rates)`. A one-argument override raises `TypeError` into the engine's
  `except Exception`, which logs at debug level and records no signal.

Either one reports **zero trades with no error** — the same species of failure as
the Atlas news-calendar bug: the system says "nothing happened" when it means
"I broke."
