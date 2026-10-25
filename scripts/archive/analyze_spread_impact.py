"""
Analyze Spread Impact on 0.1 ATR Stop Loss
Verifies if 1-pip SL is viable with realistic broker spreads
"""

import json
import numpy as np
from pathlib import Path

def analyze_spread_impact():
    print("=" * 100)
    print("SPREAD IMPACT ANALYSIS: 0.1 ATR SL (~1 pip)")
    print("=" * 100)
    
    # Load NEW config report
    report_path = Path("reports/backtest_portfolio_sl0.1_tp2.0.json")
    
    if not report_path.exists():
        print("❌ Report not found!")
        return
    
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    core = report['core_metrics']
    
    # XAUUSD typical specs
    print("\n" + "=" * 100)
    print("XAUUSD BROKER SPECIFICATIONS")
    print("=" * 100)
    
    specs = {
        'Typical Spread': '2-3 pips (0.20-0.30)',
        'ECN Spread': '1-2 pips (0.10-0.20)',
        'Widened Spread (news)': '5-10 pips (0.50-1.00)',
        'Commission (ECN)': '$7-10 per lot round-turn',
        'Slippage (avg)': '0.5-1.0 pips',
        'Stop Distance Min': '1-2 pips (broker dependent)',
    }
    
    for key, value in specs.items():
        print(f"  {key:<30} {value}")
    
    # Calculate ATR from avg loss
    print("\n" + "=" * 100)
    print("ACTUAL 0.1 ATR STOP ANALYSIS")
    print("=" * 100)
    
    avg_loss = abs(core['avg_loss'])
    avg_win = core['avg_win']
    
    # 0.01 lots on XAUUSD: $1 per pip movement
    # If avg loss = $0.52, that's ~0.52 pips
    # But that's AFTER spread already applied!
    
    print(f"\nAvg Loss: ${avg_loss:.2f}")
    print(f"Avg Win:  ${avg_win:.2f}")
    print(f"\nIf 0.01 lots = $1/pip on XAUUSD:")
    print(f"  Avg Loss in pips: ~{avg_loss:.2f} pips")
    print(f"  Avg Win in pips:  ~{avg_win:.2f} pips")
    
    # Backtest uses realistic_ecn scenario
    print("\n" + "=" * 100)
    print("BACKTEST COST MODEL (realistic_ecn)")
    print("=" * 100)
    
    print("\nFrom src/backtesting/costs.py:")
    print("  Spread: 0.20 (2 pips)")
    print("  Commission: $7 per lot round-turn")
    print("  Slippage: 0.10 (1 pip)")
    print("\nTotal cost per 0.01 lot trade:")
    print("  Spread: 0.20 * 0.01 = $0.002")
    print("  Commission: $7 * 0.01 = $0.07")
    print("  Slippage (entry+exit): 0.10 * 2 * 0.01 = $0.002")
    print("  TOTAL: ~$0.074 per trade")
    
    # Check if this matches
    gross_profit = core['gross_profit']
    net_pl = core['net_pl']
    total_costs = gross_profit - net_pl
    cost_per_trade = total_costs / core['trades']
    
    print(f"\nActual costs from backtest:")
    print(f"  Gross Profit: ${gross_profit:.2f}")
    print(f"  Net P&L: ${net_pl:.2f}")
    print(f"  Total Costs: ${total_costs:.2f}")
    print(f"  Cost per trade: ${cost_per_trade:.4f}")
    
    # SL distance analysis
    print("\n" + "=" * 100)
    print("STOP LOSS VIABILITY ANALYSIS")
    print("=" * 100)
    
    # 0.1 ATR on XAUUSD
    # XAUUSD ATR typically 8-12 pips
    # 0.1 * 10 = 1.0 pip SL distance
    
    atr_estimate = 10  # pips, typical XAUUSD M15 ATR
    sl_distance = 0.1 * atr_estimate
    
    print(f"\nEstimated ATR: {atr_estimate} pips")
    print(f"0.1 ATR SL: {sl_distance:.1f} pip")
    
    # Can broker honor this?
    print("\n⚠️  CRITICAL ISSUES:")
    print(f"  1. Stop Distance: {sl_distance:.1f} pip")
    print(f"     - Many brokers require minimum 2-3 pips")
    print(f"     - May get 'invalid stops' rejection")
    print(f"     ✅ Solution: Check broker specs, may need 0.2 ATR minimum")
    
    print(f"\n  2. Spread Impact: 2-3 pips typical")
    print(f"     - Your SL: {sl_distance:.1f} pip")
    print(f"     - Spread: 2+ pips")
    print(f"     - Trade opens ALREADY past your SL!")
    print(f"     ⚠️  Risk: Instant stop-out on entry")
    print(f"     ✅ Solution: Use ECN broker with <1 pip spread")
    
    print(f"\n  3. Slippage on Stop: 0.5-1 pip")
    print(f"     - Your SL: {sl_distance:.1f} pip")
    print(f"     - Actual fill: 1.5-2 pips worse")
    print(f"     - Avg loss should be ~$1.50-2.00, not $0.52")
    print(f"     🤔 Backtest may be too optimistic")
    
    # Reality check
    print("\n" + "=" * 100)
    print("REALITY CHECK")
    print("=" * 100)
    
    print("\n📊 BACKTEST RESULTS:")
    print(f"  Avg Loss: ${avg_loss:.2f} (~{avg_loss:.1f} pips)")
    print(f"  Win Rate: {core['win_rate']:.1f}%")
    print(f"  Profit Factor: {core['profit_factor']:.2f}")
    
    print("\n⚠️  LIVE TRADING REALITY:")
    print(f"  Avg Loss with 2-pip spread: ${avg_loss + 0.20:.2f}")
    print(f"  Avg Loss with slippage: ${avg_loss + 0.30:.2f}")
    print(f"  Additional cost per losing trade: +$0.20-0.30")
    print(f"  Over {core['losses']} losing trades: +${(core['losses'] * 0.25):.0f} extra cost!")
    
    # Adjusted PF
    extra_cost = core['losses'] * 0.25
    adjusted_net_pl = net_pl - extra_cost
    adjusted_pf = gross_profit / (core['gross_loss'] + extra_cost) if (core['gross_loss'] + extra_cost) > 0 else 0
    
    print(f"\n📉 ADJUSTED METRICS (with realistic spread/slippage):")
    print(f"  Extra Costs: ${extra_cost:.2f}")
    print(f"  Adjusted Net P&L: ${adjusted_net_pl:.2f}")
    print(f"  Adjusted Profit Factor: {adjusted_pf:.3f}")
    print(f"  Impact: -{((core['profit_factor'] - adjusted_pf) / core['profit_factor'] * 100):.1f}% on PF")
    
    if adjusted_pf > 1.3:
        print(f"  ✅ Still above 1.3 threshold!")
    else:
        print(f"  ⚠️  Below 1.3 threshold!")
    
    # Recommendations
    print("\n" + "=" * 100)
    print("RECOMMENDATIONS")
    print("=" * 100)
    
    print("\n1. BROKER REQUIREMENTS:")
    print("   ✅ Use ECN broker (IC Markets, Pepperstone, FXCM Pro)")
    print("   ✅ Verify minimum stop distance (should allow 1-2 pips)")
    print("   ✅ Check spread: Must be <1.5 pips consistently")
    print("   ✅ Look for raw spread + commission model")
    
    print("\n2. EXECUTION MONITORING:")
    print("   📊 Track actual vs expected avg loss")
    print("   📊 Log rejected orders (invalid stops)")
    print("   📊 Measure slippage on each trade")
    print("   📊 Compare live costs to backtest")
    
    print("\n3. CONFIGURATION ALTERNATIVES:")
    print("   Option A: Keep 0.1 ATR with ECN broker (<1 pip spread)")
    print("   Option B: Increase to 0.15 ATR (~1.5 pips, safer)")
    print("   Option C: Dynamic SL based on spread (0.1 ATR + 1 pip buffer)")
    
    print("\n4. LIVE TESTING:")
    print("   🔬 Start with 50 trades on demo")
    print("   🔬 Verify avg loss stays near $0.52")
    print("   🔬 If avg loss > $1.00, SL too tight for your broker")
    print("   🔬 Only then move to real money")
    
    print("\n" + "=" * 100 + "\n")

if __name__ == "__main__":
    analyze_spread_impact()
