# 22-Year XAUUSD Market Study — how gold has actually behaved

*2026-09-08. Built from the Kaggle `XAU_1m` import (2004-06-11 → 2026-02-27),
resampled to M15: 496,556 bars, price $384 → $5,193 (13.5×).*
*Companion to `D1_MARKET_STUDY.txt` (that one is D1 macro relationships from
Yahoo futures; this one is the intraday character of the price itself).*

**Data health warning.** This is a retail feed. The `spread` column is empty
(all zeros) — there is no bid/ask and no swap in this data, so any "profit"
computed on it is gross. Volume is tick-count, not contracts. **2004–2005 is
unreliable**: M15 lag-1 autocorrelation is −0.14 / −0.06 and follow-through is
31–34%, wildly outside the −0.01 / ~47% that every other year sits at — the
early bars look reconstructed from sparse data. Treat everything before 2006 as
indicative only.

---

## 1. The big picture — six regimes in 22 years

Gold compounded at **~12.7%/yr** over the full stretch, but it did *not* get
there smoothly. It moved in long directional phases separated by multi-year
reversals:

| Phase | Window | Move | CAGR | What drove it |
|---|---|---|---:|---|
| **Secular bull I** | 2004-06 → 2011-09 | $383 → $1,820 | **+24%/yr** | post-dotcom easing, weak USD, China/India demand, GFC |
| **The bear** | 2011-09 → 2015-12 | $1,820 → $1,063 | **−12%/yr** | taper tantrum, strong USD, disinflation |
| **Basing** | 2015-12 → 2018-08 | $1,063 → $1,195 | +4.5%/yr | range, no trend |
| **Bull II** | 2018-08 → 2020-08 | $1,195 → $1,948 | **+28%/yr** | trade war, rate cuts, COVID panic |
| **Consolidation** | 2020-08 → 2022-11 | $1,948 → $1,770 | −4%/yr | reopening, Fed hiking cycle |
| **Bull III (melt-up)** | 2022-11 → 2026-02 | $1,770 → $5,023 | **+38%/yr** | central-bank buying, de-dollarisation, 2025 +64.5% |

**Takeaway for system design:** gold spends years trending, then *whipsaws
hard* at the turns (2011, 2020, 2022). A trend-follower makes its money in the
phases and gives a chunk back at every inflection; a mean-reverter is on the
wrong side for years at a stretch. Neither is "always on."

---

## 2. Year by year

| yr | close $ | ret % | rlz vol % | max DD % | efficiency (ER) | med M15 ATR $ | ATR % |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2006 | 636 | +23.1 | 24.9 | −25.0 | 0.01 | 0.95 | 0.16 |
| 2007 | 832 | +30.3 | 17.1 | −8.5 | 0.02 | 0.80 | 0.12 |
| 2008 | 867 | +3.1 | **33.7** | **−33.5** | 0.00 | 1.88 | 0.21 |
| 2009 | 1098 | +25.6 | 22.1 | −13.7 | 0.01 | 1.53 | 0.16 |
| 2010 | 1408 | +28.8 | 17.7 | −9.5 | 0.02 | 1.57 | 0.13 |
| 2011 | 1564 | +10.5 | 21.6 | −20.6 | 0.00 | 2.33 | 0.15 |
| 2012 | 1675 | +6.8 | 15.2 | −14.6 | 0.00 | 1.82 | 0.11 |
| 2013 | 1208 | **−27.8** | 20.0 | −30.2 | 0.02 | 1.90 | 0.14 |
| 2014 | 1187 | −3.1 | 14.2 | −18.4 | 0.00 | 1.34 | 0.11 |
| 2015 | 1061 | −10.5 | 14.9 | −19.8 | 0.01 | 1.28 | 0.11 |
| 2016 | 1151 | +8.2 | 15.9 | −18.3 | 0.00 | 1.51 | 0.12 |
| 2017 | 1302 | +13.2 | **10.4** | −8.8 | 0.01 | 1.06 | 0.08 |
| 2018 | 1280 | −2.3 | **9.9** | −14.9 | 0.00 | 1.05 | 0.08 |
| 2019 | 1520 | +18.5 | 12.1 | −7.0 | 0.01 | 1.18 | 0.08 |
| 2020 | 1893 | +24.6 | 20.4 | −14.7 | 0.01 | 2.60 | 0.15 |
| 2021 | 1828 | −4.2 | 14.6 | −14.3 | 0.00 | 1.93 | 0.11 |
| 2022 | 1824 | −0.3 | 15.2 | −21.9 | 0.00 | 2.13 | 0.12 |
| 2023 | 2063 | +13.0 | 13.2 | −12.0 | 0.01 | 1.90 | 0.10 |
| 2024 | 2625 | +27.1 | 14.3 | −8.8 | 0.02 | 2.73 | 0.11 |
| 2025 | 4318 | **+64.5** | 23.8 | −11.0 | 0.03 | 4.77 | 0.14 |
| 2026* | 5193 | +19.9 | **41.6** | −20.3 | 0.03 | **10.80** | **0.22** |

