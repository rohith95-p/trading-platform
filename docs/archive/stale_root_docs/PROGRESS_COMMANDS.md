# ðŸ“Š Progress & Status Commands

## ï¿½ DAILY REPORTS (NEW - Automated!)

### End of Day Report (Run This Every Night!)
```powershell
python scripts/end_of_day.py
```
**Auto-generates complete markdown report:**
- âœ… Starting/ending balance (prevents confusion!)
- âœ… All trades with exact times & strategies
- âœ… Win rate, profit factor, P&L breakdown
- âœ… Saved to `daily_trade_progress/YYYY-MM-DD_DayName.md`

### Generate Report for Any Date
```powershell
python scripts/generate_daily_report.py 2026-10-06
```

### View All Reports
```powershell
cd daily_trade_progress
dir
```

---

## ï¿½ðŸ”¥ ELITE METRICS - 0.5/1.5 CONFIG (4.2 Years)

### Core Performance
- **Calmar Ratio:** 31.62 (Excellent! Target >0.5)
- **Omega Ratio:** 1.181 (Profitable, Target >1.0) 
- **Sortino Ratio:** 0.152 (Weak! Target >1.0) âŒ
- **Recovery Factor:** 5.93 (Good! Target >3.0)

### What These Mean:
- **Calmar = 31.62:** You make 31.62% return per 1% of max DD risk (Elite!)
- **Omega = 1.181:** For every $1 lost, you gain $1.18 (barely profitable)
- **Sortino = 0.152:** Low reward vs downside volatility (high losing variance)
- **Recovery = 5.93:** You make 5.93x your worst drawdown (fast recovery)

---

# ðŸ“Š Progress & Status Commands
# ðŸ“Š Progress & Status Commands

## Quick Commands Reference

### ðŸ”¥ Most Used

**Full Daily Stats** (Shows everything: P&L, Win Rate, PF, DD, Positions):
```powershell
python scripts/daily_stats.py
```

**Quick Status** (Just P&L and positions):
```powershell
python scripts/quick_status.py
```

**Account Balance Only**:
```powershell
python check_account.py
```

---

## What Each Command Shows

### `daily_stats.py` - Complete Report
Shows:
- âœ… Balance & Equity
- âœ… Day P&L & Return %
- âœ… Open Positions & Floating P&L
- âœ… Total Trades, Wins, Losses
- âœ… Win Rate
- âœ… Profit Factor
- âœ… Current & Max Drawdown
- âœ… Current Session
- âœ… End of Day Summary (after 10 PM)

**Use this when:** You want the complete picture

---

### `quick_status.py` - Fast Snapshot
Shows:
- Balance
- Day P&L
- Open Positions
- Floating P&L

**Use this when:** You just want to check if you're making money

---

### `check_account.py` - Account Info Only
Shows:
- Balance
- Equity
- Floating P&L
- Open Positions Count

**Use this when:** You just want raw account numbers

---

## ðŸ“… Weekly & Monthly Reports

**Weekly Review** (Run every Friday):
```powershell
python scripts/weekly_review.py
```

**Monthly Summary**:
```powershell
python scripts/monthly_summary.py
```
*(Will create this if needed)*

---

## ðŸ” Market & System Checks

**Check Spread**:
```powershell
python scripts/check_market_status.py
```

**Pre-Flight Check** (Before starting):
```powershell
python scripts/pre_flight_check.py
```

**Bot Heartbeat** (Check if bot is alive):
```powershell
cat logs/heartbeat
```

---

## ðŸ’¡ Pro Tips

1. **Alias for Quick Access** (Add to PowerShell profile):
```powershell
function stats { python c:\projects\ultra_core\scripts\daily_stats.py }
function status { python c:\projects\ultra_core\scripts\quick_status.py }
```

2. **Check Progress Every Few Hours**:
- Morning: `quick_status.py`
- Afternoon: `daily_stats.py`
- Night: `daily_stats.py` (full summary)

3. **End of Day Routine**:
```powershell
python scripts/daily_stats.py
# Review if target met
# Check win rate and PF
# Plan for tomorrow
```

---

## ðŸŽ¯ What "Progress?" Means

When you ask me for **"progress"**, I will run `daily_stats.py` and show you:

1. Current Balance & Day P&L
2. Win Rate & Profit Factor (if trades taken)
3. Open Positions & Floating P&L
4. Drawdown Status
5. Session Info
6. End of Day Summary (if applicable)

**Quick version:** Just type "status" and I'll run `quick_status.py` instead.

