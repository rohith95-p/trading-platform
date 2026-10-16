# Research registry — Stage 1 multi-asset screen (2026-10-16)

Script: `scripts/research/multi_asset_screen.py` · raw results: `research/registry/screen_2026-10-16.json` · data: `docs/research/DATA_COVERAGE_2026-10-16.md`

## Protocol (fixed before looking at results)
- 13 pre-registered hypotheses × 6 instruments = 78 tests (75 evaluable). No parameter was tuned after seeing results.
- Splits (chronological): **DEV** data start→2024-12-31, **VALIDATE** 2025-01-01→2026-06-30, **HOLDOUT** 2026-07-01→end (read once, never used to choose).
- Execution (tier 1, conservative): signal on closed bar, entry at next open paying spread, stop-first on ambiguous bars, shorts exit on ask, swap per rollover night from broker swap points, no extra slippage. Results in R.
- Multiple testing: two-sided normal p-values on dev expectancy, Bonferroni and Benjamini–Hochberg q-values across all 75 tests.
- Data: H1 native (EURUSD/GBPUSD trimmed to ≥ 2017-03-01 because earlier 'H1' is one bar/day); gold/others per coverage doc. Crypto trades 7 days.

## Hypotheses

| id | family | hypothesis | params |
|---|---|---|---|
| T1a | trend | Donchian breakout (turtle-style channel breakout), H1 | `{"kind": "donchian", "n": 55, "sl": 2.0, "rr": 3.0}` |
| T1b | trend | Donchian breakout, H1, wider | `{"kind": "donchian", "n": 100, "sl": 3.0, "rr": 3.0}` |
| T2a | trend | EMA50>EMA200 trend + pullback to EMA20 resume, H1 | `{"kind": "pullback", "sl": 1.5, "rr": 2.0}` |
| T2b | trend | EMA50>EMA200 trend + pullback to EMA20 resume, H1, wider | `{"kind": "pullback", "sl": 2.5, "rr": 2.0}` |
| M1a | meanrev | Bollinger(20,2)+RSI(14) 30/70 fade, H1 | `{"kind": "bbfade", "sl": 1.5, "rr": 1.0}` |
| M1b | meanrev | Bollinger(20,2.5)+RSI(14) 25/75 fade, H1 | `{"kind": "bbfade2", "sl": 2.0, "rr": 1.0}` |
| B1a | breakout | Prior-day range breakout (first close beyond prior D high/low), H1 | `{"kind": "pdrange", "sl": 1.5, "rr": 2.0}` |
| B1b | breakout | UTC-day opening-range (first 4h) breakout, H1 | `{"kind": "orb", "sl": 1.5, "rr": 2.0}` |
| V1a | volatility | Squeeze (BB width in lowest 20% of 100 bars) then breakout of 20-bar range, H1 | `{"kind": "squeeze", "sl": 1.5, "rr": 2.5}` |
| V1b | volatility | ATR expansion (ATR14 > 1.5x its 100-bar median) continuation of the bar direction, H1 | `{"kind": "atrexp", "sl": 1.5, "rr": 2.0}` |
| MO1a | momentum | Time-series momentum N=20d, daily | `{"kind": "tsmom", "n": 20}` |
| MO1b | momentum | Time-series momentum N=60d, daily | `{"kind": "tsmom", "n": 60}` |
| MO1c | momentum | Time-series momentum N=120d, daily | `{"kind": "tsmom", "n": 120}` |

## Outcome

- **0 of 75** tests are significantly positive after multiple-testing correction.
- Only 1 test has PF > 1.1 in both DEV and VALIDATE (XAUUSDm T1b, H1 Donchian-100: DEV PF 1.13, t = +0.6; VALIDATE PF 1.97; HOLDOUT PF 1.07 on 17 trades). DEV is not significant → **awaiting evidence**, not accepted.
- **5 of 75** are significantly NEGATIVE: Bollinger/RSI fades on ETH (t −4.8, −3.9), EURUSD (−3.7), BTC (−3.6), USDJPY (−3.1). Fading H1 extremes in crypto/EURUSD loses after costs → **rejected**.
- Median DEV expectancy per instrument: BTC −0.018R, ETH −0.038R, EURUSD −0.071R, GBPUSD −0.037R, USDJPY +0.035R, XAUUSD +0.006R (all inside the noise band).
- Best DEV t-stat among positives: USDJPYm V1a squeeze-breakout t = +2.4 (not significant after correction; VALIDATE PF 1.01, HOLDOUT PF 0.80 on 33 trades) → **rejected**.
- Crypto momentum/trend variants are positive in DEV/VALIDATE only by small margins (PF 1.02–1.18, t ≤ 1.4) and mixed in HOLDOUT (ETH MO1b 1.12, others 0.55–0.79) → **awaiting evidence**.

