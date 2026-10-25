# Phase 2 — Session Microstructure Research (2026-09-01)

Deep statistical characterisation of XAUUSDm by IST trading session, asking one
question: **does any session have a distinct microstructure that a specialised
strategy could exploit at 0.01 lot?**

**Headline verdict: no. Five session-localised anomalies were found and four of
them were destroyed by adversarial testing. The fifth (a London-afternoon
reversal) is statistically real but its gross magnitude is ~$0.20 per trade
against a $0.28 round-trip cost — a genuine inefficiency that is smaller than
the spread. All six sessions are efficient at the resolution a $100 account can
trade.**

Two *incidental* findings are more valuable to the mission than anything in the
edge search, and are in §8: ATR14 on M15 leaks across session boundaries badly
enough to mis-size every session-specific stop, and the spread is completely
flat across sessions so the cheapest session is the *loudest* one, not the
quietest.

Scripts: `scripts/phase2_session_microstructure.py`,
`scripts/phase2_edge_probes.py`. Raw output: `reports/session_microstructure.json`.

---

## 1. Data, method, and what was done to avoid fooling ourselves

**Source.** `research/data/XAUUSDm_M15.npy` — 100,000 M15 bars,
2022-06-07 11:15 → 2026-08-31 15:30. M15 is the only timeframe with multi-year
coverage (Phase 0: M1 starts 2026-05-20, M5 starts 2025-04-02), so all
multi-year microstructure work is necessarily M15-resolution.

**Timestamp timezone — verified, not assumed.** The 75-minute daily gold break
lands at 21:00 UTC in DST months and 22:00 UTC in winter months, i.e. 17:00 ET
in both. Broker timestamps are therefore true UTC, and **IST = UTC + 5:30** as
`market_study.build_features` assumes. This was checked because a one-hour error
would have silently relabelled every session.

**Session map (IST, and the UTC hours they actually are).**

| Session | IST | UTC | What it really is |
|---|---|---|---|
| ASIA | 02:30–11:30 | 21:00–06:00 | Asian session; contains the daily break |
| LONDON | 11:30–15:30 | 06:00–10:00 | London morning |
| OVERLAP | 15:30–17:30 | 10:00–12:00 | London midday — **not** a London/NY overlap |
| NY | 17:30–21:30 | 12:00–16:00 | NY morning through early afternoon |
| LATE | 21:30–24:00 | 16:00–18:30 | US afternoon |
| **POSTNY** | **00:00–02:30** | **18:30–21:00** | **added here — was unlabelled** |

Two notes on the project's inherited labels. "OVERLAP" (10:00–12:00 UTC) is
*before* the NY open (13:30 UTC), so it is not an overlap of anything; and
IST 00:00–02:30 was falling through every session filter in the codebase.
It is 10.6% of all bars and is the genuinely dead window, so it is added as
**POSTNY** and reported throughout. This also matters because
`screener.py::_session_mask` has a wraparound bug (Phase 0) that would have
silently dropped exactly this block.

**Windows.** Primary is **RECENT** (2024-09-01 →, 47,123 bars) because mean true
range roughly doubled across the history. **FULL** (100,000 bars) is reported
alongside. For anything claimed as an *edge*, three **disjoint** thirds are used
instead — T1 2022-06→2023-11, T2 2023-11→2025-05, T3 2025-05→2026-09 — because
RECENT is a subset of FULL and agreement between them is not evidence.

**No look-ahead.** Every conditional statistic uses only bars strictly before the
decision bar; every forward measurement starts at the bar after. Every window is
gap-checked so weekend and daily-break joins never enter a return series. Every
tradeable probe enters at `open[i]`, never at `close[i-1]`.

**Cost.** $0.26 spread + $0.02 slippage = **$0.28 round trip** per 0.01 lot,
per Phase 1.

**Multiple testing.** Roughly 130 hypothesis tests are reported below. At
α = 0.05 the Bonferroni threshold is |z| ≈ 3.5, and ~6 spurious |z| > 2 results
should be expected by chance. Nothing here is called an edge on a z-statistic
alone.

---

## 2. Volatility, range, and spread by session

### RECENT (2024-09-01 →, 47,123 bars)

| Session | bars | range mean | p10 | p50 | p75 | p90 | p99 | ATR14 | tick vol |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ASIA | 16,437 | 6.77 | 1.55 | 4.73 | 8.63 | 13.38 | 30.30 | 6.92 | 2,759 |
| LONDON | 8,238 | 6.86 | 2.16 | 5.23 | 8.83 | 12.30 | 27.63 | 6.76 | 3,042 |
| OVERLAP | 4,120 | 6.36 | 1.99 | 4.77 | 8.13 | 11.61 | 25.13 | 6.57 | 2,680 |
| **NY** | 8,236 | **10.14** | 3.02 | **7.66** | 12.79 | 19.02 | 40.85 | 8.07 | 5,548 |
| LATE | 5,109 | 7.17 | 1.96 | 4.95 | 8.72 | 13.70 | 33.87 | 8.59 | 3,628 |
| **POSTNY** | 4,983 | **5.76** | 1.32 | **3.82** | 6.98 | 11.45 | 27.98 | 7.45 | 2,602 |

### FULL (100,000 bars) — same ordering, roughly half the magnitude

| Session | bars | range mean | p50 | p90 | ATR14 |
|---|---:|---:|---:|---:|---:|
| ASIA | 34,865 | 4.07 | 2.14 | 9.28 | 4.26 |
| LONDON | 17,470 | 4.45 | 2.92 | 8.86 | 4.24 |
| OVERLAP | 8,739 | 4.12 | 2.69 | 8.21 | 4.21 |
| NY | 17,484 | 6.91 | 4.75 | 13.88 | 5.38 |
| LATE | 10,841 | 4.66 | 2.92 | 9.48 | 5.72 |
| POSTNY | 10,601 | 3.63 | 2.02 | 7.63 | 4.88 |

Median bar range **doubled** in every session between FULL and RECENT (ASIA
2.14 → 4.73, NY 4.75 → 7.66). The rank order is stable: NY is loudest by a wide
margin, POSTNY quietest, and ASIA/LONDON/OVERLAP/LATE cluster together.

### Spread — flat across sessions, which is the important part

| Session | mean | p50 | p90 | p99 | spread as % of median range | **round-trip cost as % of median range** |
|---|---:|---:|---:|---:|---:|---:|
| ASIA | 0.191 | 0.16 | 0.28 | 0.36 | 3.38% | **5.92%** |
| LONDON | 0.190 | 0.16 | 0.28 | 0.36 | 3.06% | **5.36%** |
| OVERLAP | 0.189 | 0.16 | 0.28 | 0.36 | 3.36% | **5.88%** |
| **NY** | 0.189 | 0.16 | 0.28 | 0.36 | **2.09%** | **3.65%** |
| LATE | 0.188 | 0.16 | 0.28 | 0.36 | 3.23% | **5.65%** |
| **POSTNY** | 0.191 | 0.16 | 0.28 | 0.36 | **4.19%** | **7.33%** |

(FULL window: spread median $0.20 everywhere, cost 5.9%–13.9% of median range.)

