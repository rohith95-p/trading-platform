# Phase 1 — $100 / 0.01-Lot Feasibility (2026-09-01)

All figures derived from the **live broker specification**, queried from
Exness-MT5Trial11 on 2026-09-01. No generic XAUUSD assumptions are used.

**Headline: the prior conclusion that "0.01 lot forces 15–20% risk per trade"
was wrong.** It was an artifact of assuming a 1.5×ATR stop, not a property of
the lot size. The broker imposes **no minimum stop distance**, so risk per
trade is a *strategy design choice*, not a constraint. This materially changes
what is feasible — see §3.

---

## 1. Verified contract specification

| Property | Value |
|---|---|
| Symbol | XAUUSDm (plain XAUUSD does not exist on this server) |
| Contract size | 100 oz |
| Tick size / tick value | 0.001 / $0.10 per 1.00 lot |
| Min lot / step | **0.01 / 0.01** (0.001 lots are NOT available) |
| **Stops level** | **0 — broker imposes no minimum stop distance** |
| Freeze level | 0 |
| Spread (current / median historical) | 260 pts = $0.26 / 200 pts = $0.20 |
| Leverage | 200 |
| Swap long / short | **−515.5 / 0.0** → −$0.52 per night per 0.01 lot on longs |
| Balance | $105.74 |
| Price at audit | 4427.84 |

### The core arithmetic
`0.01 lot × 100 oz = 1 oz` → **$1 of risk per $1 of stop distance.** A $6 stop
risks exactly $6. This is clean, unavoidable, and the basis of everything below.

### Two constraints not previously documented

**Margin caps concurrent positions at 4.** Margin per 0.01 lot =
(1 oz × $4,428) / 200 = **$22.14**. On $105.74 free margin that is **4
positions maximum**, assuming zero floating loss. A "max 3 concurrent" policy
sits at the edge of this limit, not comfortably inside it.

**Longs bleed overnight, shorts do not.** −$0.52/night per 0.01 lot on longs
is ~0.5% of this account per night. Any multi-day long hold is structurally
penalised; shorts are free. No backtest to date has modelled this.

---

## 2. Risk and breakeven tables

Cost assumption: $0.26 spread + $0.02 slippage = **$0.28 round-trip per trade**.

| Stop | Risk $ | % of $105.74 | Cost as % of stop | BE win rate @1:1 | @1:2 | @1:3 |
|---:|---:|---:|---:|---:|---:|---:|
| $1 | $1.00 | 0.9% | **28.0%** | 64.0% | 42.7% | 32.0% |
| $2 | $2.00 | 1.9% | 14.0% | 57.0% | 38.0% | 28.5% |
| $3 | $3.00 | 2.8% | 9.3% | 54.7% | 36.4% | 27.3% |
| $5 | $5.00 | 4.7% | 5.6% | 52.8% | 35.2% | 26.4% |
| $7.50 | $7.50 | 7.1% | 3.7% | 51.9% | 34.6% | 25.9% |
| $10 | $10.00 | 9.5% | 2.8% | 51.4% | 34.3% | 25.7% |
| $15 | $15.00 | 14.2% | 1.9% | 50.9% | 34.0% | 25.5% |
| $20 | $20.00 | 18.9% | 1.4% | 50.7% | 33.8% | 25.4% |
| $30 | $30.00 | 28.4% | 0.9% | 50.5% | 33.6% | 25.2% |

**Reading it:** stops below ~$3 are destroyed by spread (cost ≥ 9% of the
stop). Above ~$10 the cost drag becomes negligible but the account risk becomes
severe. **The workable band is roughly $5–$10 (4.7%–9.5% of account).**

### Minimum balance required per risk target

| Stop | for 10% | 5% | 3% | 2% | 1% |
|---:|---:|---:|---:|---:|---:|
| $3 | $30 | $60 | $100 | $150 | $300 |
| $5 | $50 | $100 | $167 | $250 | $500 |
| $10 | $100 | $200 | $333 | $500 | $1,000 |
| $15 | $150 | $300 | $500 | $750 | $1,500 |
| $21 | $210 | $420 | $700 | $1,050 | $2,100 |

At $105.74, a **$5 stop = 4.7% risk** and a **$3 stop = 2.8% risk** are both
achievable *today*, without any change to lot size. Conventional 1–2% risk
requires $250–$500 of balance at a $5 stop.

---

## 3. The critical question: what is the smallest *statistically valid* stop?

A tight stop is only useful if it sits **outside routine market noise**.
Measured the adverse excursion (MAE) distribution from entry-at-next-open over
the following 4 hours, by session, on recent M15 data (~21k sampled entries):

| Session (IST) | n | MAE p25 | **MAE p50** | MAE p75 | MFE p50 | **MFE/MAE** |
|---|---:|---:|---:|---:|---:|---:|
| ASIA (02:30–11:30) | 8,132 | $2.24 | **$5.77** | $13.72 | $6.23 | 1.08 |
| LONDON (11:30–15:30) | 4,080 | $2.69 | **$6.55** | $13.55 | $6.97 | 1.06 |
| OVERLAP (15:30–17:30) | 2,040 | $4.31 | **$10.14** | $21.36 | $10.29 | 1.01 |
| NY (17:30–21:30) | 4,074 | $3.72 | **$8.69** | $18.83 | $8.71 | 1.00 |
| LATE (21:30–24:00) | 2,531 | $2.26 | **$5.16** | $12.05 | $5.53 | 1.07 |

