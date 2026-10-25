"""
Calculate the account size and position sizing required to earn $10/day
with the current 0.1 ATR SL / 2.0 ATR TP system
"""
import json
from pathlib import Path

def load_backtest_results():
    """Load NEW config backtest results"""
    with open('reports/backtest_portfolio_sl0.1_tp2.0.json', 'r') as f:
        return json.load(f)

def print_section(title):
    print("\n" + "="*100)
    print(title.center(100))
    print("="*100 + "\n")

print_section("PATH TO $10 PER DAY")

# Load backtest data
results = load_backtest_results()
core = results['core_metrics']

# Extract key metrics
total_trades = core['trades']
net_pnl = core['net_pl']
expectancy = core['expectancy']
win_rate = core['win_rate']
avg_win = core['avg_win']
avg_loss = abs(core['avg_loss'])
profit_factor = core['profit_factor']

# Backtest period (from our analysis)
start_date = "2022-07-15"
end_date = "2026-10-02"

# Calculate days
from datetime import datetime
start = datetime.strptime(start_date, '%Y-%m-%d')
end = datetime.strptime(end_date, '%Y-%m-%d')
total_days = (end - start).days
trading_days = total_days  # Approximate (includes weekends)

# Calculate actual metrics
trades_per_day = total_trades / trading_days
pnl_per_day = net_pnl / trading_days

print("CURRENT SYSTEM PERFORMANCE (0.01 lots)")
print("-" * 100)
print(f"Backtest Period: {start_date} to {end_date} ({total_days:,} days / {trading_days/365:.1f} years)")
print(f"Total Trades: {total_trades:,}")
print(f"Net P&L: ${net_pnl:,.2f}")
print(f"Expectancy per Trade: ${expectancy:.4f}")
print(f"Win Rate: {win_rate:.2f}%")
print(f"Profit Factor: {profit_factor:.3f}")
print(f"Avg Win: ${avg_win:.2f}")
print(f"Avg Loss: ${avg_loss:.2f}")
print()
print(f"Trades per Day: {trades_per_day:.2f}")
print(f"P&L per Day: ${pnl_per_day:.2f}")

print_section("SCALING TO $10 PER DAY")

# Calculate required scaling
target_daily_pnl = 10.0
scaling_factor = target_daily_pnl / pnl_per_day
required_lots = 0.01 * scaling_factor

print(f"TARGET: ${target_daily_pnl:.2f} per day")
print(f"CURRENT: ${pnl_per_day:.2f} per day (with 0.01 lots)")
print(f"\nSCALING FACTOR: {scaling_factor:.2f}x")
print(f"REQUIRED POSITION SIZE: {required_lots:.4f} lots")

# Calculate account size requirements
# Standard risk management: 1-2% risk per trade
risk_percent_conservative = 0.01  # 1%
risk_percent_aggressive = 0.02    # 2%

# Avg loss at required lot size
avg_loss_scaled = avg_loss * scaling_factor

# Calculate required account sizes
account_size_conservative = avg_loss_scaled / risk_percent_conservative
account_size_aggressive = avg_loss_scaled / risk_percent_aggressive

print_section("ACCOUNT SIZE REQUIREMENTS")

print(f"Average Loss per Trade (scaled): ${avg_loss_scaled:.2f}")
print(f"\nTo maintain proper risk management:")
print(f"\n1% RISK PER TRADE (Conservative):")
print(f"   Required Account Size: ${account_size_conservative:,.2f}")
print(f"   Risk per Trade: ${account_size_conservative * risk_percent_conservative:.2f}")
print(f"\n2% RISK PER TRADE (Aggressive):")
print(f"   Required Account Size: ${account_size_aggressive:,.2f}")
print(f"   Risk per Trade: ${account_size_aggressive * risk_percent_aggressive:.2f}")

# Alternative: Calculate based on current account
current_account = 100  # Starting assumption
lots_for_100 = current_account * risk_percent_conservative / avg_loss

print_section("STARTING WITH $100 ACCOUNT")

print(f"If you start with: ${current_account:.2f}")
print(f"1% risk per trade: ${current_account * risk_percent_conservative:.2f}")
print(f"Safe position size: {lots_for_100:.4f} lots")
print(f"\nWith {lots_for_100:.4f} lots:")
print(f"   Avg Win: ${avg_win * (lots_for_100/0.01):.2f}")
print(f"   Avg Loss: ${avg_loss * (lots_for_100/0.01):.2f}")
print(f"   Expectancy: ${expectancy * (lots_for_100/0.01):.4f}")
print(f"   Expected Daily P&L: ${pnl_per_day * (lots_for_100/0.01):.2f}")