*2026 = Jan–Feb only.*

- **Efficiency ratio never exceeds 0.03.** ER = |net move| / |sum of all
  moves|. Even in the biggest trend years, gold takes a hugely inefficient path
  — 97%+ of the M15 movement is noise around the drift. This is the single most
  important number in the study for a small-account system: **there is very
  little clean intraday trend to capture.**
- **Volatility is regime-dependent and rising.** The 2017–2019 lull (rlz vol
  ~10–12%, ATR 0.08% of price) is a different market from 2008, 2020, or 2026
  (20–42%). ATR % of price ranges 0.08% → 0.22% — a fixed ATR-multiple stop
  automatically adapts, a fixed-dollar stop does not.
- **2025–2026 is an outlier in magnitude, not character.** +64.5% then a
  volatile +20% in eight weeks; ATR went from ~$2.70 to ~$10.80. Any $-based
  parameter tuned pre-2025 is now mis-scaled.

---

## 3. Drawdown anatomy (how deep, how long)

| Peak → trough | Depth | Underwater |
|---|---:|---:|
| 2011-09 → 2015-12 (recovered 2020-07) | **−44.6%** | **2,748 trading days (~11 yr)** |
| 2008-04 → 2008-11 (recovered 2009-09) | −29.7% | 427 days |
| 2006-05 → 2006-10 (recovered 2007-09) | −22.4% | 402 days |
| 2022-06 → 2022-11 (recovered 2023-12) | −20.9% | 442 days |
| 2020-11 → 2021-03 (recovered 2022-03) | −18.1% | 398 days |

Gold's own worst drawdown was **−44.6% and stayed underwater for a decade**.
Buy-and-hold on gold is not a low-risk benchmark. But note: the *intraday*
drawdowns a stopped-out strategy faces are far smaller and faster — the
−20–30% moves play out over months, giving a daily/weekly system plenty of
warning if it watches trend.

---

## 4. Intraday structure — where the movement is

Median M15 range and volume share by IST hour (all years):

| IST hour | session | med M15 range $ | |ret|/bar bp | vol share |
|---|---|---:|---:|---:|
| 05–12 | **Asia** | ~0.90–1.15 | ~4.5–5.5 | 16% |
| 12–17 | **London** | ~0.85–1.55 | ~4.2–7.2 | 19% |
| 17–24 | **NY** | **1.35–2.73** | **6.3–12.6** | **44%** |
| 00–05 | late-NY | ~1.1–1.8 | ~5.8–8.5 | 21% |

- **NY (17:00–24:00 IST) is where gold lives** — 44% of all volume, ~2× the
  per-bar range of Asia, and the widest bars of the day at 21:00–23:00 IST
  (COMEX afternoon / US data reaction). This is *why* the live FVG legs are
  NY-session — correct instinct.
- **Asia is quiet and small.** Ranges under $1 on M15. A fixed spread/cost is a
  much bigger fraction of the move here — Asia strategies fight a structural
  cost headwind.
- **Mean drift per hour is ~0 bp everywhere** (largest is +1.2 bp at 06:00 IST,
  on thin volume — noise). Gold has no reliable time-of-day directional bias.

### Follow-through by session

| Session | follow-through % (sign of next M15 = sign of this M15) |
|---|---:|
| Asia | 46.2% |
| London | 47.0% |
| NY | 46.5% |
| late-NY | 45.5% |