### Finding A — no session offers free asymmetry
**MFE/MAE ≈ 1.00–1.08 everywhere.** From a random entry, favourable and adverse
excursions are near-symmetric in every session. There is no "easy" session where
the market simply pays you more than it takes. **Any edge must come from entry
timing/selection, not from session choice alone.** This is a strong null result
and it constrains every hypothesis in Phases 2–3.

### Finding B — the noise floor differs sharply, and this is what a small account cares about
Because risk in dollars *is* the stop distance, the session with the smallest
noise floor permits the smallest viable stop, hence the lowest % risk:

| Session | Min viable stop (≈MAE p50) | Risk as % of $105.74 |
|---|---:|---:|
| **LATE (21:30–24:00)** | ~$5–6 | **~5%** |
| **ASIA** | ~$6–7 | **~6%** |
| LONDON | ~$7–8 | ~7% |
| NY | ~$9–11 | ~9–10% |
| OVERLAP | ~$10–13 | ~10–12% |

**The $100 account structurally favours the QUIET sessions — Asia and late
evening — not London/NY.** This is the opposite of conventional retail advice,
and it follows directly from the fact that this account's risk is denominated
in dollars of stop distance rather than in percent of a large balance.

It also retroactively explains why EMA_STACK's unrestricted 24h version beat
every session-restricted variant in prior testing: the Asia hours contribute
trades at roughly *half* the dollar risk of NY/Overlap trades.

---

## 4. Answers to the Phase 16 questions (asked early, since they are now answerable)

**Q1 — Can a $100 account trade XAUUSDm safely at 0.01 lot?**
**Conditionally yes**, which reverses the prior finding. It requires a stop in
the **$5–$10** band (4.7%–9.5% risk), which is only statistically valid in
**Asia or late-evening** sessions where the noise floor is ~$5–6. It is *not*
safely possible with 1.5×ATR stops at current volatility ($15 = 14.2%), and not
possible at all in the Overlap session (noise floor ~$10 = 10%+ risk).

**Q2 — Minimum balance for a given risk target** (at a $5 stop, the tightest
statistically valid): 10% → $50 · 5% → $100 · 3% → $167 · 2% → $250 · 1% → $500.
The account is *already* at the 5%-risk threshold today; conventional 1–2% risk
needs $250–$500.

**Q3 — Smallest statistically valid stop distance:** ~**$5–6**, available only
in the LATE (21:30–24:00 IST) and ASIA sessions. Below ~$3, spread alone
consumes ≥9% of the stop and the required breakeven win rate becomes unrealistic.

**Q4 — Best expectancy after true 0.01-lot economics:** *Not yet answerable.*
All prior candidate rankings are invalidated by Phase 0 Finding 1 (M1 data was
excluded, inflating profit factor ~24% and net profit ~3×). Must be re-measured.

**Q5 — Probability of ruin:** *Not yet answerable* for the same reason. Prior
survivability numbers are upper bounds, not measurements.

**Q6 — Probability of growth within drawdown limits:** *Not yet answerable.*

---

## 5. Hard constraints this program must design around

1. **M1 data begins 2026-05-20 and the broker serves no more** (verified by
   direct request at 1/2/3 years back — all return the same wall). Execution-
   realistic validation is permanently capped at **~3.5 months**. Multi-year
   walk-forward at true fidelity is **impossible**; longer studies are
   M15-resolution and inflate results.
2. **0.001 lots do not exist.** 0.01 is the floor; no sub-minimum sizing.
3. **Max 4 concurrent positions** by margin, at current price.
4. **Volatility has doubled** (mean TR 4.67 full-history vs 10.03 recent), so
   historical results were generated under roughly half of today's dollar risk
   per ATR-based stop.
5. **Long swap −$0.52/night**, short swap $0.00 — unmodelled in all prior work.

---

## 6. What this changes about the research direction

The prior program searched for strategies and then asked whether the account
could survive them. **The correct order is the reverse:** the account can only
tolerate a $5–$10 stop, that stop is only valid in the low-noise sessions, and
therefore the search space should be **constrained up-front** to:

- **Sessions:** Asia (02:30–11:30) and Late (21:30–24:00) IST primarily;
  London secondarily; NY/Overlap only if a strategy demonstrates edge large
  enough to justify ~10% risk per trade.
- **Stops:** $5–$10, i.e. roughly 0.5×–1.0×ATR at current volatility, *not*
  the 1.5×ATR convention inherited from the live system.
- **Reward:risk:** ≥1:2 required — at 1:1 the breakeven win rate is >52%, which
  the MFE/MAE≈1.0 finding says the market does not hand out for free.
- **Direction bias:** shorts are structurally cheaper to hold (no swap).
- **Frequency:** low. At 5% risk per trade, a 6-trade losing streak is −30%.

---

*Phase 1 completed 2026-09-01. Evidence: live MT5 terminal query,
`research/data/XAUUSDm_M15.npy` (100k bars), noise-floor measurement over
~21k sampled entries. Supersedes HYP-015 and HYP-024, both of which
generalised a 1.5×ATR assumption into a false claim about the lot size.*