# Calculate days to reach $10/day capacity
days_to_target = 0
account = current_account
daily_log = []

while account < account_size_conservative and days_to_target < 365 * 5:  # Max 5 years
    # Calculate position size (1% risk)
    lots = account * risk_percent_conservative / avg_loss
    
    # Calculate expected daily P&L
    daily_pnl = pnl_per_day * (lots / 0.01)
    
    # Update account
    account += daily_pnl
    days_to_target += 1
    
    # Log milestones
    if days_to_target in [30, 60, 90, 180, 365] or account >= account_size_conservative:
        daily_log.append({
            'day': days_to_target,
            'account': account,
            'lots': lots,
            'daily_pnl': daily_pnl,
        })

print_section("GROWTH PATH FROM $100 TO $10/DAY CAPACITY")

print(f"{'Day':<10} {'Account':<15} {'Position Size':<15} {'Daily P&L':<15}")
print("-" * 70)

for log in daily_log:
    print(f"{log['day']:<10} ${log['account']:>12,.2f}  {log['lots']:>12.4f} lots  ${log['daily_pnl']:>12.2f}")

if account >= account_size_conservative:
    print(f"\n>>> TARGET REACHED in {days_to_target:,} days ({days_to_target/365:.1f} years)")
    print(f">>> Final Account Size: ${account:,.2f}")
else:
    print(f"\n>>> Would take >{days_to_target:,} days to reach target")

print_section("ALTERNATIVE: LARGER STARTING CAPITAL")

starting_amounts = [500, 1000, 2000, 5000, 10000]

print(f"{'Starting Capital':<20} {'Position Size':<15} {'Daily P&L':<15} {'Days to $10/day':<20}")
print("-" * 80)

for start_cap in starting_amounts:
    lots = start_cap * risk_percent_conservative / avg_loss
    daily = pnl_per_day * (lots / 0.01)
    
    # Calculate days to grow to $10/day capacity
    if daily >= target_daily_pnl:
        days = 0
        status = "READY NOW"
    else:
        acc = start_cap
        days = 0
        while acc < account_size_conservative and days < 365 * 5:
            lots_temp = acc * risk_percent_conservative / avg_loss
            daily_temp = pnl_per_day * (lots_temp / 0.01)
            acc += daily_temp
            days += 1
        
        if acc >= account_size_conservative:
            status = f"{days:,} days ({days/365:.1f} yrs)"
        else:
            status = ">5 years"
    
    print(f"${start_cap:>18,.2f}  {lots:>12.4f} lots  ${daily:>12.2f}  {status:<20}")

print_section("REALISTIC BROKER REQUIREMENTS")

print(f"To trade {required_lots:.4f} lots on XAUUSD:")
print(f"\n1. MINIMUM BALANCE (Margin Requirements):")
print(f"   - Leverage 1:100: ${required_lots * 1000 * 2600 / 100:,.2f}")
print(f"   - Leverage 1:500: ${required_lots * 1000 * 2600 / 500:,.2f}")
print(f"\n2. ECN BROKER REQUIREMENTS:")
print(f"   - Spread: <1.5 pips")
print(f"   - Commission: ~$7 per lot round-turn")
print(f"   - Minimum lot size: 0.01 (standard micro lots)")
print(f"\n3. RECOMMENDED BROKERS:")
print(f"   - IC Markets (min deposit: $200)")
print(f"   - Pepperstone (min deposit: $200)")
print(f"   - FXCM Pro (min deposit: varies)")

print_section("FASTEST PATH TO $10/DAY")

print("OPTION 1: START WITH ADEQUATE CAPITAL")
print(f"  - Deposit: ${account_size_conservative:,.2f}")
print(f"  - Position Size: {required_lots:.4f} lots")
print(f"  - Expected Daily: ${target_daily_pnl:.2f}")
print(f"  - Time to Target: 0 days (immediate)")
print(f"  - Risk: 1% per trade (conservative)")
print()
print("OPTION 2: START SMALL AND COMPOUND")
print(f"  - Deposit: $500")
print(f"  - Initial Position: {500 * risk_percent_conservative / avg_loss:.4f} lots")
print(f"  - Initial Daily: ${pnl_per_day * (500 * risk_percent_conservative / avg_loss / 0.01):.2f}")

