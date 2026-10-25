"""
Calculate $10/day feasibility WITHOUT ECN broker (standard 2-3 pip spreads)
"""
import json

def print_section(title):
    print("\n" + "="*100)
    print(title.center(100))
    print("="*100 + "\n")

print_section("CAN YOU EARN $10/DAY WITHOUT ECN?")

# Load backtest results
with open('reports/backtest_portfolio_sl0.1_tp2.0.json', 'r') as f:
    results = json.load(f)

core = results['core_metrics']

# Original backtest metrics (with realistic ECN spread model: 0.2 pips spread)
original_trades = core['trades']
original_net_pnl = core['net_pl']
original_expectancy = core['expectancy']
original_avg_win = core['avg_win']
original_avg_loss = abs(core['avg_loss'])

print("BACKTEST RESULTS (with 0.2 pip ECN spread model):")
print("-" * 100)
print(f"Total Trades: {original_trades:,}")
print(f"Net P&L: ${original_net_pnl:,.2f}")
print(f"Expectancy: ${original_expectancy:.4f} per trade")
print(f"Avg Win: ${original_avg_win:.2f}")
print(f"Avg Loss: ${original_avg_loss:.2f}")
print(f"Daily P&L (0.01 lots): ${original_net_pnl / 1540:.2f}")

print_section("IMPACT OF STANDARD BROKER SPREAD (2.5 pips)")

# Standard broker costs
standard_spread = 2.5  # pips
ecn_spread = 0.2  # pips (what backtest used)
extra_spread = standard_spread - ecn_spread  # 2.3 pips extra

# Extra cost per trade (entry + exit)
# For 0.01 lots: 1 pip = $0.01, so 2.3 pips = $0.023
extra_cost_per_trade = extra_spread * 0.01

print(f"ECN Spread (backtest): {ecn_spread} pips")
print(f"Standard Spread: {standard_spread} pips")
print(f"Extra Spread Cost: {extra_spread} pips")
print(f"\nExtra Cost per Trade (0.01 lots): ${extra_cost_per_trade:.4f}")
print(f"Total Extra Cost ({original_trades:,} trades): ${extra_cost_per_trade * original_trades:,.2f}")

# Adjusted metrics with standard spread
adjusted_net_pnl = original_net_pnl - (extra_cost_per_trade * original_trades)
adjusted_expectancy = original_expectancy - extra_cost_per_trade
adjusted_daily_pnl = adjusted_net_pnl / 1540

print(f"\nADJUSTED METRICS (with 2.5 pip standard spread):")
print(f"Net P&L: ${adjusted_net_pnl:,.2f} (was ${original_net_pnl:,.2f})")
print(f"Expectancy: ${adjusted_expectancy:.4f} (was ${original_expectancy:.4f})")
print(f"Daily P&L (0.01 lots): ${adjusted_daily_pnl:.2f} (was ${original_net_pnl / 1540:.2f})")

# Calculate if still profitable
if adjusted_expectancy > 0:
    print(f"\n✅ SYSTEM STILL PROFITABLE with standard broker!")
    print(f"   Profit reduced by {(1 - adjusted_net_pnl/original_net_pnl)*100:.1f}%")
else:
    print(f"\n❌ SYSTEM BECOMES UNPROFITABLE with standard broker!")
    print(f"   Negative expectancy: ${adjusted_expectancy:.4f}")

print_section("TO EARN $10/DAY WITHOUT ECN")

target_daily = 10.0

