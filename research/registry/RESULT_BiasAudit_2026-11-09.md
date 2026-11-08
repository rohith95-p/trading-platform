# Result — the engine is not pessimistic. If anything it is slightly optimistic.

Pre-registered in `PREREG_BiasAudit_2026-11-09.md` (`cb5124b`), run in the
direction that could falsify this project's negative verdict.

**Verdict: NEGATIVE VERDICT ROBUST.**

| arm | trades | net $ | PF | win % |
|---|---|---|---|---|
| BASE (as published) | 2,556 | −1,311.35 | **0.90** | 35.6 |
| **GENEROUS** (ambiguity → target) | 2,556 | −1,284.10 | **0.90** | 35.7 |
| HARSH (gapped stops fill at the gap) | 2,556 | −1,426.65 | **0.89** | 35.6 |

The bar was PF >= 1.15 on GENEROUS. It returned 0.90. The negative verdict stands
under the most favourable reading the data permits.

## Why the pessimistic bias turned out to be nothing

| | |
|---|---|
| trades flagged intrabar-ambiguous | **2 of 2,556 (0.1%)** |
| ambiguous M1 bars seen | 2 |
| ambiguous bars handed to the target in GENEROUS | 2 |

Two trades. The whole "stop-first resolution is unfair" concern was worth
**$27.25** across eighteen years. `_walk_minute`'s own docstring was right that
co-touch is rare at minute resolution — it is the *coarse* M15 engine where this
mattered, and that was fixed in October.

## And a correction to myself: the error runs the other way

| | |
|---|---|
| stops that had gapped through the level | **122** |
| loss the default assumption hides | **$115.30** |

Filling gapped stops honestly makes the result **worse** — 0.89. So the engine is
mildly **optimistic**, not pessimistic. Every published figure in this repo,
including PF 0.90, is about $115 too kind over 18 years.

Swap accounting is clean: **0** shorts charged, **0** zero-night trades charged,
total swap paid $178.36 across 18 years.

## Live reconciliation — and this is a finding of its own

October 2026, the only month the current four legs have traded for real:

| | trades | net |
|---|---|---|
| broker's ledger (live bot) | 2 | +$112.45 |
| engine's replay | **10** | +$278.10 |

The engine found **five times as many signals as the live bot executed**, and made
more money on them. Whatever else is true, **the engine is not grinding results
down** — the live bot is taking a fraction of what the strategy logic generates.

**Caveat, stated honestly:** this is not like-for-like. The engine ran with
`ULTRA_TRADE_24H=1`, the Atlas rule engine off, and no own-news filter, while the
live bot applies all three plus the trading-window rule. So part of the 10-vs-2
gap is gates the engine deliberately did not apply, not a live malfunction. What
it does establish is the direction: there is no evidence of engine pessimism, and
there is evidence the live path is far more restrictive than the backtest.

The under-execution deserves its own investigation — `gate_audit.py` exists for
exactly this — but it cannot rescue the strategies: the engine's *unrestricted*
view of 18 years is still PF 0.90.

## What this closes

The last remaining way the negative verdict could have been an artefact was
"Claude's engine is wrong." It was tested in the direction that would have
embarrassed me, with the bar fixed in advance, and:

- the pessimistic bias is **0.1% of trades, worth $27**
- the optimistic bias is **122 trades, worth $115**
- cost is charged exactly once per round trip (verified by reading, engine.py:1455)
- swap is charged only where it is owed
- the live record, where it diverges, diverges *against* the live bot, not the engine

PF 0.90 over 2,556 trades is a real measurement of a real absence of edge.