**The spread does not widen in thin sessions.** Median is $0.16 and p90 is $0.28
in all six, RECENT and FULL alike. Sample sizes are 4,000–16,000 bars per cell,
so this is not a resolution artifact. The consequence is that **cost is a fixed
toll and only the size of the move varies**, which makes the loud session the
cheap one: a round trip costs 3.65% of a typical NY bar and 7.33% of a typical
POSTNY bar — POSTNY is **twice as expensive** per unit of available movement.

This is in direct tension with Phase 1's conclusion that the $100 account should
prefer the quiet sessions. Both statements are true and they are about different
things — see §8.2.

---

## 3. Return distribution and fat tails

Log returns per M15 bar, in basis points, RECENT window.

| Session | n | mean (bp) | std | mean abs | skew | excess kurtosis | P(>3σ) | P(>5σ) | drift z |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ASIA | 15,921 | +0.131 | 13.84 | 8.36 | −0.99 | **29.4** | 1.75% | 0.54% | 1.20 |
| LONDON | 8,237 | +0.155 | 13.43 | 8.56 | −1.27 | **31.1** | 1.42% | 0.36% | 1.05 |
| OVERLAP | 4,120 | +0.369 | 13.49 | 7.83 | +7.25 | **258.8** | 1.07% | 0.29% | 1.76 |
| NY | 8,235 | −0.143 | 19.39 | 12.90 | −1.15 | **23.4** | 1.59% | 0.35% | −0.67 |
| LATE | 5,109 | −0.055 | 14.44 | 8.60 | −1.20 | **42.5** | 1.45% | 0.47% | −0.27 |
| POSTNY | 4,983 | +0.147 | 12.17 | 7.15 | +0.90 | **31.4** | 1.91% | 0.68% | 0.85 |

FULL window is the same picture at lower amplitude (kurtosis 21–311, |drift z|
≤ 1.5 everywhere).

**No session has statistically significant directional drift.** Every |z| < 1.8,
against a Bonferroni threshold of 3.5. The mildly positive Asia/London/Overlap
means and negative NY mean are noise — and note that even the *sign* pattern
(gold drifting up overnight, down in NY) reverses between windows for LATE.

**Excess kurtosis of 23–259 is the single most important number in this
section.** Gaussian is 0. A distribution this fat means correlation-based
statistics are dominated by a handful of observations, which is exactly what
§7 shows destroyed four of the five candidate edges. The OVERLAP figure of 259
is driven by a small number of extreme prints in the 10:00–12:00 UTC block.

Skew is mildly negative in four of six sessions (−0.99 to −1.27): down-moves in
gold are slightly more abrupt than up-moves. This is too small and too unstable
to trade but it does argue against symmetric-target assumptions.

---

## 4. Efficiency tests — is any session predictable?

### 4.1 Return autocorrelation, lags 1–8 (RECENT; ρ with z in parentheses)

| Session | n | lag1 | lag2 | lag3 | lag4 | lag5 | lag6 | lag7 | lag8 |
|---|---:|---|---|---|---|---|---|---|---|
| ASIA | 15,239 | .003 (0.3) | .001 (0.1) | −.028 (−3.4) | −.012 (−1.4) | .021 (2.4) | −.021 (−2.3) | .014 (1.6) | −.004 (−0.4) |
| **LONDON** | 7,721 | **−.069 (−6.1)** | .055 (4.6) | .020 (1.6) | .008 (0.6) | −.001 (−0.1) | −.045 (−3.3) | .041 (2.8) | −.061 (−3.9) |
| OVERLAP | 3,605 | −.038 (−2.3) | .008 (0.4) | −.058 (−3.0) | .015 (0.7) | .011 (0.4) | −.045 (−1.5) | −.051 (−1.2) | — |
| NY | 7,720 | .026 (2.3) | .009 (0.8) | −.008 (−0.7) | −.019 (−1.5) | −.007 (−0.5) | .010 (0.7) | −.004 (−0.3) | .002 (0.1) |
| LATE | 4,595 | −.014 (−0.9) | −.021 (−1.3) | .012 (0.7) | .030 (1.7) | .018 (0.9) | .044 (2.0) | .031 (1.2) | .026 (0.8) |
| POSTNY | 4,481 | **.054 (3.6)** | −.012 (−0.7) | −.004 (−0.2) | .004 (0.2) | **−.108 (−5.4)** | .034 (1.5) | −.087 (−3.4) | −.038 (−1.2) |

FULL window agrees on sign and significance for LONDON lag1 (−.052, z = −6.7),
POSTNY lag1 (+.042, z = 4.1) and POSTNY lag5 (−.071, z = −5.1); ASIA, NY and
LATE remain indistinguishable from zero at every lag.

Only **LONDON lag 1** and **POSTNY lag 1/lag 5** clear the |z| = 3.5 threshold in
both windows. Everything else is consistent with an efficient series.

### 4.2 Reversal vs continuation (consecutive-bar sign agreement)

| Session | RECENT n | cont. rate | z | FULL n | cont. rate | z |
|---|---:|---:|---:|---:|---:|---:|
| ASIA | 15,231 | 0.4935 | −1.60 | 32,325 | 0.4902 | −3.52 |
| LONDON | 7,721 | 0.4902 | −1.72 | 16,374 | 0.4881 | −3.05 |
| OVERLAP | 3,605 | 0.4791 | −2.52 | 7,640 | 0.4796 | −3.57 |
| NY | 7,718 | 0.4900 | −1.75 | 16,386 | 0.4883 | −3.00 |
| LATE | 4,591 | 0.4877 | −1.67 | 9,741 | 0.4925 | −1.49 |
| POSTNY | 4,477 | 0.4845 | −2.08 | 9,524 | 0.4817 | −3.57 |

**Every session is below 50%, everywhere, in both windows.** Gold M15 is mildly
mean-reverting at bar scale as a universal property — not a session-specific
one. The effect is 1–2 percentage points, which is far too small to pay a
$0.28 toll (see §7).

### 4.3 Directional persistence expectancy (RECENT)

Signal = `close[i] − close[i−4]`; outcome = `close[i+4] − close[i]`, signed by
the prior move. Positive = trend-following pays.

| Session | n | mean $ | median $ | mean ATR | hit | hit z | mean z | net of cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ASIA | 13,710 | **+0.210** | +0.084 | +0.039 | 0.507 | 1.52 | 2.01 | −0.070 |
| LONDON | 8,229 | −0.124 | −0.246 | −0.041 | 0.482 | −3.21 | −1.09 | −0.404 |
| **OVERLAP** | 4,116 | **−0.376** | −0.539 | −0.073 | 0.461 | **−4.96** | −1.91 | −0.656 |
| NY | 8,227 | −0.074 | −0.034 | +0.013 | 0.498 | −0.36 | −0.40 | −0.354 |
| LATE | 5,059 | −0.279 | −0.283 | −0.050 | 0.476 | −3.45 | −1.76 | −0.559 |
| POSTNY | 3,641 | −0.102 | −0.114 | −0.001 | 0.488 | −1.44 | −0.59 | −0.382 |

At the 8-bar horizon ASIA (+$0.56, z = 3.86) and NY (+$0.57, z = 2.27) turn
positive while OVERLAP (−$0.48) and LATE (−$0.76, z = −3.50) get worse. But the
FULL window shrinks all of these toward zero (ASIA +$0.20, NY +$0.25, both
|z| < 2.9) — i.e. the RECENT "persistence" is mostly the volatility doubling
inflating a near-zero edge into a larger dollar figure.