# Scaling needed
if adjusted_daily_pnl > 0:
    scaling_factor = target_daily / adjusted_daily_pnl
    required_lots = 0.01 * scaling_factor
    
    print(f"Current Daily P&L (0.01 lots): ${adjusted_daily_pnl:.2f}")
    print(f"Target Daily P&L: ${target_daily:.2f}")
    print(f"\nScaling Factor: {scaling_factor:.2f}x")
    print(f"Required Position Size: {required_lots:.4f} lots")
    
    # Calculate avg loss with standard spread at required lot size
    adjusted_avg_loss = original_avg_loss + (extra_spread * 0.01)  # At 0.01 lots
    adjusted_avg_loss_scaled = adjusted_avg_loss * scaling_factor
    
    print(f"\nWith {required_lots:.4f} lots:")
    print(f"  Avg Win: ${original_avg_win * scaling_factor:.2f}")
    print(f"  Avg Loss: ${adjusted_avg_loss_scaled:.2f} (includes spread impact)")
    print(f"  Expectancy: ${adjusted_expectancy * scaling_factor:.4f}")
    
    # Account size requirements
    risk_1pct = adjusted_avg_loss_scaled / 0.01
    risk_2pct = adjusted_avg_loss_scaled / 0.02
    
    print(f"\nAccount Size Requirements:")
    print(f"  1% risk per trade: ${risk_1pct:,.2f}")
    print(f"  2% risk per trade: ${risk_2pct:,.2f}")
    
else:
    print("❌ IMPOSSIBLE: System loses money with standard spreads!")

print_section("COMPARISON: ECN vs STANDARD BROKER")

# ECN calculations (from previous analysis)
ecn_daily_pnl = original_net_pnl / 1540  # $5.25
ecn_scaling_for_10 = 10.0 / ecn_daily_pnl  # 1.90x
ecn_required_lots = 0.01 * ecn_scaling_for_10  # 0.019 lots
ecn_account_needed = (original_avg_loss * ecn_scaling_for_10) / 0.01  # ~$99

# Standard calculations
std_daily_pnl = adjusted_daily_pnl
if std_daily_pnl > 0:
    std_scaling_for_10 = 10.0 / std_daily_pnl
    std_required_lots = 0.01 * std_scaling_for_10
    std_avg_loss = (original_avg_loss + extra_spread * 0.01) * std_scaling_for_10
    std_account_needed = std_avg_loss / 0.01
else:
    std_scaling_for_10 = float('inf')
    std_required_lots = float('inf')
    std_account_needed = float('inf')

print(f"{'Metric':<30} {'ECN Broker':<20} {'Standard Broker':<20} {'Winner'}")
print("-" * 90)
print(f"{'Spread':<30} {'0.2 pips':<20} {'2.5 pips':<20} {'ECN'}")
print(f"{'Daily P&L (0.01 lots)':<30} {'$' + f'{ecn_daily_pnl:.2f}':<20} {'$' + f'{std_daily_pnl:.2f}':<20} {'ECN' if ecn_daily_pnl > std_daily_pnl else 'STD'}")
print(f"{'Scaling for $10/day':<30} {f'{ecn_scaling_for_10:.2f}x':<20} {f'{std_scaling_for_10:.2f}x':<20} {'ECN' if ecn_scaling_for_10 < std_scaling_for_10 else 'STD'}")
print(f"{'Required Lots':<30} {f'{ecn_required_lots:.4f}':<20} {f'{std_required_lots:.4f}':<20} {'ECN' if ecn_required_lots < std_required_lots else 'STD'}")

if std_account_needed != float('inf'):
    print(f"{'Account Needed (1% risk)':<30} {'$' + f'{ecn_account_needed:.2f}':<20} {'$' + f'{std_account_needed:.2f}':<20} {'ECN' if ecn_account_needed < std_account_needed else 'STD'}")
else:
    print(f"{'Account Needed (1% risk)':<30} {'$' + f'{ecn_account_needed:.2f}':<20} {'IMPOSSIBLE':<20} {'ECN'}")

print_section("ALTERNATIVE: USE WIDER STOP LOSS")

print("OPTION: Switch to 0.5 ATR SL / 1.5 ATR TP (wider stops)")
print("-" * 100)

# Load old config results
with open('reports/backtest_portfolio_sl0.5_tp1.5.json', 'r') as f:
    old_results = json.load(f)

