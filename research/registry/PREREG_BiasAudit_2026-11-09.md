# PREREG: is the engine wrong in MY favour or against me? (2026-11-09)

**Owner's instruction, 2026-11-09:** run the forward/look-ahead bias audit.

Every negative verdict I have given this project rests on one assumption: that
`src/backtesting/engine.py` is right. Every validation in this repo was built to
catch **optimism** — coarse-candle inflation, selection bias, in-sample
reporting. **Not one was built to catch pessimism.** If the engine makes results
look worse than reality, then PF 0.90 is an artefact and I have spent two days
talking the owner out of a working system.

This audit is therefore run in the direction that can **falsify my own
conclusion**.

## Two real biases found by reading the code, pointing opposite ways

**1. Intrabar ambiguity is resolved stop-first — pessimistic.**
`_walk_minute` (engine.py:1110-1140): when one M1 bar touches both stop and
target, the stop is taken and the trade flagged `intrabar_ambiguous`. The true
tick order is unknown. Every such trade is booked as a loss that might have been
a win.

**2. A stop that gaps through still fills exactly at the stop — optimistic.**
`_walk_minute` returns `pos.sl - slip` (long) / `pos.sl + slip` (short) however
far the bar's low or high ran past the level. A real market stop that gaps fills
at the gap, not at the level. Losses are therefore understated.

Already verified by reading, and **not** a bias: cost is charged correctly.
A buy fills at ask (engine.py:1455) and exits on raw bid; a sell fills at bid and
exits on ask-converted highs and lows. That is **exactly one spread per round
trip**, not two. Commission is per round trip. Slippage is adverse on entry and
on stop exits, none on limit targets.

## What runs

The live four legs on the full out-of-sample record, 2004-07..2022-08, five eras
pooled — identical to `RESULT_EighteenYearHoldout_2026-11-07.md` in every respect
except the one knob being moved:

| arm | ambiguity | gapped stops | what it bounds |
|---|---|---|---|
| **BASE** | stop-first | fill at stop | reproduces the published PF 0.90 |
| **GENEROUS** | **target-first** | fill at stop | the most favourable reading the data permits |
| **HARSH** | stop-first | **fill at the gap** | the most unfavourable |

Two new `EngineConfig` fields, both defaulting to current behaviour so nothing
existing changes: `ambiguous_resolution` (`"sl_first"` default, `"tp_first"`) and
`gap_fill_stops` (`False` default). Neither is a live-parity flag.

Also reported: the count of ambiguous bars and of gapped stops, so the size of
each bias is visible rather than argued.

## The bar, set now

> **If the GENEROUS arm reaches PF >= 1.15, the engine was the problem.** My
> negative conclusion would be wrong, I would say so plainly and without
> qualification, and the four legs would go back on the table.
>
> **If GENEROUS reaches 1.00-1.15**, the engine's pessimism is material but not
> sufficient: the legs are not profitable but my stated margin was overstated,
> and I would correct the record.
>
> **If GENEROUS stays below 1.00**, the negative verdict is robust to the most
> favourable assumption the data allows, and the ambiguity bias is not the
> explanation for anything.

## Two further checks, same run

**Live reconciliation.** The only two real fills the current portfolio has ever
produced (2026-10-30, magic 7320 +$53.33 and magic 7324 +$59.12, from the broker's
own ledger) are replayed through the engine. Reported: engine entry price, exit
price and net against the broker's. A systematic shortfall against real fills is
direct evidence of pessimism; this is a sample of two and is read as a sanity
check, not as proof.

**Swap nights.** Nights charged are checked against calendar nights held, to
confirm the $1.031/night long figure is not being applied to intraday trades.

## Honest prior

I expect GENEROUS to land **below 1.00** and the ambiguity count to be small,
because `_walk_minute`'s own docstring says co-touch is rare at M1 resolution
("at M15 it was routine"), and because the two biases found point in opposite
directions and should partly cancel.

But I have been wrong twice this week in the direction of being too generous to
an idea, and I was wrong about position size. So the bar above is written before
the run, and a GENEROUS result at or above 1.15 retires the negative verdict
whatever I expect.

Run: `python -I scripts/validation/bias_audit.py`