**Net of cost, only ASIA-8×8 (+$0.28) and NY-8×8 (+$0.29) are positive in
RECENT, and neither survives into FULL.** OVERLAP is the most consistently
anti-trend cell in the entire study: negative in both windows, at both horizons,
with hit-rate z of −5.0 and −5.6.

### 4.4 Breakouts and false breakouts (20-bar extreme, RECENT)

False break = close returns inside the prior range within 4 bars.

| Session | dir | n | break rate | **false rate** | fwd8 $ | fwd8 ATR | hit | hit z | net of cost |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ASIA | up | 668 | 12.2% | 75.8% | +0.58 | +0.13 | 0.536 | 1.86 | +0.30 |
| ASIA | dn | 543 | 9.9% | 79.2% | −0.12 | −0.10 | 0.453 | −2.19 | −0.40 |
| LONDON | up | 1,179 | 14.3% | 75.9% | +0.56 | +0.18 | 0.520 | 1.37 | +0.28 |
| LONDON | dn | 846 | 10.3% | 81.1% | −1.48 | −0.22 | 0.442 | −3.37 | −1.76 |
| OVERLAP | up | 485 | 11.8% | **83.1%** | +0.12 | +0.05 | 0.493 | −0.32 | −0.16 |
| OVERLAP | dn | 331 | 8.1% | **86.1%** | +0.06 | −0.23 | 0.381 | −4.34 | −0.22 |
| **NY** | up | 1,444 | 17.6% | 75.8% | **+0.89** | +0.26 | **0.565** | **4.95** | **+0.61** |
| NY | dn | 1,098 | 13.4% | 77.1% | +0.60 | +0.13 | 0.499 | −0.06 | +0.32 |
| LATE | up | 450 | 9.0% | **84.7%** | −1.76 | −0.20 | 0.429 | −3.02 | −2.04 |
| LATE | dn | 298 | 6.0% | 84.2% | −0.62 | −0.15 | 0.436 | −2.20 | −0.90 |
| POSTNY | up | 84 | 5.1% | 78.6% | +2.19 | +0.17 | 0.548 | 0.87 | +1.91 |
| POSTNY | dn | 74 | 4.5% | 81.1% | −1.65 | +0.03 | 0.419 | −1.40 | −1.93 |

**Breakouts fail 76–86% of the time in every session.** The best case (NY and
ASIA up-breaks, ~76%) is barely better than the worst (OVERLAP/LATE, ~85%).
There is no session where a 20-bar break is a reliable continuation signal.

The apparent up/down asymmetry — up-breaks look better than down-breaks
everywhere — is **not** microstructure. Gold went 1,850 → 4,428 (+139%) across
this sample. Any long-biased statistic is contaminated. §7 removes the drift and
the asymmetry largely goes with it.

NY up-breaks are the only cell with a hit-rate z above the Bonferroni threshold
(4.95). It is tested properly in §7.4 and does not survive.

### 4.5 Z-score mean reversion (20-bar z, 4-bar forward, RECENT)

| Session | bucket | n | mean $ | mean ATR | hit | hit z | mean z | net |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| ASIA | all | 5,471 | −0.86 | −0.096 | 0.473 | −3.96 | −5.75 | −1.14 |
| ASIA | \|z\|>2 | 705 | −1.02 | −0.123 | 0.462 | −2.00 | −2.15 | −1.30 |
| LONDON | all | 8,229 | +0.14 | +0.026 | 0.521 | 3.80 | 1.23 | −0.14 |
| LONDON | \|z\|>2 | 1,647 | +0.39 | +0.042 | 0.526 | 2.14 | 1.27 | +0.11 |
| **OVERLAP** | all | 4,108 | +0.33 | +0.097 | 0.558 | **7.40** | 1.67 | +0.05 |
| OVERLAP | \|z\|>2 | 546 | +0.87 | +0.097 | 0.566 | 3.08 | 1.28 | +0.59 |
| OVERLAP | \|z\|>2.5 | 251 | +1.42 | +0.063 | 0.574 | 2.34 | 1.32 | +1.14 |
| NY | all | 8,211 | −0.36 | −0.054 | 0.493 | −1.27 | −1.92 | −0.64 |
| NY | \|z\|>2 | 2,338 | −0.68 | −0.111 | 0.487 | −1.24 | −2.16 | −0.96 |
| LATE | \|z\|>2 | 438 | +1.82 | +0.245 | 0.605 | 4.40 | 1.98 | +1.54 |
| POSTNY | \|z\|>2 | 388 | −0.46 | −0.062 | 0.531 | 1.22 | −0.57 | −0.74 |

**ASIA and NY punish mean reversion; OVERLAP, LONDON and LATE reward it.** This
is the mirror image of §4.3 (ASIA/NY were the only trend-positive cells) and is
internally consistent: ASIA and NY are the trending sessions, OVERLAP and LATE
are the chopping ones.

The OVERLAP `all`-bucket hit-rate z of 7.40 is the largest single statistic in
this report and it replicates in FULL (z = 6.27, n = 8,724). But note the mean-z
column: only 1.67. **The hit rate is reliably above 50% while the dollar mean is
not reliably above zero** — the wins are smaller than the losses. That is the
signature of an effect that cannot pay a fixed toll, and §7.3 confirms it.

### 4.6 Volatility clustering (RECENT)

| Session | n | ρ(\|r\|, lag 1) | z | P(next range > median \| range > p75) | P(… \| range < p25) |
|---|---:|---:|---:|---:|---:|
| ASIA | 15,239 | 0.369 | 45.5 | 0.943 | 0.062 |
| LONDON | 7,721 | 0.317 | 27.8 | 0.903 | 0.103 |
| OVERLAP | 3,605 | 0.290 | 17.4 | 0.914 | 0.094 |
| NY | 7,720 | 0.304 | 26.7 | 0.917 | 0.115 |
| LATE | 4,595 | 0.320 | 21.7 | 0.942 | 0.085 |
| POSTNY | 4,481 | 0.327 | 21.9 | 0.945 | 0.060 |

**Volatility is overwhelmingly predictable in every session** (z = 17–70; FULL
window z = 25–70). After a top-quartile bar, the next bar exceeds the median
range 90–95% of the time; after a bottom-quartile bar, 6–14%.

This is the one genuinely strong, universal, replicable structure in the data —
and it says nothing about *direction*. Its only use is **position sizing and
stop placement**, which is exactly where the $100 account's problem lives (§8.1).
The session differences are small and not exploitable; ASIA clusters slightly
harder than the rest.

### 4.7 Trend-state persistence (EMA20/50/200 stack, RECENT)

Runs attributed to the session in which they started.

| Session | fraction aligned | 1-bar survival | runs started | mean len (bars) | p50 | p90 |
|---|---:|---:|---:|---:|---:|---:|
| ASIA | 0.767 | 0.983 | 586 | 44.0 | 38 | 92 |
| LONDON | 0.698 | 0.981 | 91 | 34.4 | 37 | 57 |
| OVERLAP | 0.688 | 0.986 | 46 | 23.9 | 23.5 | 42.5 |
| NY | 0.714 | 0.979 | 140 | 24.4 | 27 | 34.1 |
| LATE | 0.739 | 0.989 | 55 | 15.7 | 16 | 22 |
| POSTNY | 0.763 | 0.990 | 51 | 7.0 | 7 | 11 |