old_core = old_results['core_metrics']
old_net_pnl = old_core['net_pl']
old_expectancy = old_core['expectancy']
old_avg_loss = abs(old_core['avg_loss'])
old_daily_pnl = old_net_pnl / 1540

print(f"\nOLD CONFIG (0.5 ATR SL / 1.5 ATR TP) with ECN:")
print(f"  Daily P&L (0.01 lots): ${old_daily_pnl:.2f}")
print(f"  Avg Loss: ${old_avg_loss:.2f}")
print(f"  Expectancy: ${old_expectancy:.4f}")

# This config has ~5 pip stop loss, so 2.5 pip spread is less impactful
# Extra cost is still 2.3 pips, but relative to 5-pip loss it's smaller
old_extra_cost = extra_spread * 0.01
old_adjusted_expectancy = old_expectancy - old_extra_cost
old_adjusted_daily_pnl = old_daily_pnl - (old_extra_cost * original_trades / 1540)

print(f"\nOLD CONFIG with STANDARD BROKER:")
print(f"  Daily P&L (0.01 lots): ${old_adjusted_daily_pnl:.2f}")
print(f"  Expectancy: ${old_adjusted_expectancy:.4f}")

if old_adjusted_expectancy > 0:
    old_scaling = 10.0 / old_adjusted_daily_pnl
    old_required_lots = 0.01 * old_scaling
    old_adjusted_avg_loss = old_avg_loss + old_extra_cost
    old_account_needed = (old_adjusted_avg_loss * old_scaling) / 0.01
    
    print(f"\nTo earn $10/day with OLD CONFIG + STANDARD BROKER:")
    print(f"  Required Lots: {old_required_lots:.4f}")
    print(f"  Account Needed (1% risk): ${old_account_needed:,.2f}")
    print(f"  Trade-off: {((original_net_pnl - old_net_pnl) / original_net_pnl * 100):.0f}% less profit vs NEW config with ECN")

print_section("FINAL VERDICT")

if adjusted_expectancy > 0:
    print("✅ YES, you CAN earn $10/day without ECN, BUT:")
    print(f"\n   ECN Broker:")
    print(f"     - Account needed: ${ecn_account_needed:,.2f}")
    print(f"     - Lots needed: {ecn_required_lots:.4f}")
    print(f"     - Profit Factor: 3.318 (ELITE)")
    print(f"\n   Standard Broker:")
    print(f"     - Account needed: ${std_account_needed:,.2f}")
    print(f"     - Lots needed: {std_required_lots:.4f}")
    print(f"     - Profit reduced by {(1 - adjusted_net_pnl/original_net_pnl)*100:.0f}%")
    print(f"\n   DIFFERENCE: ${std_account_needed - ecn_account_needed:,.2f} MORE capital needed without ECN")
    print(f"   RECOMMENDATION: ECN is more efficient!")
else:
    print("❌ NO, you CANNOT earn $10/day without ECN with 0.1 ATR SL")
    print(f"\n   The 2.5 pip spread DESTROYS your 1-pip stop loss edge")
    print(f"   Expectancy becomes NEGATIVE: ${adjusted_expectancy:.4f}")
    print(f"\n   YOUR OPTIONS:")
    print(f"   1. Use ECN broker (RECOMMENDED)")
    print(f"   2. Switch to wider stops (0.5 ATR SL)")
    print(f"      - With standard broker, daily = ${old_adjusted_daily_pnl:.2f}")
    print(f"      - Need ${old_account_needed:,.2f} account for $10/day")
    print(f"      - But {((original_net_pnl - old_net_pnl) / original_net_pnl * 100):.0f}% less profit than NEW config")

print("\n" + "="*100)
print("BOTTOM LINE: ECN broker is almost mandatory for 0.1 ATR SL strategy.")
print("             Without ECN, you need wider stops (less profit) or more capital.")
print("="*100)