**Every session is < 50%.** M15 gold is *mildly mean-reverting bar-to-bar in
every session* — a move is slightly more likely to be followed by a reversal
than a continuation. There is no session where momentum "turns on."

---

## 5. M15 autocorrelation by year — the coin-flip, confirmed over 22 years

| period | lag-1 autocorr | follow-through % |
|---|---:|---:|
| 2006–2010 | −0.02 to −0.03 | 42–47% |
| 2011–2019 | −0.01 to −0.03 | 47–48% |
| 2020–2024 | ≈ −0.01 | 47–48% |
| 2025 | +0.002 | 48.9% |
| 2026 | **+0.044** | 48.8% |

- For 20 straight years, M15 gold returns have **near-zero (slightly negative)
  autocorrelation** and **47–48% follow-through**. This is the same result the
  earlier M15 and D1 studies found, now confirmed across every regime including
  2008 and 2020. **Mechanical M15 trend-continuation entries do not have a
  structural edge — the tape does not follow through.**
- 2026 shows the *first* positive lag-1 autocorrelation in the sample (+0.044).
  It is one year, in the most extreme melt-up in gold's history, and
  follow-through is *still* below 50%. Not a signal to trade — a flag to watch
  whether the melt-up regime has genuinely different microstructure.

---

## 6. Seasonality (23 Januaries, so: weak evidence)

| month | mean C2C % | median % | positive years |
|---|---:|---:|---:|
| **Jan** | **+3.51** | +3.76 | 15/22 |
| Feb | +1.44 | +1.93 | 13/22 |
| Apr | +1.90 | +1.50 | 14/21 |
| Aug | +1.71 | +1.36 | 14/22 |
| **May** | −0.34 | **−1.17** | 9/21 |
| **Sep** | +0.08 | **−1.28** | 10/22 |

January is genuinely strong (15/22 up, +3.5% mean), and May/September are soft.
But this is ~22 observations per month with no multiple-testing correction —
consistent with the D1 study's verdict: **suggestive, not tradeable on its
own.** Could be a tie-breaker filter, never a signal.

Day-of-week: nothing. Mean per-bar return is 0.00–0.10 bp Mon–Fri, ranges are
flat across the week.

---

## 7. Gap behaviour

Daily open vs prior close: **mean |gap| 0.11%, median 0.067%**. Only 2.7% of
days gap more than 0.5%, 0.7% more than 1%. Gold trades ~23h/day and the
weekend gap is small. **Overnight/weekend gap risk is low** — a system that
flattens for the weekend is giving up very little, and holding through is not
especially dangerous on gap alone (the danger is Sunday-open trend shock, not
measured here).

---

## 8. What this means for the $100-account mission

**Confirmed dead ends (don't re-test):**
1. M15 trend-continuation / breakout — 22 years of sub-50% follow-through,
   near-zero autocorrelation, every regime. This is the strongest negative
   result in the repo now.
2. Intraday time-of-day directional bias — none exists.
3. Asia-session strategies on a cost-bearing account — the moves are too small
   relative to any realistic spread.

**Where the structure genuinely is:**
1. **NY session** concentrates 44% of volume and the widest ranges. If anything
   intraday works, it works here. (The live FVG NY legs are correctly located;
   their problem per `SYSTEM_FAULTS.md` is edge/size, not session.)
2. **Long D1 trend phases** are real and last years — but they whipsaw at the
   turns and the direction gate lags exactly there (`SYSTEM_FAULTS.md` §2).
3. **ATR-multiple sizing adapts across the 0.08%→0.22% vol range; fixed-dollar
   does not.** Re-tune any $-based parameter — 2025–26 tripled ATR.

**The uncomfortable core finding:** efficiency ratio never breaks 0.03 in 22
years. Intraday gold is ~97% noise. A fixed-0.01-lot account that pays spread on
every entry is trying to extract a signal from a series that is, by this
measure, almost pure noise intraday. The edge — if there is one for this
account — is more likely on the **D1 timeframe with a macro driver** (the DXY
lead/lag test in `D1_SYSTEM_PLAN.md`) than anywhere in the intraday tape.

---

*Regenerate: `python scripts/d1_study/intraday_22yr_study.py` (script archived with this
study). Phase CAGRs and drawdown table from the same M15 series.*
