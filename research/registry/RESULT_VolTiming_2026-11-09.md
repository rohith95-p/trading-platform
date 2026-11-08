# Result — the breakout-timing payoff did not replicate. Signal search closed.

Pre-registered in `PREREG_VolTiming_2026-11-09.md` (`dc33864`), committed before
the run.

**Verdict: nothing cleared the gate. The volatility-timing idea is closed, and
with it the signal-search route to a funded account.**

## The finding that prompted this, and what happened to it

On 2004-2016, randomising **direction** at a 20-day Donchian breakout returned
profit factors of 1.033, 1.027, 1.042, 1.157, 1.220, 1.098 — **six of six above
1.00**, mean 1.096. A coin flip appeared to make money.

On 2016-2022, the same coin-flip arms returned:

| geometry | coin seeds | mean |
|---|---|---|
| DONCH20 6/10 | 0.76, 0.91, 1.17 | **0.945** |
| DONCH20 8/16 | 0.85, 0.72, 0.80 | **0.787** |

**It did not replicate.** The effect was not small — it was absent. The 6-of-6
was itself noise.

## All 16 arms, 2016-2022

| arm | trades | net $ | PF | win % | avg hrs |
|---|---|---|---|---|---|
| **DONCH20_S6_T10 coin seed 3** | 146 | +261.70 | **1.17** | 43.2 | 23.5 |
| DONCH20_S6_T10 long_only | 89 | −0.72 | 1.00 | 43.8 | 19.1 |
| DONCH20_S6_T10 force_long | 147 | −7.22 | 1.00 | 42.9 | 21.6 |
| DONCH20_S8_T16 force_short | 149 | −174.49 | 0.92 | 40.3 | 33.5 |
| DONCH20_S6_T10 coin seed 2 | 148 | −155.63 | 0.91 | 41.9 | 24.3 |
| DONCH20_S8_T16 force_long | 148 | −294.85 | 0.85 | 45.9 | 34.3 |
| DONCH20_S6_T10 force_short | 147 | −307.14 | 0.83 | 38.8 | 24.5 |
| DONCH20_S6_T10 as_is | 149 | −324.33 | 0.82 | 40.9 | 23.8 |
| DONCH20_S8_T16 as_is | 149 | −627.35 | 0.72 | 42.3 | 35.2 |
| DONCH20_S8_T16 short_only | 60 | −317.22 | 0.67 | 38.3 | 40.5 |
| DONCH20_S6_T10 short_only | 60 | −323.60 | 0.62 | 36.7 | 30.8 |

(Remaining coin arms interleaved; full table in `vol_timing_test_2026-11-09.json`.)

**The best of all sixteen arms is a coin flip.** `coin seed 3` at PF 1.17, the only
arm above 1.15 in the entire table, is random direction. That one line is the
clearest statement of what this whole project has been measuring.

## The two sub-ideas, both dead

**Zero-swap short bias gave nothing.** `force_short` — take every breakout, always
short, paying no overnight swap — returned **0.83 and 0.92**. Its swap-paying
mirror `force_long` returned **1.00 and 0.85**. The swap asymmetry is a broker
markup, and avoiding it does not buy an edge; the spot drift offsets it, which is
what no-arbitrage says should happen.

**Directional selection gave nothing.** `long_only` 1.00 / 0.76 and `short_only`
0.62 / 0.67, the latter on only 60 trades.

Average holds ran 19-40 hours, so roughly one to two nights — enough for swap to
matter, which is why the force_short arm was worth testing at all.

## Where I was wrong, and it matters methodologically

I pre-registered that the effect would be **"real but too small to trade,"** worth
2-3 points of win rate against a 4.3-point bar. That was too generous. It was not
real.

I over-read my own control arms. Six seeds above 1.00 looked like p = 0.016, but
the seeds within a geometry **share entry times and hold overlapping positions**,
so they are not independent draws — and the two geometries are correlated with
each other for the same reason. The honest independent count was closer to two,
not six. **The safeguard I built to catch false positives produced one of its own
the moment I read it as a finding rather than as a baseline.** That is worth more
to remember than the null result.

## Consequences, as pre-committed

1. **The volatility-timing idea is closed.** No swept thresholds, no new
   geometries, no re-cut windows, no third look.
2. **2022-2026 was not run.** The harness refused on an empty advancing list, so
   that window remains completely unspent.
3. **This project has no demonstrated path to a funded account through strategy
   search.** Stated plainly, as committed, rather than dressed as a further
   variation.

## The complete tally

| what was tested | verdict |
|---|---|
| 4 live legs, 18-year holdout, 2,556 trades | PF 0.90 |
| Those legs vs a coin flip at zero cost | PF 1.02 vs band 0.91-1.04 — identical to chance |
| 21 fresh candidates, 7 families, 3 geometries | 0 survived |
| Breakout timing, direction-independent, 16 arms | 0 survived; best arm is a coin flip |

Roughly 70 strategy variants, 18 years of minute data, four pre-registered tests.
No directional or timing edge has survived data it did not choose.

## What is actually true about this repository

The execution platform works and is worth keeping: minute-accurate backtesting
with an enforced holdout, one bar source, the broker measured at startup, a
self-repairing feed, sixteen auditable gates, pre-registration discipline and a
chance-baseline harness that has now caught three would-be false positives
(PF 1.40/1.81, NRX's 1.51, and this one).

What it does not have is a strategy. The live record is **two trades, +$112.45**,
and a zero-edge system shows a profit 62% of the time after two trades.

No real money. The demo may keep running as an infrastructure test, and the
news-calendar fix is worth deploying so the execution path is exercised, but its
P&L will not be evidence for a long time yet.