## Decisions

| status | items |
|---|---|
| Accepted | none |
| Awaiting evidence | XAUUSDm T1b (H1 Donchian-100); XAUUSDm V1a; ETHUSDm MO1b/T1a; BTCUSDm MO1b |
| Rejected | all Bollinger/RSI fades (M1a, M1b) on crypto, EURUSD, USDJPY; USDJPYm V1a; EURUSD/GBPUSD trend, pullback, breakout and momentum variants (median DEV expectancy < 0) |

## Known limits of this screen
- Tier-1 simulation, one position at a time per test, no portfolio interaction, no slippage beyond spread.
- Swap units assumed points/lot/night for every symbol (`swap_mode` 1 reported by the broker; crypto units unverified); weekend triple swap not modeled.
- Exness prices only; Atlas prices/spreads may differ.
- 13 hypotheses are a deliberately small set: the absence of an edge here does not prove none exists, only that these standard rules do not show one.

---

# Stage 1b — slow (H4/D1) screen, 2026-10-16

Script `scripts/research/multi_asset_slow.py` · results `research/registry/slow_2026-10-16.json`. Same splits and BH/Bonferroni protocol. Volatility-targeted (1 %/day per asset), next-open execution, half-spread per unit of turnover, broker swap per night. **61 pre-registered tests** (9 hypotheses × 6 assets, broker-swap carry proxy on 3 FX pairs, 4 portfolio-level tests).

| id | hypothesis |
|---|---|
| S1a–S1d | time-series momentum 20/60/120/250 days (D1) |
| S2a/S2b | EMA 20/100 and 50/200 cross trend (D1) |
| S3a/S3b | Donchian 50/25 (D1) and 120/60 (H4), long+short |
| S4a | TS momentum 60d gated by Kaufman efficiency ratio > 0.25 |
| C1 | broker-swap carry proxy (FX; weak proxy for true interest carry) |
| P1a/P1b | equal-weight portfolio of TS momentum 60d / 120d across the 6 assets |
| P2a/P2b | cross-sectional momentum 60d / 120d: long top-2, short bottom-2 of 6 |

Outcome
- **No test is significant**: minimum Benjamini–Hochberg q across all 61 tests is **0.98**.
- Most significant DEV results are USDJPY (carry proxy t = +2.2, S3b t = +1.9, S1a t = +1.8); all fail VALIDATE/HOLDOUT (USDJPY holdout Sharpe −1.6 to −1.9) and are rejected.
- Median DEV Sharpe by asset: USDJPY +0.73, BTC +0.42, PORTFOLIO +0.29, XAU +0.20, GBP +0.05, ETH +0.02, EUR −0.07: all within noise.
- Gold trend/momentum variants had VALIDATE Sharpe 1.6–2.6 (2025–26 rally) but DEV Sharpe 0.1–0.5 and HOLDOUT −0.2 to −2.4 (Jul–Oct 2026). They are the same regime-dependent trend exposure seen before; **not accepted**.
- Only two items are positive on DEV (Sharpe > 0.3), VALIDATE (> 0.3) and HOLDOUT (> 0): **ETHUSDm S1b** (TS momentum 60d) and **PORTFOLIO P2a** (cross-sectional momentum 60d; DEV t = +0.8, VALIDATE t = +1.4, HOLDOUT Sharpe +0.04 on 92 days). Neither is statistically distinguishable from zero → **awaiting evidence**.
- The July–Oct 2026 holdout (≈ 3.5 months) is negative for almost all trend/momentum variants (equal-weight TS momentum portfolio P1b: Sharpe −3.9, t = −2.2): trend-following has been losing recently.

Decisions: Accepted — none. Awaiting evidence — ETHUSDm S1b, PORTFOLIO P2a. Rejected — all other Stage 1b tests.
Limits: swap carry is a broker-markup proxy, not interest-rate carry; D1 histories are short for gold/JPY/crypto (from 2021-10); daily returns assumed independent in the t-statistics; Exness prices only.
