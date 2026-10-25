# DAILY BATTLE PLAN — 2026-10-09 (IST)

_Generated: 2026-10-09 18:38 IST | Account: REAL | Balance: $175.21_

---

## ⚡ ACCOUNT STATUS

| Field | Value |
|---|---|
| Balance | **$175.21** |
| Equity | $175.21 |
| Free Margin | $175.21 |
| Open Positions | **0** (flat) |
| Daily Loss Cap | **6%** (~$10.51) |
| Hard Kill Threshold | N/A |

---

## 🎯 MARKET CONDITION & BIAS

**D1 EMA20 ≈ 4,218.8 | Current Price ~4,175 → 43 pts BELOW**

> **⚠️ BIAS GATE = SHORT ONLY**
> Price is ~43 points below D1 EMA20 — remaining in a bearish regime.
> ALL long signals must be detected, BLOCKED, and logged.
> This is enforced in code via the D1 bias gate. Verify it's working.

**Macro vs Price Structure:**
- Macro: Oil slumping heavily (-5%), USD flat, yields mixed.
- Price structure: Sharp drop on Oct 7 (-120+ pts) followed by inside consolidation and a squeeze higher today. Still firmly below the major daily moving average.
- **Verdict: Both AGREE — bear trend, short bias.** No conflict today.

**Today's theme:** NY Session liquidity expansions. Wait for sweeps of early H1 highs and short into weakness.

---

## 📐 LIVE LEGS & SESSION SCHEDULE (IST today)

_Currently running `PORTFOLIO_V5` (6 legs)_

| Leg | IST Window | SL × ATR | TP × ATR | H1 ATR ~16pt | SL pts | TP pts |
|---|---|---|---|---|---|---|
| TREND_PULLBACK_V5 | 11:30–21:30 | 0.5 | 1.5 | 16 | ~8 | ~24 |
| BB_MEAN_REVERSION_V5 | **17:30–21:30** ← NOW | 0.5 | 1.5 | 16 | ~8 | ~24 |
| NVMR_TARGET_10_V5 | ALL_DAY | 0.5 | 1.5 | 16 | ~8 | ~24 |
| FVG_NY_TIGHT_V5 | **17:30–21:30** ← NOW | 0.5 | 1.5 | 16 | ~8 | ~24 |
| PDHLR_STRATEGY_V5 | ALL_DAY | 0.5 | 1.5 | 16 | ~8 | ~24 |
| NY_LIQUIDITY_EXPANSION_V5| **17:30–21:30** ← NOW | 0.5 | 1.5 | 16 | ~8 | ~24 |

**At 0.01 lots, 1pt = $0.10 → each SL = ~$0.80 real risk**

---

## 🔑 KEY PRICE LEVELS TO WATCH

| Level | Type | Notes |
|---|---|---|
| **4,218** | 🔴 Resistance | D1 EMA20 Gate Level |
| **4,207** | 🔴 Resistance | Today's H1 high (Liquidity sweep) |
| **4,186** | 🔴 Resistance | Oct 6 supply high |
| **4,175** | ⚪ Current | Now |
| **4,144** | 🟢 Support | Today's open |
| **4,108** | 🟢 Key support | Recent structural low |

**Short setups to watch:**
1. Rejection from 4,186-4,207 area in NY session.
2. FVG fill on 5m/15m aligned with NY_LIQUIDITY_EXPANSION_V5.

**Long signals:** **BLOCKED** per D1 bias gate. Log them.

---

## 📋 TRADE REVIEW (Recent session)

> Full P&L detail in [`LIVE_TRADE_HISTORY.md`](../trade_logs/LIVE_TRADE_HISTORY.md)

- Recent trades around Oct 7: Minor losses and solid TP hits observed in historical deals.
- Bias gate and sizing were respected correctly.
- Hard risk rules (0.5x ATR stops) working smoothly, preserving capital while hunting for the +3R home runs.

---

## 🛡️ HARD RISK RULES FOR TODAY

| Rule | Value | Status |
|---|---|---|
| Lot size | 0.01 | ✅ Fixed |
| Max concurrent positions | 1 (balance <$200 → ladder) | ✅ Enforced via sizing ladder |
| Max total volume | 0.01 | ✅ |
| Daily loss cap | 6% = ~$10.51 | ✅ Fresh |
| D1 bias gate | SHORT ONLY | ✅ |
| Consecutive loss pause | 3 losses → 4h pause | ✅ |

**Bot command:** `python -m src.core.main_loop`

---

## 🕰️ TONIGHT'S WATCH LIST

- **NY Session is currently ACTIVE**.
- Let the algorithms execute. Monitor logs to ensure `D1 GATE: bias=BEARISH` is respected and long signals are blocked.
