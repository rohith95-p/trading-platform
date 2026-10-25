# 📋 Morning Pre-Market Checklist

## What to Check Before Starting Trading Every Day

---

## 🚀 Quick Start (30 seconds)

```bash
cd c:\projects\ultra_core
python scripts\pre_market_check.py
```

This checks everything automatically!

---

## 📊 What Gets Checked:

### ✅ 1. MT5 Connection
- MT5 is running and connected
- Account logged in
- Demo vs Real account confirmed

### ✅ 2. Symbol Status
- XAUUSDm is tradeable
- Current bid/ask spread
- **Warning if spread >$1.00** (normal is $0.20-0.50)

### ✅ 3. Open Positions
- Check for any positions left from yesterday
- Review floating P&L if any exist

### ✅ 4. Bot Status
- Lock file check (is bot already running?)
- Heartbeat freshness
- Safe to start new instance

### ✅ 5. Yesterday's Performance
- Quick P&L from previous day
- Links to full report

### ✅ 6. Market Hours
- Are we in trading window? (6:00 AM - 9:30 PM)
- What session is active now?
- When is peak trading time today?

### ✅ 7. D1 Bias (CRITICAL!)
- **BULLISH or BEARISH?**
- Current price vs EMA20
- **Which trades are allowed today:**
  - BULLISH → BUY allowed, SELL blocked
  - BEARISH → SELL allowed, BUY blocked

### ✅ 8. System Health
- Log file sizes
- Daily reports folder

---

## 📈 Today's Pre-Market Check Results

**Wednesday, October 7, 2026 - 12:12 AM**

### Account Status:
- ✅ Balance: $185.84
- ✅ Equity: $185.84
- ✅ No open positions

### Market Status:
- ✅ XAUUSDm tradeable
- ✅ Spread: $0.24 (normal)
- 🔴 **D1 BEARISH** → SELL trades only

### Yesterday (Tuesday):
- 📈 P&L: +$13.14
- 4 trades (2W-2L)

### System:
- ✅ Bot stopped
- ✅ Ready to start

---

## 🎯 Daily Routine

### Every Morning (Before 6:00 AM):
1. Run pre-market check
2. Review D1 bias
3. Check yesterday's report

### 6:00 AM - Start Trading:
```bash
python -m src.core.main_loop
```

### Throughout Day:
```bash
python scripts\daily_stats.py  # Quick status
```

### End of Day (9:30 PM):
```bash
python scripts\end_of_day.py  # Generate report
```

---

## 🔴 D1 BIAS - Why It Matters

**Current Status: BEARISH**
- Price: $4,134
- EMA20: $4,244
- Gap: $109 below EMA

**What This Means:**
- ❌ BUY signals will be BLOCKED
- ✅ SELL signals allowed
- This is working as designed
- Tuesday: 0 trades until evening because of this gate

**If bias flips to BULLISH:**
- ✅ BUY signals allowed
- ❌ SELL signals blocked

---

## ⚠️ Red Flags to Watch

### Don't Start If:
- ❌ MT5 not connected
- ❌ Symbol not tradeable
- ❌ Spread >$2.00
- ❌ Lock file exists with recent heartbeat

### Warnings (OK to proceed):
- ⚠️ Positions left open (review P&L)
- ⚠️ Outside trading hours (wait for 6:00 AM)
- ⚠️ High spread $1-2 (monitor, may normalize)

---

## 📊 Expected Performance Benchmarks

### Daily Targets:
- **Minimum:** $10/day
- **Average:** $13-18/day (based on 2 days)
- **Trades:** 3-6 per day expected

### Weekly Targets:
- **Minimum:** $50/week
- **Average:** $70-100/week
- **Trades:** 15-30 needed for stats

### Monthly Targets:
- **Minimum:** $200/month
- **Stretch:** $300-400/month
- **Trades:** 100+ for validation

---

## 🔥 Peak Trading Times

### **11:30 AM - 3:30 PM** (London Open)
- Moderate activity
- 2 strategies active
- ~20% of trades

### **5:30 PM - 9:30 PM** (NY Session) 🔥
- **HIGHEST ACTIVITY**
- All 6 strategies active
- ~80% of trades
- **86% of total profit**

### Best times to monitor:
- 5:30 PM - watch for entries
- 6:00 PM - 8:00 PM - peak action
- 9:00 PM - last chances

---

## 💾 Files to Check Daily

```
daily_trade_progress/
  └── YYYY-MM-DD_DayName.md  ← Yesterday's report

logs/
  ├── heartbeat              ← Bot alive?
  ├── main_loop.lock         ← Bot running?
  └── trades/
      └── YYYY-MM-DD.jsonl   ← Today's trades

PROGRESS_COMMANDS.md          ← Quick command reference
```

---

## 🎯 Quick Commands Reference

```bash
# Pre-market check
python scripts\pre_market_check.py

# Start bot
python -m src.core.main_loop

# Quick status
python scripts\daily_stats.py

# End of day
python scripts\end_of_day.py

# View reports
cd daily_trade_progress
dir
```

---

## ✅ Ready to Trade Checklist

- [ ] MT5 connected
- [ ] Pre-market check passed
- [ ] D1 bias confirmed
- [ ] Yesterday's report reviewed
- [ ] No stale lock files
- [ ] Spread is normal (<$1)
- [ ] Time is 6:00 AM or later
- [ ] Computer will stay on

**All checked?** → Start bot!

---

**Created:** 2026-10-09 00:15 IST
**Status:** Ready for Wednesday morning
