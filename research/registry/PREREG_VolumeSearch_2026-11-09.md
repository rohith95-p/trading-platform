# PREREG: volume-conditioned direction — the last untested information we own (2026-11-09)

**Owner's instruction, 2026-11-09:** "Run the search."

Design basis: `DESIGN_NextSearch_2026-11-09.md`. Specs there were derived from
measurement; this document freezes the candidates, the gates and the
consequences before anything runs.

## The hypothesis, and its honest prior

All ~209 trials this project has run predicted direction from **price alone**.
`tick_volume` has never been used. Measured on 113,465 M15 bars (2022–2026):

| | correlation |
|---|---|
| volume → next-bar range | **+0.695** |
| volume → \|next-bar return\| | +0.518 |
| volume → **signed** next return | **−0.002** |

Volume forecasts magnitude strongly and direction not at all. That correlation is
*linear and unconditional*, so it does not rule out direction becoming
predictable from **volume regime interacting with price structure** — which is
the only hypothesis the measurement leaves open.

**Stated prior: low.** Magnitude without direction cannot be monetised on a spot
account, and seventy cuts of price structure have already failed. I expect this
to fail and am running it because the owner asked and because the protocol is now
good enough that the answer will mean something either way.

## Candidates — 4 signals × 2 geometries = 8, frozen

All read a rolling **percentile** of volume, never an absolute level: median
`tick_volume` is 14 in 2004–2008 and 1,452 in 2022–2026, so any fixed threshold
would be meaningless across eras.

| id | signal |
|---|---|
| VOLBREAK | 40-bar structure break **with** participation (volume ≥ 80th pct) |
| VOLDIVERG | 40-bar break **without** participation (≤ 20th pct) — faded |
| VOLSPIKE | volume ≥ 95th pct and the close pinned in the bottom/top 20% of the bar |
| VWAPREV | close ≥ 1.5σ from the 96-bar **volume-weighted** average, traded back |

VOLBREAK and VOLDIVERG are deliberate inverses on identical structure: if either
has an edge the other should lose, and if both sit at chance then the volume
regime carries no directional information at all.

Geometries, per the cost spec (average win ≥ $25 so $0.51 is ~2% of a winner
rather than 3.94%): **6/10** and **8/14** ATR. Thresholds (500-bar lookback, 40
bars, 0.80/0.20/0.95, 20%, 96 bars, 1.5σ) are **fixed and not swept** — the 1/e
trial cap matters more than coverage.

Engine: `live_parity_preset`, `m1_policy="skip"`, `realistic_ecn`, 0.02 lots,
**max_concurrent 5**, D1 gate off, Atlas engine off. Each candidate runs solo.

**Firing rates measured before the run** (per month, pre-concurrency):

| | 2004–2008 | 2020–2022 |
|---|---|---|
| VOLBREAK | 48.0 | 69.5 |
| VOLSPIKE | 42.2 | 51.2 |
| VWAPREV | 457.2 | 615.1 |
| **VOLDIVERG** | **3.6** | **6.3** |

Recorded now: **VOLDIVERG is marginal on power** (~500 trades over FIT) and may
land as inconclusive rather than refuted. **VWAPREV is saturated** — it signals
on ~20% of all candles, so its trade count will be set by the concurrency cap
rather than by the signal, making it closer to "always in the market" than a
selective rule. Neither observation changes the gates.

## Windows — and a disclosure

| stage | window | state |
|---|---|---|
| FIT | 2004-01 .. 2016-01 | **already spent once** (entry-search SELECT) |
| CHECK | 2016-01 .. 2022-08 | **already spent twice** (CONFIRM, vol-timing TEST) |

**There is no clean historical window left.** Both are being **re-spent**, logged
through `src/research/ledger.spend_window` with `allow_respend=True` and the
owner's instruction as the recorded reason. The ledger refuses silently-repeated
holdouts, so this reuse is a deliberate act with a name on it.

What that costs, stated plainly: **a pass here is not an out-of-sample verdict.**
Bailey & López de Prado (p.6) — applying holdout repeatedly makes false positives
expected. So this search's job is **generation, not validation**: it may produce
at most one candidate, whose actual test is forward, on the live demo, on bars
nobody has seen. `HOLDOUT_FROM = 2026-11-01` keeps that window sealed.

## Gates

| stage | bar |
|---|---|
| FIT | ≥ 500 trades, net PF ≥ 1.15 after costs, **and** above the max of its own 3-seed coin-flip band |
| advance | **at most 2** of 8, by FIT PF |
| CHECK | ≥ 300 trades, PF ≥ 1.15, and above its own control band |
| forward | **one** survivor goes to the live demo. No historical result is treated as the verdict |

**For the first time, `k_eff` will be computable.** The trial ledger now saves
every variant's per-trade series, so the deflated Sharpe is reported twice: at
raw N (209 prior trials + these 8) and at the correlation-aware effective N.
A candidate is only taken seriously at **DSR ≥ 0.95 on k_eff**.

## Pre-committed consequences

1. **Nothing clears FIT → the search is closed and reported as closed.** No
   swept thresholds, no third geometry, no extra signal, no re-cut windows.
2. Clears FIT but fails CHECK → reported as a failed candidate, not re-tuned.
3. Clears both → still not a real-money proposal. It goes to the demo for forward
   testing, and Atlas survivability is tested only after that.
4. If VOLBREAK and VOLDIVERG **both** land inside their chance bands, that is
   recorded as the direct finding that volume regime carries no directional
   information — which closes the question this project has been circling for two
   weeks.

Run: `python -I scripts/validation/volume_search.py --stage fit`