FULL window is nearly identical (ASIA mean 43.9, POSTNY 6.6), so this is stable.

A stack is aligned ~70–77% of the time in every session and survives the next
bar with p ≈ 0.98–0.99 everywhere. **The stack is almost always "on" and almost
never flips — it carries very little information.** The run-length differences
are an artifact of where runs *start*, not of session character: ASIA has 9 hours
to start runs in and POSTNY has 2.5, and a run started at 00:00 IST has at most
10 bars before POSTNY ends. The 1-bar survival column, which is duration-neutral,
is flat at 0.979–0.990 across all six sessions.

**Implication for EMA_STACK** (the project's current best candidate): its entry
condition is satisfied roughly three-quarters of the time in every session, so it
is not selecting a rare state. Whatever it does, it is not the stack filter doing
it.

### 4.8 Wick characteristics (RECENT)

| Session | n | upper wick | lower wick | body | body p50 | upper − lower |
|---|---:|---:|---:|---:|---:|---:|
| ASIA | 16,437 | 0.270 | 0.284 | 0.447 | 0.442 | −0.014 |
| LONDON | 8,238 | 0.273 | 0.281 | 0.446 | 0.445 | −0.008 |
| OVERLAP | 4,120 | 0.276 | 0.285 | 0.440 | 0.422 | −0.009 |
| NY | 8,236 | 0.263 | 0.283 | 0.454 | 0.458 | −0.021 |
| LATE | 5,109 | 0.275 | 0.288 | 0.437 | 0.434 | −0.013 |
| POSTNY | 4,983 | 0.269 | 0.283 | 0.449 | 0.452 | −0.014 |

**Effectively identical across all six sessions**, in both windows: body ≈ 45% of
range, each wick ≈ 27–29%. The largest between-session difference is 1.7
percentage points of body fraction (NY 0.454 vs LATE 0.437). Lower wicks exceed
upper wicks by 0.8–2.1 points everywhere — a faint buy-the-dip signature
consistent with the sample's secular uptrend, not a session property.

**Bar shape carries no session information.** Any candidate keyed on wick
patterns has no session-specific basis to stand on.

---

## 5. Hour-by-hour (IST), RECENT window

| IST hr | session | bars | range p50 | \|r\| bp | ρ lag1 | z | cont. | z | persist $ | z | n |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 00 | POSTNY | 2,006 | 4.16 | 7.91 | +.101 | **3.93** | 0.489 | −0.83 | +0.14 | 0.61 | 1,985 |
| 01 | POSTNY | 1,985 | 3.82 | 6.91 | −.042 | −1.63 | 0.486 | −1.09 | −0.33 | −1.10 | 1,324 |
| 02 | POSTNY | 1,324 | 3.18 | 5.99 | −.021 | −0.62 | 0.473 | −1.57 | −0.64 | −1.34 | 332 |
| 03 | ASIA | 1,008 | 3.59 | 6.30 | −.196 | −2.52 | 0.560 | 1.55 | — | — | 0 |
| 04 | ASIA | 1,708 | 3.86 | 7.02 | +.024 | 0.75 | 0.488 | −0.79 | +1.01 | 2.31 | 676 |
| 05 | ASIA | 2,059 | 4.75 | 8.68 | −.071 | −2.79 | 0.489 | −0.89 | +0.54 | 1.44 | 1,706 |
| 06 | ASIA | 2,060 | 6.42 | 11.57 | −.043 | −1.68 | 0.488 | −0.94 | +0.36 | 1.11 | 2,059 |
| 07 | ASIA | 2,060 | 5.98 | 10.00 | +.054 | 2.14 | 0.496 | −0.33 | +0.04 | 0.16 | 2,060 |
| 08 | ASIA | 2,060 | 5.30 | 8.67 | −.026 | −1.04 | 0.504 | 0.33 | −0.15 | −0.82 | 2,060 |
| 09 | ASIA | 2,060 | 3.86 | 6.03 | −.052 | −2.06 | 0.496 | −0.33 | −0.20 | −1.30 | 2,059 |
| 10 | ASIA | 2,060 | 4.05 | 6.31 | +.055 | 2.17 | 0.487 | −1.04 | +0.18 | 0.61 | 2,060 |
| **11** | ASIA | 2,060 | 5.77 | 9.95 | **+.114** | **4.49** | 0.490 | −0.79 | +0.16 | 0.59 | 2,060 |
| **12** | LONDON | 2,060 | 5.44 | 8.62 | **−.127** | **−4.99** | 0.496 | −0.33 | −0.36 | −1.47 | 2,059 |
| 13 | LONDON | 2,059 | 5.33 | 8.93 | −.063 | −2.49 | 0.516 | 1.27 | +0.39 | 1.63 | 2,056 |
| 14 | LONDON | 2,059 | 5.02 | 8.09 | −.094 | −3.69 | 0.476 | −1.91 | −0.21 | −1.08 | 2,056 |
| **15** | LONDON | 2,060 | 4.68 | 7.55 | **−.138** | **−5.44** | 0.476 | −1.91 | −0.43 | −1.77 | 2,058 |
| 16 | OVERLAP | 2,060 | 4.63 | 7.82 | −.057 | −2.25 | 0.469 | −2.47 | −0.54 | −2.11 | 2,058 |
| 17 | OVERLAP | 2,058 | 5.41 | 9.11 | −.031 | −1.23 | 0.501 | 0.08 | +0.31 | 0.97 | 2,056 |
| 18 | NY | 2,059 | 7.40 | 12.47 | −.065 | −2.55 | 0.486 | −1.10 | −0.47 | −1.31 | 2,056 |
| **19** | NY | 2,060 | **9.22** | **15.04** | −.029 | −1.14 | 0.499 | −0.10 | −0.07 | −0.18 | 2,059 |
| 20 | NY | 2,060 | 7.99 | 13.48 | **+.088** | **3.44** | 0.498 | −0.18 | +0.07 | 0.17 | 2,057 |
| 21 | NY | 2,057 | 6.17 | 10.78 | +.025 | 0.97 | 0.502 | 0.15 | −0.15 | −0.54 | 2,048 |
| 22 | LATE | 2,048 | 5.09 | 8.36 | −.013 | −0.52 | 0.493 | −0.54 | −0.22 | −0.84 | 2,033 |
| 23 | LATE | 2,033 | 4.44 | 7.89 | −.084 | −3.29 | 0.470 | **−2.36** | −0.33 | −1.36 | 2,005 |

The FULL window reproduces every one of the bolded cells with the same sign and
comparable or larger |z| (hour 11 +.097/z=5.56, hour 12 −.097/z=−5.57, hour 15
−.101/z=−5.80, hour 20 +.066/z=3.78, hour 00 +.071/z=4.00).

**Best and worst hours.**
- **Loudest:** IST 19 (median range $9.22, |r| 15.0 bp) — NY midday, 12:30–13:30
  UTC, the US data window. IST 18–20 is the only three-hour block where median
  range exceeds $7.
- **Quietest:** IST 02–03 ($3.18–3.59) — includes the daily break, which is why
  hour 03 has only 1,008 bars and zero valid 4-bar persistence windows.
- **Most reverting:** IST 15 (ρ = −0.138) and IST 12 (ρ = −0.127), the London
  block's first and last hours.
- **Most trending:** IST 11 (ρ = +0.114), the final Asia hour immediately before
  the London open.
- **Worst directional expectancy:** IST 16 (−$0.54, z = −2.11), the first
  OVERLAP hour.

Every persistence-expectancy |z| in this table is below 2.4 except hour 04
(z = 2.31 on only 676 samples, an artifact of the daily break truncating
windows). Against a 24-test Bonferroni threshold of z ≈ 3.1, **no hour has
tradeable directional expectancy.** The significant cells are all
autocorrelation, and §7 shows why that does not convert.

---

## 6. Day-of-week and sub-window effects

### 6.1 Day of week

The only cell reaching |z| > 2.5 in either window is **ASIA on Wednesday**:
RECENT mean return +0.685 bp (drift z = 3.15) with persistence expectancy
+$0.851 (z = 4.36, n = 2,719); FULL +0.318 bp (z = 2.86), +$0.335 (z = 3.58,
n = 5,851). It replicates across windows with consistent sign.

It is nonetheless **rejected**: with 6 sessions × 5 weekdays × 2 statistics = 60
tests, the Bonferroni threshold is z ≈ 3.4, and Wednesday-Asia is the only
survivor out of 60 — precisely the rate at which a scan of this size produces
one. There is no mechanism (no Wednesday gold event exists at 02:30–11:30 IST),
and the neighbouring cells are inconsistent: ASIA Monday is −$0.449 (z = −1.61)
in RECENT but −$0.221 (z = −1.61) in FULL, while LATE Friday flips from
−1.14 bp (z = −2.40) in RECENT to −0.447 bp (z = −1.68) in FULL.

Everything else is flat. Range by weekday varies by less than 20% within any
session; NY Thursday/Friday are the widest bars ($8.04/$8.00 vs Monday $6.95),
consistent with the US data calendar, but carry no directional edge (|z| ≤ 1.2).

### 6.2 Sub-windows — where sessions genuinely differ internally (RECENT)

| Session | sub-window | bars | range p50 | \|r\| bp | ρ lag1 | z | cont. | z | persist $ | z | body |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ASIA | first 1h | 664 | 2.72 | 5.53 | −.082 | −1.82 | 0.540 | 1.79 | — | — | 0.444 |
| ASIA | middle | 13,713 | 4.79 | 8.45 | −.010 | −1.07 | 0.491 | −2.10 | +0.15 | 1.33 | 0.446 |
| **ASIA** | **last 1h** | 2,060 | 5.12 | 8.69 | **+.108** | **4.24** | 0.507 | 0.59 | +0.57 | 1.86 | 0.455 |
| LONDON | first 1h | 2,060 | 5.42 | 9.10 | +.073 | 2.89 | 0.507 | 0.53 | −0.49 | −2.03 | 0.455 |
| LONDON | middle | 4,118 | 5.28 | 8.60 | −.054 | −3.26 | 0.499 | −0.17 | +0.19 | 1.10 | 0.444 |
| **LONDON** | **last 1h** | 2,060 | 4.84 | 7.92 | **−.215** | **−8.43** | **0.452** | **−3.79** | −0.38 | −2.02 | 0.440 |
| OVERLAP | first 1h | 2,060 | 4.67 | 7.53 | −.006 | −0.24 | 0.479 | −1.65 | −0.39 | −1.40 | 0.444 |
| OVERLAP | last 1h | 2,060 | 4.86 | 8.12 | −.121 | −4.76 | 0.495 | −0.38 | −0.36 | −1.31 | 0.436 |
| NY | first 1h | 2,057 | 6.37 | 11.07 | +.019 | 0.74 | 0.505 | 0.36 | +0.01 | 0.02 | 0.455 |
| NY | middle | 4,120 | 8.65 | 14.25 | −.017 | −1.04 | 0.488 | −1.48 | −0.12 | −0.41 | 0.457 |
| **NY** | **last 1h** | 2,059 | 7.04 | 12.02 | **+.164** | **6.45** | 0.473 | −2.09 | −0.06 | −0.19 | 0.449 |
| LATE | first 1h | 2,055 | 5.44 | 9.48 | +.015 | 0.60 | 0.495 | −0.43 | −0.33 | −1.32 | 0.442 |
| LATE | middle | 2,039 | 4.73 | 7.97 | −.047 | −1.84 | 0.487 | −1.05 | −0.34 | −1.38 | 0.431 |
| LATE | last 30m | 1,015 | 4.45 | 8.10 | +.011 | 0.25 | 0.466 | −1.51 | −0.04 | −0.12 | 0.436 |
| POSTNY | first 1h | 2,006 | 4.16 | 7.91 | +.101 | 3.93 | 0.489 | −0.83 | +0.14 | 0.61 | 0.453 |
| POSTNY | rest | 2,977 | 3.61 | 6.64 | +.006 | 0.31 | 0.486 | −1.41 | −0.39 | −1.52 | 0.445 |

**Sub-windows differ materially, and by more than the sessions do.** The
London last hour (ρ = −0.215) and the NY last hour (ρ = +0.164) are further apart
from each other than any two whole sessions are, and each is far from its own
session's average (LONDON overall −0.069, NY overall +0.026). A session-level
analysis genuinely does average away real structure.

Three sub-windows are worth naming, all replicated in FULL:
1. **LONDON last hour (IST 14:30–15:30)** — the strongest reversal cell in the
   dataset. ρ = −0.215 (z = −8.43) RECENT, −0.169 (z = −9.65) FULL; continuation
   rate 0.452 (z = −3.79) RECENT, 0.471 (z = −3.36) FULL. This clears Bonferroni
   comfortably in both windows.
2. **NY last hour (IST 20:30–21:30)** — ρ = +0.164 (z = 6.45) RECENT, +0.131
   (z = 7.50) FULL. But note continuation rate is *below* 50% (0.473, z = −2.09)
   at the same time. Positive correlation with negative sign-persistence is a
   contradiction that only resolves one way: the correlation is coming from a few
   large pairs. §7.2 confirms this.
3. **ASIA last hour (IST 10:30–11:30)** — ρ = +0.108 (z = 4.24), the pre-London
   momentum hour, replicated at +0.092 (z = 5.24) in FULL.

Range and bar shape barely move across sub-windows (body fraction 0.431–0.457
across all sixteen). The internal variation is in *serial dependence*, not in
volatility or bar geometry.

---

## 7. Adversarial testing — do the five anomalies convert into money?

Every candidate from §4–§6 was turned into a tradeable rule and evaluated on
three **disjoint** thirds. Entry `open[i]`, exit `close[i+h−1]`, $0.28 charged
per round trip, direction decided only from `close[i−1]` and earlier.

The `close[i−1] → open[i]` gap is small ($0.039 mean absolute, $0.031 median,
n = 98,903), so entering at the next open rather than the signal close costs
almost nothing. **The gap is not what kills these — the cost is.**

`drift$` is the expectancy of taking *every* bar in the probe's candidate
universe at the probe's own long/short mix; `excess$` is gross minus that. It
exists because gold rose 139% across this sample.

### 7.1 The decisive test: is the autocorrelation in the body or the tails?

Excess kurtosis of 23–259 (§3) means a Pearson correlation can be produced
entirely by a handful of extreme bar-pairs. A sign-based rule cannot harvest
that. Comparing Pearson against Spearman (rank) and winsorised (clipped at the
1st/99th percentile) correlations separates the two cases:

| Window | n | Pearson | z | Spearman | z | Winsorised | z |
|---|---:|---:|---:|---:|---:|---:|---:|
| **LONDON last hr** IST 14:30–15:30 | 3,276 | −0.169 | −9.65 | **−0.072** | **−4.11** | **−0.078** | **−4.44** |
| LONDON all IST 11:30–15:30 | 16,376 | −0.052 | −6.67 | −0.026 | −3.34 | −0.025 | −3.19 |
| **NY last hr** IST 20:30–21:30 | 3,278 | +0.131 | 7.50 | **−0.026** | −1.49 | **−0.008** | −0.45 |
| ASIA last hr IST 10:30–11:30 | 3,276 | +0.092 | 5.24 | +0.028 | 1.60 | +0.048 | 2.77 |
| **OVERLAP last hr** IST 16:30–17:30 | 3,277 | −0.096 | −5.48 | −0.025 | −1.45 | **+0.008** | 0.44 |
| **POSTNY first hr** IST 00:00–01:00 | 3,196 | +0.071 | 4.00 | **−0.029** | −1.66 | +0.015 | 0.86 |

**This table eliminates four of the five candidates.**

- **NY last hour**: Pearson +0.131 (z = 7.50) collapses to −0.008 (z = −0.45)
  winsorised, and the sign *flips*. The apparent momentum is a handful of large
  bar-pairs; the body of the distribution is, if anything, faintly reverting.
  This resolves the §6.2 contradiction exactly as predicted.
- **OVERLAP last hour**: −0.096 (z = −5.48) → +0.008 (z = 0.44). Pure tail
  artifact, sign flips.
- **POSTNY first hour**: +0.071 (z = 4.00) → +0.015 (z = 0.86), Spearman −0.029.
  Pure tail artifact.
- **ASIA last hour**: +0.092 → +0.048 (z = 2.77). Survives partially but falls
  below the multiple-testing threshold and is a third of its headline size.
- **LONDON last hour**: −0.169 → −0.078 (z = −4.44), **same sign, still
  significant**. This is the only anomaly in the entire study that lives in the
  body of the distribution rather than in its tails.

### 7.2 The four tail artifacts, traded

| Probe | window | n | gross $ | gross ATR | net $ | hit | t | total $ |
|---|---|---:|---:|---:|---:|---:|---:|
| NY_MOM follow prev bar, IST 20:30–21:30 | T1 | 1,451 | +0.061 | +0.016 | −0.219 | 0.420 | −3.79 | −318 |
| | T2 | 1,540 | −0.099 | −0.015 | −0.379 | 0.432 | −4.44 | −584 |
| | T3 | 1,378 | +0.195 | +0.011 | −0.085 | 0.472 | −0.31 | −117 |
| | **ALL** | 4,369 | +0.047 | +0.003 | **−0.233** | 0.441 | −2.47 | **−1,018** |
| ASIA_MOM follow prev bar, IST 10:30–11:30 | T1 | 1,448 | −0.013 | −0.011 | −0.293 | 0.374 | −10.04 | −425 |
| | T2 | 1,539 | +0.042 | +0.025 | −0.238 | 0.421 | −4.51 | −367 |
| | T3 | 1,380 | +0.114 | −0.011 | −0.166 | 0.465 | −0.87 | −230 |
| | **ALL** | 4,367 | +0.046 | +0.002 | **−0.234** | 0.420 | −3.67 | **−1,021** |
| OVL_ZREV fade \|z\|>2, IST 15:30–17:30, h=4 | T1 | 429 | +0.341 | +0.137 | +0.061 | 0.497 | 0.31 | +26 |
| | T2 | 474 | +0.028 | −0.021 | −0.252 | 0.473 | −0.95 | −119 |
| | T3 | 331 | +0.544 | +0.035 | +0.264 | 0.553 | 0.28 | +87 |
| | **ALL** | 1,234 | +0.275 | +0.049 | **−0.005** | 0.502 | −0.02 | **−6** |
| OVL_ZREV+ fade \|z\|>2.5 | ALL | 556 | +0.938 | +0.152 | +0.658 | 0.513 | 1.41 | +366 |
| LON_BRKD short 20-bar break | ALL | 986 | −0.460 | −0.100 | **−0.740** | 0.432 | −1.57 | **−730** |

**NY_MOM and ASIA_MOM lose money in all three disjoint thirds** and lose
$1,018 and $1,021 respectively over the full sample. The §4.1/§6.2 momentum
signals are unambiguously not tradeable.

**OVL_ZREV** — the OVERLAP mean-reversion candidate with the study's highest
hit-rate z (7.40) — nets **−$0.005 per trade** over 1,234 trades. Exactly as
§4.5 predicted from the hit-rate/mean-z divergence: it wins slightly more often
than it loses and loses slightly more when it does. Tightening to |z| > 2.5
gives +$0.658 (t = 1.41, n = 556) but the thirds read +0.59 / −0.12 / +1.94 —
sign-unstable, and 76% of the total profit comes from T3 alone.

### 7.3 NY breakout continuation, with the drift removed

| Probe | window | n | gross $ | net $ | hit | t | drift $ | **excess $** |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| NY_BRK long 20-bar break, h=8 | T1 | 449 | +0.539 | +0.259 | 0.445 | 0.64 | +0.014 | +0.525 |
| | T2 | 533 | +0.247 | −0.033 | 0.516 | −0.08 | −0.210 | +0.458 |
| | T3 | 481 | +0.853 | +0.573 | 0.570 | 0.54 | −0.777 | +1.630 |
| | **ALL** | 1,463 | +0.536 | **+0.256** | 0.512 | **0.64** | −0.315 | +0.851 |

The §4.4 hit-rate z of 4.95 does not survive contact with a real entry rule.
Net expectancy is +$0.26 per trade with **t = 0.64** on 1,463 trades — no
significance whatsoever, and negative in T2. The excess-over-drift column is
positive in all three thirds, so there may be something there, but at t = 0.64
it is indistinguishable from noise and nowhere near enough to build on.

### 7.4 The survivor: the London-afternoon reversal

This is the only candidate with body-of-distribution support (§7.1). Traded:

| Probe | window | n | gross $ | gross ATR | net $ | hit | t | total $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| LON_REV fade prev bar, IST 14:30–15:30 | T1 | 1,448 | −0.013 | −0.005 | −0.293 | 0.398 | −8.25 | −424 |
| | T2 | 1,540 | +0.021 | +0.004 | −0.259 | 0.444 | −5.12 | −398 |
| | T3 | 1,379 | +0.612 | +0.042 | +0.332 | 0.509 | 1.84 | +458 |
| | **ALL** | 4,367 | **+0.197** | **+0.013** | **−0.083** | 0.450 | −1.37 | **−364** |
| LON_REV+ \|prev\| > 0.5×ATR | T1 | 612 | +0.033 | +0.017 | −0.247 | 0.412 | −4.50 | −151 |
| | T2 | 621 | +0.089 | +0.024 | −0.191 | 0.457 | −2.49 | −119 |
| | T3 | 479 | +1.284 | +0.086 | +1.004 | 0.566 | 3.30 | +481 |
| | **ALL** | 1,712 | +0.403 | +0.039 | +0.123 | 0.471 | 1.33 | +211 |
| LON_REV++ \|prev\| > 1.0×ATR | **ALL** | 457 | +0.473 | +0.053 | +0.193 | 0.505 | 1.31 | +88 |

**The gross edge is +$0.197 per trade. The cost is $0.28.** The unfiltered rule
loses $364 over 4,367 trades. In ATR units the edge is **0.013 ATR** while the
cost is 0.042 ATR at current volatility and 0.067 ATR historically — **the toll
is three to five times the edge.**

This is the cleanest possible statement of the result: *the inefficiency is real
and it is smaller than the spread.*

The magnitude filters raise the gross edge (0.039 and 0.053 ATR) and turn ALL
slightly positive, but t = 1.33 and 1.31, and both are negative in T1 and T2.

**Is the filtered version saved by high volatility?** The edge scales with ATR
while the cost does not, so in principle a high-ATR regime could pay for it:

| ATR bucket | n | gross $ | gross ATR | net $ | t | hit | cost/ATR |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0–2 | 487 | +0.005 | +0.007 | −0.275 | −5.56 | 0.392 | 0.181 |
| 2–4 | 735 | +0.043 | +0.018 | −0.237 | −3.62 | 0.452 | 0.107 |
| 4–6 | 155 | +0.177 | +0.046 | −0.103 | −0.38 | 0.510 | 0.057 |
| 6–8 | 136 | +0.519 | +0.075 | +0.239 | 0.62 | 0.588 | 0.040 |
| 8–12 | 129 | +1.319 | +0.141 | +1.039 | 2.37 | 0.581 | 0.029 |
| >12 | 70 | +5.545 | +0.214 | +5.265 | 3.28 | 0.714 | 0.017 |

This looks compelling and it is **almost entirely a regime confound**:

| ATR bucket | n | fraction of samples from T3 (2025-05 →) |
|---|---:|---:|
| 0–4 | 1,222 | **4.8%** |
| 4–8 | 291 | **78.0%** |
| >8 | 199 | **97.0%** |

"The edge appears when ATR > 8" and "the edge appears after May 2025" are the
same sentence. Splitting by era confirms it:

| Era | ATR bucket | n | gross $ | gross ATR | net $ | t |
|---|---|---:|---:|---:|---:|---:|
| **T1+T2** (2022-06 → 2025-05) | 0–3 | 996 | +0.037 | +0.017 | **−0.243** | **−5.66** |
| | >3 | 237 | +0.160 | +0.037 | −0.120 | −0.72 |
| **T3** (2025-05 →) | 0–6 | 164 | −0.050 | −0.008 | −0.330 | −1.36 |
| | 6–9 | 165 | +0.813 | +0.107 | +0.533 | 1.49 |
| | >9 | **150** | +3.261 | +0.167 | **+2.981** | **3.61** |

**The entire economic result rests on 150 trades, in one 16-month window, at the
highest volatility in the sample.** In the 35 months before that the same rule
loses money at every ATR level. That is a single-regime observation, not a
validated edge.

### 7.5 Falsifying the one plausible mechanism

The London-afternoon window contains a real, named market event: the **LBMA gold
benchmark AM auction at 10:30 London**. Price being pushed into a benchmark
auction and reverting afterwards would be a textbook mechanism, and it would
make the finding credible.

It is testable. The auction is fixed to the *London* clock, so the reverting slot
must shift by a full hour in UTC between BST and GMT. Winsorised lag-1 ρ by
15-minute slot, BST (Apr–Sep) vs GMT (Nov–Feb):

| IST slot | UTC | n BST | ρ BST | z | n GMT | ρ GMT | z |
|---|---|---:|---:|---:|---:|---:|---:|
| 14:15 | 08:45 | 581 | −0.110 | −2.64 | 335 | −0.049 | −0.90 |
| 14:30 | 09:00 | 581 | −0.024 | −0.59 | 336 | −0.071 | −1.29 |
| **14:45** | **09:15** | 581 | **−0.192** | **−4.62** | 336 | −0.027 | −0.49 |
| **15:00** | **09:30** | 581 | +0.029 | 0.71 | 336 | **−0.221** | **−4.04** |
| 15:15 | 09:45 | 581 | −0.079 | −1.91 | 336 | −0.045 | −0.83 |
| 15:45 | 10:15 | 581 | +0.053 | 1.29 | 336 | −0.117 | −2.14 |
| **16:00** | **10:30** | 581 | +0.014 | 0.34 | 336 | −0.045 | −0.83 |

**The auction hypothesis is falsified.** The hot slot sits at 09:15 UTC in BST
and 09:30 UTC in GMT — a 15-minute shift, not the 60-minute shift a
London-clock-anchored event requires. And the slot that *would* be the GMT
auction (10:30 UTC, IST 16:00) shows ρ = −0.045, z = −0.83: nothing.

The effect is anchored to UTC at an unremarkable time with no known gold-market
event. A structure that is regime-dependent (§7.4), sub-cost (§7.4), and has no
mechanism is far more likely to be an artifact than an edge.

---

## 8. Two incidental findings that matter more than the edge search

### 8.1 ATR14 on M15 leaks across session boundaries and mis-sizes every stop

ATR14 on M15 averages the previous 3.5 hours, which routinely spans a session
boundary. The result is that ATR14 **massively understates how different the
sessions are**, and systematically over-sizes stops in the quiet ones:

| Session (RECENT) | median bar range | ATR14 mean | **ATR14 / median range** | 1.5×ATR stop | % of $105.74 |
|---|---:|---:|---:|---:|---:|
| ASIA | 4.73 | 6.92 | 1.46 | $10.37 | 9.8% |
| LONDON | 5.23 | 6.76 | 1.29 | $10.14 | 9.6% |
| OVERLAP | 4.77 | 6.57 | 1.38 | $9.86 | 9.3% |
| NY | **7.66** | 8.07 | **1.05** | $12.11 | 11.5% |
| **LATE** | 4.95 | **8.59** | **1.73** | **$12.89** | **12.2%** |
| **POSTNY** | **3.82** | 7.45 | **1.95** | $11.18 | 10.6% |

NY's true range is **62% larger** than Asia's (7.66 vs 4.73), but ATR14 shows
only a **17%** difference (8.07 vs 6.92). ATR14 captures roughly a quarter of the
real session volatility differential.

The damage is worst exactly where the mission wants to trade. **LATE and POSTNY
are the two quietest sessions by actual bar range, yet ATR14 rates them as
volatile** (8.59 and 7.45) because it is still carrying NY's volatility forward.
A 1.5×ATR stop in LATE is 2.6× the median bar range and risks **12.2%** of the
account — the largest risk of any session, in the session Phase 1 identified as
the *safest*.

**Any session-specific stop must be sized from a session-local statistic**
(median range, or an ATR computed only over same-session bars), never from
rolling ATR14. This directly affects `risk_manager.py` and every ATR-based
candidate in the program, including EMA_STACK.

### 8.2 Resolving the tension with Phase 1

Phase 1 concluded the $100 account should prefer quiet sessions (smaller noise
floor → smaller stop → smaller dollar risk). §2 here shows quiet sessions have
the *worst* cost-to-range ratio (POSTNY 7.33% vs NY 3.65%). Both are correct;
they are different constraints:

- **Phase 1's constraint is survival.** Risk per trade = stop distance in
  dollars. A quiet session permits a $5–6 stop (5% of account) where NY needs
  $9–11 (9–10%).
- **This report's constraint is profitability.** Cost is a flat $0.28 toll, so
  the fraction of each move it consumes is twice as large in POSTNY as in NY.

The two combine into a real bind: **the sessions the account can afford to risk
are the sessions where costs eat the most of each move, and the session where
costs are cheapest is the one the account can least afford to be stopped in.**
There is no session that is both cheap and safe. Any viable strategy must beat
this trade-off explicitly rather than pick a side of it.

---

## 9. VERDICT

### Does each session have a distinct microstructure?

**Partly — but not in ways that can be exploited.**

Sessions differ **materially and reliably** in:
- **Volatility level** (median range NY $7.66 vs POSTNY $3.82, a 2.0× spread)
- **Cost as a fraction of available movement** (3.65% NY to 7.33% POSTNY)
- **Volatility clustering strength** (ρ|r| 0.29–0.37)
- **Trend-vs-chop character** — ASIA/NY are the trending cells, OVERLAP/LATE the
  reverting cells, consistently across §4.3 and §4.5 and across both windows

Sessions are **indistinguishable** in:
- **Spread** (median $0.16, p90 $0.28 in all six)
- **Bar geometry** (body 0.437–0.454, wicks within 2 points everywhere)
- **Trend-state survival** (0.979–0.990 one-bar survival in all six)
- **Directional drift** (every |z| < 1.8)

### Is any session measurably NOT efficient?

**No session is inefficient enough to trade.** Explicitly, against each of the
three forms the question was asked in:

| Question | Answer | Evidence |
|---|---|---|
| Persistent autocorrelation? | **No.** One real cell (LONDON afternoon, winsorised ρ = −0.078, z = −4.44); its edge is 0.013 ATR ≈ $0.20/trade against a $0.28 cost. Four other apparent cells are tail artifacts that vanish or flip sign under winsorisation. | §7.1, §7.4 |
| Reliable reversal after extension? | **No.** The best cell (OVERLAP, hit-rate z = 7.40, replicated) nets **−$0.005/trade** over 1,234 trades. Wins slightly more often, loses slightly more per event. | §4.5, §7.2 |
| Reliable breakout follow-through? | **No.** Breakouts fail 76–86% in every session. The best cell (NY up-breaks) nets +$0.26/trade at **t = 0.64** and is negative in one of three thirds. | §4.4, §7.3 |

### Session-by-session

| Session | Verdict |
|---|---|
| **ASIA** | **Efficient.** Trend-leaning at the 8-bar horizon (+$0.56, z = 3.86) but it vanishes in FULL. The last hour's momentum (ρ +0.092) survives winsorisation at only z = 2.77 and loses $1,021 when traded across all three thirds. Wednesday effect rejected as a 1-in-60 scan artifact. |
| **LONDON** | **The one real inefficiency, and it is sub-cost.** Afternoon reversal is genuine, body-of-distribution, replicated in both windows, clears Bonferroni. Gross edge $0.197 vs $0.28 cost. Profitable only in T3 at ATR > 9 (n = 150), where regime and ATR are 97% confounded. No mechanism — the LBMA auction explanation is falsified. |
| **OVERLAP** | **Efficient, and the most hostile session.** Most consistently anti-trend cell in the study (persistence z = −4.96 and −5.57), worst breakout failure (83–86%), highest kurtosis (259). Its strong mean-reversion hit rate nets zero. Combined with Phase 1's $10.14 noise floor, this session should be **excluded**. |
| **NY** | **Efficient, and the cheapest.** Best cost-to-range ratio by a wide margin (3.65%). Its two apparent edges — last-hour momentum and up-breakouts — are a tail artifact and a t = 0.64 non-result. Loudest hours IST 18–20. |
| **LATE** | **Efficient and structurally bad.** Negative persistence at both horizons (z = −3.45, −3.50), worst breakout follow-through (−$1.76 on up-breaks), and §8.1 shows ATR14 over-sizes its stops by 1.73×. Its low noise floor is real but ATR-based sizing throws that advantage away. |
| **POSTNY** | **Efficient. Newly characterised — it was invisible to every prior filter.** Genuinely the quietest (median range $3.82) and therefore the smallest achievable stop, but the most expensive per unit of movement (7.33%) and the worst ATR14 distortion (1.95×). Both its autocorrelation cells are tail artifacts. |

### What this means for the program

1. **Do not build a session-specialised directional strategy.** Five candidates
   were generated by an honest scan of 130 tests and all five died. The
   distinguishing feature of every failure is the same: **the effect is smaller
   than the $0.28 round trip.** Adding another directional session filter to a
   candidate is not a promising direction.
2. **Session choice should be made on cost and risk arithmetic, not on edge.**
   The measurements that survived every robustness check are the volatility
   levels, the flat spread, and the cost ratios in §2. Those are the numbers a
   session filter should be built from.
3. **Fix ATR-based stop sizing before any further candidate testing** (§8.1).
   Every session-restricted result in this program that used a rolling-ATR stop
   has mis-sized risk by 1.05×–1.95× depending on session, systematically
   over-risking in exactly the quiet sessions the account depends on.
4. **Exclude OVERLAP** (IST 15:30–17:30): worst microstructure and a $10.14
   noise floor against a $105.74 account.
5. **The only reliably predictable quantity in this instrument is volatility,
   not direction** (§4.6, z = 17–70 in every session, both windows). If anything
   in this report should drive a strategy, it is that — and it points at sizing
   and stop placement rather than at entries.
6. **Re-examine EMA_STACK's premise.** Its stack condition holds 69–77% of the
   time in every session with 0.98–0.99 one-bar survival (§4.7). It is not
   selecting a rare or informative state, so its performance is coming from
   somewhere other than the filter it is named for.

### Honest statement of what would change this conclusion

The London-afternoon reversal is the only finding not fully killed. It would
become credible if: (a) it produced positive net expectancy in a *fourth*,
future, disjoint window at ATR > 9, and (b) a mechanism were identified that is
anchored to 09:15–09:30 UTC. Absent both, it should be recorded as a **measured
sub-cost inefficiency**, not a strategy candidate. Given 150 supporting trades in
a single regime, the prior should be that it is noise.

---

*Phase 2 completed 2026-09-01. Evidence: `scripts/phase2_session_microstructure.py`,
`scripts/phase2_edge_probes.py`, `reports/session_microstructure.json`, all on
`research/data/XAUUSDm_M15.npy` (100,000 bars, 2022-06-07 → 2026-08-31).
Builds on Phase 0 (`reports/PHASE_0_RESEARCH_AUDIT.md`) and Phase 1
(`reports/ACCOUNT_100_USD_FEASIBILITY.md`); does not re-derive the MAE/MFE
excursion profile established there.*
