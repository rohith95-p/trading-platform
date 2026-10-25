# External Indicators — Assessment

*2026-09-03, rohith-2. Two TradingView Pine scripts the owner flagged:*
*BigBeluga "Market Structure Trend Matrix" and LuxAlgo "Smart Money Concepts".*
*Question: are they useful, and what should be backtested?*

---

## 1. BigBeluga — Market Structure Trend Matrix

### What it actually is
A **structure-break trend-follower with a wide breathing trailing stop.**

- **Entry:** the trend flips BULLISH when `close` crosses *above* the most recent
  confirmed pivot high; BEARISH when `close` crosses *below* the most recent
  confirmed pivot low.
- Pivots use `ta.pivothigh(10, 10)` — a 10-bar lookback **and 10-bar lookahead**,
  so a pivot is only confirmed 10 bars (2.5h on M15) after it forms. Lagging by
  design.
- **Exit:** an ATR trailing stop at **4× ATR(14)**, ratcheting only (never loosens).
- The "infinite targets" at 2×ATR steps are **visual markers, not exits** — the
  script never closes anything at a target. There is no fixed take-profit.

### Verdict
The entry rule is already covered by the candidate library
(`_c_donchian_break`, `_c_bos_retest`, `change_of_character` in
`market_study.py`). The 10-bar lookahead pivot makes it *more* lagging than
what we run.

**The interesting part is the exit.** A 4×ATR trailing stop is the *opposite
end of the spectrum* from the 0.7/0.3×ATR trail that was just removed for
strangling winners (rohith-2, 2026-09-03). A wide "let it breathe, only exit on
a real structure failure" trail is a genuine, untested hypothesis — and exit
geometry is the #1 documented research gap (`REAL_MONEY_READINESS.md` V.2).

**Action:** test a wide ATR trail (2/3/4/5×) against the current fixed TP on the
portfolio_v4 legs. See `scripts/exit_trail_ab.py`.

---

## 2. LuxAlgo — Smart Money Concepts

### What it actually is
~500 lines, of which ~90% is drawing boxes, lines and labels. The tradeable
primitives inside:

| Primitive | Already in codebase? |
|---|---|
| BOS / CHoCH (internal + swing structure breaks) | **Yes** — `change_of_character`, `_c_bos_retest`, `_c_failed_breakout` |
| Fair Value Gaps | **Yes** — `_c_fvg`; size-filtered variant tested 2026-09-03 (PF 1.66 → 2.11) |
| Equal Highs / Lows (liquidity pools) | **Partial** — `_c_liquidity_sweep` covers sweep-and-reverse |
| **Order Blocks** | **NO — genuinely new** |
| Premium / Discount zones | Trivial (= 50% of the swing range). Not worth a candidate. |
| MTF prior high/low levels | Reference only, not a signal |

### Two things worth extracting

**(a) Order Blocks — the one new primitive.**
LuxAlgo's definition, reduced to arithmetic:
- On a bullish structure break, the **bullish OB** is the candle with the lowest
  low in the run from the last pivot to the break (using volatility-parsed lows).
- On a bearish break, the **bearish OB** is the candle with the highest high in
  that run.
- The OB is "mitigated" (removed) when price closes back through it.
- Volatility filter: on a bar where `range ≥ 2× ATR(200)`, the high and low are
  *swapped* for OB detection — this rejects blow-off bars from defining an OB.

Two ways to test it:
1. **As an entry trigger** — enter when price returns to an unmitigated OB in the
   direction of the structure (mean-reversion-to-imbalance).
2. **As a confluence filter** on the existing legs — only take a signal if it
   fires inside / near an unmitigated same-direction OB.

**(b) Volatility-swapped pivot detection.**
`highVolatilityBar = (high-low) >= 2*ATR(200)` → then use the *opposite* extreme
for that bar. A cheap, sensible noise-rejection trick. Worth adopting in the
shared pivot helper (`market_study.py`) regardless of the rest — it makes every
structure-based candidate slightly more robust to spikes.

### Verdict
No reason to port the indicator. Extract **order blocks** as a candidate and
**vol-swapped pivots** as a helper improvement. Everything else LuxAlgo draws,
the library already computes.

---

## 2b. Built so far (rohith-2, 2026-09-03)

- **`src/research/structure.py`** — BigBeluga logic as backward-looking
  arithmetic: `compute()` returns per-bar confirmed pivot levels, the binary
  trend state, BOS/CHoCH events, and distance-to-pivot. `trend_series()` for
  gate use. Vol-swap option included.
- **Engine `direction_gate` option** (`src/backtesting/engine.py`) —
  `"d1_ema20"` (default, unchanged) / `"d1_ema10"` / `"structure"` / `"both"`.
- **Order blocks** — `structure.compute()` now tracks the most recent
  unmitigated bullish/bearish OB (LuxAlgo definition: origin candle of the move
  that broke structure, parsed-low/high, mitigated on a close through the far
  edge).
- **Candidates** added: `XAU-121..126` Structure CHoCH (trend flip),
  `XAU-127..132` Structure BOS (continuation), `XAU-133..138` Order block retest.
- Scripts: `direction_gate_ab.py`, `exit_trail_ab.py`, `structure_screen.py`.

### Frequencies (last 600 M15 bars, ~6 weeks)
- Structure CHoCH: ~9 fires (rare — the flip is infrequent, and late)
- Order block retest: ~33 fires (~1.4/day, mostly long in this bull-ish stretch)

