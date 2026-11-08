# Result — volume carries no directional edge. Search closed.

Pre-registered in `PREREG_VolumeSearch_2026-11-09.md` (`9477ada`), with the prior
recorded before the run: *low, I expect this to fail.*

**Verdict: 0 of 8 cleared the FIT gate. The search is closed.**

## FIT, 2004-2016 (re-spent, logged)

| candidate | trades | net $ | PF | win % | avg win | avg loss |
|---|---|---|---|---|---|---|
| VOLBREAK_S6_T10 | 2,615 | +656.03 | **1.02** | 42.7 | 25.45 | −18.51 |
| VOLBREAK_S8_T14 | 2,122 | −640.81 | 0.98 | 44.0 | 28.40 | −22.86 |
| VOLSPIKE_S6_T10 | 2,087 | −2,732.91 | 0.89 | 40.4 | 25.72 | −19.62 |
| VWAPREV_S8_T14 | 1,497 | −2,562.47 | 0.87 | 38.5 | 29.80 | −21.42 |
| VOLDIVERG_S6_T10 | 629 | −934.06 | 0.85 | 35.9 | 23.10 | −15.27 |
| VOLSPIKE_S8_T14 | 1,434 | −2,836.82 | 0.84 | 42.7 | 23.96 | −21.29 |
| VWAPREV_S6_T10 | 1,841 | −4,037.17 | 0.79 | 35.7 | 22.92 | −16.13 |
| VOLDIVERG_S8_T14 | 623 | −1,848.48 | 0.77 | 35.2 | 27.43 | −19.45 |

Gate: ≥500 trades, PF ≥1.15, above its own coin-flip band. **Nothing reached
PF 1.15**, so the control arms were never run — a precision worth stating: these
candidates failed the *profit-factor* gate, not the chance test. The chance test
was never needed.

Best of eight is **1.02 on 2,615 trades**. A zero-edge system at ~2,550 trades
produces PF 0.93–1.07 by luck (measured, `RESULT_MetricSuite`). 1.02 is the
middle of that band.

## The design specs were met. That is the useful part.

This search was built to a spec derived in `DESIGN_NextSearch_2026-11-09.md`, and
the spec **worked**:

| spec | target | delivered |
|---|---|---|
| trades in the window | ≥500 | 623–2,615 |
| average win | ≥$25 | $23–30 |
| cost as share of a win | ~2% | **~2%** (vs 3.94% for the live legs) |

So the cost structure really was improved roughly two-fold, exactly as the map
predicted — and the arithmetic's prediction was right to the decimal. The map
said a better cost ratio is worth about **+0.07 to +0.12 of profit factor**. The
live legs sit at 0.90; the best candidate here, with double the average win,
came in at **1.02**.

**That is +0.12, precisely as forecast — and it is still not an edge.** It is the
clearest possible demonstration that cost was never the binding constraint.
Fixing the cost ratio delivers exactly what the arithmetic promises, and what the
arithmetic promises is not enough, because there is no directional edge to
leverage.

## The pre-committed finding, with one correction to my own framing

Both volume regimes were traded in the direction folk wisdom prescribes, and both
fail:

- **high volume + follow the break** (VOLBREAK): 1.02 and 0.98 — chance
- **low volume + fade the break** (VOLDIVERG): 0.85 and 0.77 — worse than chance

**Correction to the pre-registration.** It called VOLBREAK and VOLDIVERG "exact
inverses on identical structure," so that "if either has an edge the other must
lose." That was imprecise: they take *different volume regimes* (≥80th vs ≤20th
percentile) on the same price structure, not the same trades inverted. The strict
complementarity I claimed does not hold, and the result should not be read as
though it did.

What the result does establish, which is enough: **neither volume regime yields a
directional edge in either prescribed direction.** Combined with the measured
correlations — volume → next-bar range **+0.695**, volume → signed next return
**−0.002** — the conclusion is that volume forecasts magnitude and not direction,
and that the interaction hypothesis does not rescue it.

## First working effective-trial count

| | |
|---|---|
| k_raw | 24 |
| **k_eff** | **20.38** |
| reduction | 15.1% |

The trial ledger saved every variant's series, so `k_eff` computed for the first
time in this project's history. The 24 are window-level trials (8 candidates × 3
windows), which is not quite the right unit for a DSR on a pooled candidate —
noted as a refinement for next time — but the machinery works, and the answer is
that these trials are **largely independent**: a 15% reduction, not the 94% that
the broken version reported before `7eab239` fixed it.

That matters for the owner's correlation objection. The honest reduction here is
small. There is no reason to expect the original 48-strategy screen to collapse
to an effective 2, which is what the PF 1.41 would need.

## Consequences, as pre-committed

1. **The search is closed.** No swept thresholds, no third geometry, no extra
   signal, no re-cut windows. CHECK on 2016-2022 was not run, because nothing
   advanced — the harness refuses on an empty advancing list.
2. Nothing goes forward to the demo. There is no candidate.
3. The honest trial count rises to **at least 217** (209 backfilled + 8 here),
   all recorded.

## Where this leaves the project

The data has now been characterised rather than merely searched:

- price structure, ~209 trials across 18 years: **no directional edge**
- volume, 8 trials, the only untouched field: **magnitude yes, direction no**
- cost reduction, measured twice: worth **+0.07 to +0.12 PF**, never an edge
- the engine itself, audited in the direction that could falsify all of the
  above: **not pessimistic; slightly optimistic**

A directional edge, if one is reachable, requires information this dataset does
not contain — real traded volume and depth, correlated instruments, scheduled
releases, or options-implied volatility. That is a different project, and it
should not begin without the protocol that now exists here.
