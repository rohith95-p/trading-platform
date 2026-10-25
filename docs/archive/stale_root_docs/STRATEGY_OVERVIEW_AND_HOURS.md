# Current 6-Strategy Portfolio + Trading Hours Analysis

## 📊 The 6 Strategies (Portfolio V5)

### 1. **TREND_PULLBACK_V5**
- **Backtest:** 4,003 trades, 27.6% WR, PF 1.087, +$1,091
- **Status:** ⚠️ Marginal (lowest PF)
- **Type:** Grid-based pullback
- **Risk:** 0.5 ATR SL / 1.5 ATR TP

### 2. **BB_MEAN_REVERSION_V5**
- **Backtest:** 1,161 trades, 36.0% WR, PF 1.366, +$1,162
- **Status:** ✅ Good
- **Type:** Bollinger Band bounce
- **Risk:** 0.5 ATR SL / 1.5 ATR TP

### 3. **NVMR_TARGET_10_V5**
- **Backtest:** 48 trades, 31.2% WR, **PF 5.667**, +$153
- **Status:** ✅ **ELITE** (best PF!)
- **Type:** New York Mean Reversion
- **Risk:** 0.5 ATR SL / 1.5 ATR TP
- **Note:** Low sample size but elite performance

### 4. **FVG_NY_TIGHT_V5** ⭐
- **Backtest:** 1,793 trades, 25.5% WR, **PF 3.101**, +$3,081
- **Status:** ✅ **ELITE** (highest profit!)
- **Type:** Fair Value Gap (NY session 17:30-21:30)
- **Risk:** 0.5 ATR SL / 1.5 ATR TP
- **Note:** Top earner in portfolio

### 5. **PDHLR_STRATEGY_V5**
- **Backtest:** 464 trades, **23.1% WR**, PF 2.365, +$548
- **Status:** ✅ Strong
- **Type:** Previous Day High/Low Rejection
- **Risk:** 0.5 ATR SL / 1.5 ATR TP
- **Note:** Lowest WR but big wins when it hits

### 6. **NY_LIQUIDITY_EXPANSION_V5**
- **Backtest:** 137 trades, 32.8% WR, **PF 3.030**, +$218
- **Status:** ✅ **ELITE**
- **Type:** NY liquidity breakout
- **Risk:** 0.5 ATR SL / 1.5 ATR TP

---

## ⏰ Current Trading Hours

**Current Window:** 6:00 AM - 9:30 PM IST (15.5 hours)

### Session Breakdown:
- **Pre-London:** 6:00 - 11:30 (5.5 hrs)
- **London Open:** 11:30 - 15:30 (4 hrs)
- **London-NY Overlap:** 15:30 - 17:30 (2 hrs)
- **NY Morning:** 17:30 - 21:30 (4 hrs)

**Owner Rule (2026-09-06):** "No night trades" = 6:00-21:30 IST only

---

## 🎯 Your Proposed Change

### Current: 6:00 AM - 9:30 PM (15.5 hours)
### Proposed: **4:40 PM - 10:00 PM (5.3 hours)**

**Reasoning:** "We're getting trades then anyway"

---

## 📊 Analysis: What Happens If We Shorten Hours

### Trades by Time (Based on Yesterday)

**Tuesday Oct 6 - All 4 trades:**
- 5:45 PM: BB_MEAN_REVERSION (WIN +$9.22)
- 6:43 PM: PDHLR (LOSS -$3.07)
- 7:02 PM: PDHLR (LOSS -$3.17)
- 7:54 PM: FVG_NY_TIGHT (WIN +$10.16)

**All trades were 5:45 PM - 7:54 PM** ✅

---

## 💡 Impact Analysis

### ✅ Pros of 4:40 PM - 10:00 PM:

1. **Tuesday would be identical** - all 4 trades fall in this window
2. **Captures NY session** (17:30-21:30 = 5:30 PM - 9:30 PM)
3. **FVG_NY_TIGHT** (your top earner) is NY-only → fully captured
4. **Less time monitoring** - only 5.3 hours vs 15.5 hours
5. **High activity period** - NY session is most volatile

### ⚠️ Cons of 4:40 PM - 10:00 PM:

1. **Lose London Open trades** (11:30-15:30)
2. **Lose morning setups** (6:00-16:40)
3. **Reduces sample size** - fewer trades = slower validation
4. **Risk concentration** - all eggs in NY session basket

---

## 📈 Backtest Data: Session Performance

From FINAL_6_STRATEGY_METRICS_TABLE.md:

| Session | Trades | PF | Net P&L | Status |
|---------|--------|-----|---------|--------|
| **NY_MORNING (17:30-21:30)** | ~6,200 | **1.306** | **+$5,400** | ✅ **BEST** |
| **LONDON_OPEN (11:30-15:30)** | ~1,400 | 1.153 | +$580 | ✅ Good |

**Key Finding:** NY produces 4.4x more trades and 9.3x more profit than London!

---

## 🎯 Recommendation

### Option 1: Aggressive (Your Proposal)
**Hours:** 4:40 PM - 10:00 PM (5.3 hours)
- **Keep:** NY session (where 80% of profit comes from)
- **Drop:** London, pre-market
- **Risk:** Lower sample size, concentration risk

### Option 2: Conservative (Current)
**Hours:** 6:00 AM - 9:30 PM (15.5 hours)
- **Keep:** Everything
- **More trades:** Faster validation
- **More work:** Longer monitoring

### Option 3: Compromise
**Hours:** 11:30 AM - 10:00 PM (10.5 hours)
- **Keep:** London + NY (captures 95%+ of profit)
- **Drop:** Only pre-London (6:00-11:30)
- **Balance:** Good trade flow + reasonable hours

---

## 📊 Expected Trade Frequency

**Based on backtest (464 days):**

| Window | Est. Trades/Day | Days to 50 Trades |
|--------|-----------------|-------------------|
| **Current (6:00-21:30)** | ~16 trades/day | **3 days** |
| **Proposed (16:40-22:00)** | ~13 trades/day | **4 days** |
| **Compromise (11:30-22:00)** | ~15 trades/day | **3.3 days** |

---

## 💭 My Take

**Your instinct is RIGHT** - NY session (4:40 PM - 10:00 PM region) produces most profits.

**BUT** - you're only 2 days in with 7 total trades. 

**Suggestion:**
1. **Keep current hours for 1 more week** (get to 50 trades)
2. **Track when trades actually happen**
3. **Then make data-driven decision**

If 90% of trades ARE happening 4:40-10:00 PM, then switch!

---

## 🚀 To Implement Your Change

Edit `src/core/market_hours.py`:

```python
# Current:
TRADING_WINDOW_IST = (6.0, 21.5)  # 6:00 AM - 9:30 PM

# Change to:
TRADING_WINDOW_IST = (16.67, 22.0)  # 4:40 PM - 10:00 PM
```

Then restart bot.

---

## ❓ Questions to Answer First

1. **Sample size:** Are you OK with ~13 trades/day vs 16?
2. **Validation:** Can you wait 4 days to hit 50 trades vs 3?
3. **London:** Ready to give up the +$580 from London Open?
4. **Data:** Want to track 1 more week before deciding?

**Your call!** Data supports both approaches.

---

**Created:** 2026-10-08 23:55 IST
**Current Status:** Using 6:00 AM - 9:30 PM window