### Live check (last 5 days, M15)
The module printed a bearish BOS chain through the 2026-09-02 morning downtrend,
then a **bullish CHoCH at 17:15** (close 4332) as the NY reversal began. The D1
EMA20 gate stayed BEARISH and blocked longs for another ~5 hours. Structure saw
the turn first. Whether that generalises is what `direction_gate_ab.py` measures.

## 2c. Reframe (owner, 2026-09-03): CONFLUENCE, not entries

The owner's intent is that these tools **support** a trade taken by an existing
leg — confirm or veto it — not fire their own. So the standalone candidates
(XAU-121..138) are secondary. The real questions:

1. **Structure trend as a filter** on the 4 legs — only take a leg's signal if
   the M15 structure trend agrees. (`direction_gate_ab.py`, `direction_gate="structure"`.)
2. **Order block as a filter** — only take a signal if price is at/near an
   unmitigated same-direction order block. (`confluence_ab.py`.)
3. Both together.

`scripts/confluence_ab.py` wraps each leg with a veto: baseline vs +structure
vs +order-block vs +both. Leg entry rules unchanged.

## RESULTS (2026-09-03) — everything from these indicators makes the system worse

100-day window, all 4 legs, one shared account, 0.01 lots, realistic costs,
6% breaker. **Baseline (frozen live config): PF 1.478, net $843, maxDD 21.4%.**

### Exit — BigBeluga trailing style (`exit_trail_ab.py`)
| Exit | PF | Net | maxDD |
|---|---|---|---|
| **FROZEN fixed per-leg TP, no trail** | **1.478** | **$843** | **21.4%** |
| trail 2.0×ATR + keep TP | 1.320 | $452 | 30.5% |
| trail 3.0×ATR + keep TP | 1.266 | $378 | 40.1% |
| trail 4.0×ATR + keep TP | 1.422 | $702 | 25.1% |
| trail 3.0×, no fixed TP (pure BigBeluga) | 1.282 | $395 | 40.1% |
| trail 4.0×, no fixed TP (pure BigBeluga) | 1.422 | $702 | 25.1% |

Every trail loses to the fixed TP. 4× only *approaches* baseline because it
rarely fires before the target — the best trail is the one that does nothing.

### Direction gate (`direction_gate_ab.py`)
| Gate | n | PF | Net | maxDD |
|---|---|---|---|---|
| **D1 EMA20 (current live)** | 330 | **1.478** | **$843** | **21.4%** |
| D1 EMA10 (faster daily) | 324 | 1.403 | $712 | 30.5% |
| D1 EMA20 AND M15 structure | 194 | 1.304 | $332 | 45.5% |
| M15 structure trend (len 10) | 14 | 0.327 | −$96 | 90.7% |
| no gate | 39 | 0.767 | −$90 | 87.7% |

The slow D1 EMA20 is the best gate by a wide margin. Faster = worse. Structure
= catastrophic (vetoes 96% of signals). "No gate" only yields 39 trades because
without it the 6% breaker trips nearly every day.

### Order block / structure as a confluence filter (`confluence_ab.py`)
| Filter on the 4 legs | n | PF | Net | maxDD |
|---|---|---|---|---|
| **baseline (no filter)** | 330 | **1.478** | **$843** | **21.4%** |
| + M15 structure trend agrees | 194 | 1.304 | $332 | 45.5% |
| + price near an unmitigated order block | 18 | 0.912 | −$12 | 41.2% |
| + structure AND order block | 13 | 1.164 | $17 | 19.3% |

The OB filter vetoes 95% of signals. n=13–18 is statistical noise. Nothing here
helps.

### Conclusion
**Do not wire any of this into the live system.** Not the trail, not the
structure gate, not the order-block filter. Every configuration tested loses to
the frozen config, most of them badly. The frozen config
(D1 EMA20 gate, per-leg fixed SL/TP, no trailing, no confluence) is now
**validated by exclusion** — a broad search of structure-based alternatives
found nothing better.

### What was still worth doing
1. `src/research/structure.py` — a clean, backward-looking, A/B-able
   implementation of market structure. Reusable for any future structure
   hypothesis instead of eyeballing charts.
2. Confirmation that the rohith-2 exit decision (kill trailing) was right — a
   wide trail is no better than a tight one for these legs.
3. The vol-swapped pivot trick and the fast/slow (internal/swing) structure
   split from LuxAlgo are noted for future use, untested.

The BigBeluga / LuxAlgo indicators remain useful as a **human analysis lens**
(what is the structure, where are the swings, is this a BOS or a CHoCH) — just
not as inputs to the bot's decisions.

## 3. (superseded) What to backtest — priority order

1. **Wide ATR trailing exit** (2/3/4/5×) vs current fixed TP, all 4 legs, on the
   validation window. Fills the #1 gap; both indicators point here.
   → `scripts/exit_trail_ab.py`
2. **Order Block entry candidate** — add `_c_order_block` to the library, run it
   through the standard screen + random-entry control.
3. **Order Block as a confluence filter** on FVG_NY and EMASTACK_LONDON.
4. **Vol-swapped pivots** in `market_study.py` — re-run the structure-based
   candidates before/after, check robustness didn't drop.

**None of this touches the frozen live config.** It is research for after the
Thu/Fri evaluation.

---

## 4. What NOT to do

- Do not port either indicator wholesale.
- Do not add premium/discount zones, MTF level lines, or the equal-H/L display —
  no edge, just chart furniture.
- Do not stack order blocks + FVG + CHoCH + equal-H/L into one mega-filter. The
  research is explicit (rule `strategy_design.md`): > 2–3 aligned conditions
  destroys frequency and lags entries. Test each primitive alone first.