# Calculate for $500 start
acc = 500
days = 0
while acc < account_size_conservative and days < 365 * 5:
    lots_temp = acc * risk_percent_conservative / avg_loss
    daily_temp = pnl_per_day * (lots_temp / 0.01)
    acc += daily_temp
    days += 1

print(f"  - Time to $10/day: {days:,} days ({days/365:.1f} years)")
print(f"  - Final Account: ${acc:,.2f}")
print(f"  - Risk: 1% per trade (conservative)")
print()
print("OPTION 3: AGGRESSIVE GROWTH (2% risk)")
print(f"  - Deposit: $500")
print(f"  - Initial Position: {500 * risk_percent_aggressive / avg_loss:.4f} lots")
print(f"  - Initial Daily: ${pnl_per_day * (500 * risk_percent_aggressive / avg_loss / 0.01):.2f}")

# Calculate for $500 start with 2% risk
acc = 500
days = 0
while acc < account_size_aggressive and days < 365 * 5:
    lots_temp = acc * risk_percent_aggressive / avg_loss
    daily_temp = pnl_per_day * (lots_temp / 0.01)
    acc += daily_temp
    days += 1

print(f"  - Time to $10/day: {days:,} days ({days/365:.1f} years)")
print(f"  - Final Account: ${acc:,.2f}")
print(f"  - Risk: 2% per trade (aggressive, higher drawdown)")

print_section("RECOMMENDED ACTION PLAN")

print("STEP 1: CHOOSE YOUR PATH")
print(f"  [ ] START NOW: Deposit ${account_size_conservative:,.2f} -> Earn $10/day immediately")
print(f"  [ ] COMPOUND: Deposit $500-$1,000 -> Grow to $10/day in {days/365:.1f}-{(500*0.01/avg_loss*pnl_per_day/0.01)/10*365/2:.1f} years")
print(f"  [ ] SMALL START: Deposit $100 -> Grow slowly (5+ years)")
print()
print("STEP 2: SETUP ECN BROKER")
print("  [ ] Open IC Markets or Pepperstone account")
print("  [ ] Verify spread <1.5 pips on XAUUSD")
print("  [ ] Confirm 0.01 minimum lot size")
print("  [ ] Test with demo account first (2-4 weeks)")
print()
print("STEP 3: RISK MANAGEMENT")
print("  [ ] Set max risk per trade: 1-2% of account")
print("  [ ] Calculate position size before each trade")
print("  [ ] Never override the position sizing formula")
print("  [ ] Track actual vs expected results weekly")
print()
print("STEP 4: MONITOR & ADJUST")
print("  [ ] Wait for 50-100 trades before making changes")
print("  [ ] Track actual daily P&L vs expected")
print("  [ ] If avg loss >$1.00, broker spread too wide")
print("  [ ] Re-calculate position size as account grows")

print_section("SUMMARY")

print(f"CURRENT SYSTEM WITH 0.01 LOTS:")
print(f"  - Expectancy: ${expectancy:.4f} per trade")
print(f"  - Trades per Day: {trades_per_day:.2f}")
print(f"  - Daily P&L: ${pnl_per_day:.2f}")
print()
print(f"TO EARN $10 PER DAY:")
print(f"  - Required Position: {required_lots:.4f} lots ({scaling_factor:.1f}x current)")
print(f"  - Required Account (1% risk): ${account_size_conservative:,.2f}")
print(f"  - Required Account (2% risk): ${account_size_aggressive:,.2f}")
print()
print(f"REALITY CHECK:")
print(f"  - You CANNOT earn $10/day with $100 immediately")
print(f"  - You need either: MORE CAPITAL or TIME TO COMPOUND")
print(f"  - With $500 + compounding: ~{days/365:.1f} years to reach $10/day")
print(f"  - With ${account_size_conservative:,.0f} capital: $10/day from day 1")
print()
print("RECOMMENDED START:")
print(f"  >>> Deposit: $500-$1,000 (realistic for most traders)")
print(f"  >>> Expected Initial Daily: $1-2/day")
print(f"  >>> Compound profits, don't withdraw")
print(f"  >>> Target: $10/day in 2-3 years")

print("\n" + "="*100)
print("CALCULATION COMPLETE")
print("="*100)
