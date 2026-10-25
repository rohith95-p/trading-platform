"""
Compare Two Backtest Results
Reads the final reports and generates side-by-side comparison
"""

import json
from pathlib import Path
from datetime import datetime

def load_report(config_name):
    report_path = Path(f"reports/backtest_trendpullback_{config_name}.json")
    if not report_path.exists():
        return None
    with open(report_path, "r") as f:
        return json.load(f)

def compare_reports():
    # Load both reports
    old_config = load_report("sl0.5_tp1.5")
    new_config = load_report("sl0.1_tp2.0")
    
    if not old_config:
        print("❌ Old configuration (0.5/1.5) report not found!")
        return
    
    if not new_config:
        print("❌ New configuration (0.1/2.0) report not found!")
        return
    
    print("=" * 100)
    print("BACKTEST COMPARISON: OLD (0.5/1.5) vs NEW (0.1/2.0)")
    print("=" * 100)
    
    # Extract metrics
    old_m = old_config["core_metrics"]
    new_m = new_config["core_metrics"]
    
    print(f"\n{'Metric':<30} {'OLD (0.5/1.5)':<20} {'NEW (0.1/2.0)':<20} {'Change':<15} {'Winner':<10}")
    print("-" * 100)
    
    metrics = [
        ("Total Trades", "trades", "{:,.0f}"),
        ("Win Rate %", "win_rate", "{:.2f}%"),
        ("Profit Factor", "profit_factor", "{:.3f}"),
        ("Net P&L", "net_pl", "${:.2f}"),
        ("Expectancy/trade", "expectancy", "${:.4f}"),
        ("Avg Win", "avg_win", "${:.2f}"),
        ("Avg Loss", "avg_loss", "${:.2f}"),
        ("Payoff Ratio", "payoff_ratio", "{:.2f}x"),
        ("Max Drawdown %", "max_drawdown_pct", "{:.2f}%"),
        ("Return %", "return_pct", "{:.2f}%"),
        ("End Balance", "end_balance", "${:.2f}"),
    ]
    
    for label, key, fmt in metrics:
        old_val = old_m.get(key, 0)
        new_val = new_m.get(key, 0)
        
        old_str = fmt.format(old_val)
        new_str = fmt.format(new_val)
        
        # Calculate change
        if old_val != 0:
            change_pct = ((new_val - old_val) / abs(old_val)) * 100
            change_str = f"{change_pct:+.1f}%"
        else:
            change_str = "N/A"
        
        # Determine winner (higher is better, except for drawdown and avg loss)
        if key in ["max_drawdown_pct", "avg_loss"]:
            winner = "OLD" if old_val < new_val else "NEW" if new_val < old_val else "TIE"
        else:
            winner = "OLD" if old_val > new_val else "NEW" if new_val > old_val else "TIE"
        
        winner_icon = "🏆 " + winner if winner != "TIE" else "="
        
        print(f"{label:<30} {old_str:>18}  {new_str:>18}  {change_str:>13}  {winner_icon:<10}")
    
    # Bootstrap comparison
    print("\n" + "=" * 100)
    print("BOOTSTRAP CONFIDENCE (5000 resamples)")
    print("=" * 100)
    
    old_bs = old_config.get("bootstrap", {})
    new_bs = new_config.get("bootstrap", {})
    
    print(f"\n{'Metric':<30} {'OLD (0.5/1.5)':<20} {'NEW (0.1/2.0)':<20} {'Winner':<10}")
    print("-" * 80)
    
    bs_metrics = [
        ("Bootstrap p05", "p05", "${:.4f}"),
        ("Bootstrap p50", "p50", "${:.4f}"),
        ("Bootstrap p95", "p95", "${:.4f}"),
        ("P(negative)", "prob_negative", "{:.2%}"),
    ]
    
    for label, key, fmt in bs_metrics:
        old_val = old_bs.get(key, 0)
        new_val = new_bs.get(key, 0)
        
        old_str = fmt.format(old_val)
        new_str = fmt.format(new_val)
        
        if key == "prob_negative":
            winner = "OLD" if old_val < new_val else "NEW" if new_val < old_val else "TIE"
        else:
            winner = "OLD" if old_val > new_val else "NEW" if new_val > old_val else "TIE"
        
        winner_icon = "🏆 " + winner if winner != "TIE" else "="
        
        print(f"{label:<30} {old_str:>18}  {new_str:>18}  {winner_icon:<10}")
    
    # Validation gates
    print("\n" + "=" * 100)
    print("VALIDATION GATES")
    print("=" * 100)
    
    old_gates = old_config["validation_gates"]
    new_gates = new_config["validation_gates"]
    
    print(f"\n{'Gate':<50} {'OLD':<10} {'NEW':<10}")
    print("-" * 70)
    
    for gate in old_gates.keys():
        old_pass = old_gates.get(gate, False)
        new_pass = new_gates.get(gate, False)
        
        old_icon = "✅" if old_pass else "❌"
        new_icon = "✅" if new_pass else "❌"
        
        print(f"{gate:<50} {old_icon:<10} {new_icon:<10}")
    
    old_score = old_config["validation_score"]
    new_score = new_config["validation_score"]
    
    print(f"\n{'TOTAL SCORE':<50} {old_score:<10} {new_score:<10}")
    
    # Final verdict
    print("\n" + "=" * 100)
    print("FINAL VERDICT")
    print("=" * 100)
    
    old_pf = old_m["profit_factor"]
    new_pf = new_m["profit_factor"]
    
    old_exp = old_m["expectancy"]
    new_exp = new_m["expectancy"]
    
    print(f"\nOLD Configuration (0.5 SL / 1.5 TP):")
    print(f"  Profit Factor: {old_pf:.3f}")
    print(f"  Expectancy:    ${old_exp:.4f}")
    print(f"  Score:         {old_score}")
    
    print(f"\nNEW Configuration (0.1 SL / 2.0 TP):")
    print(f"  Profit Factor: {new_pf:.3f}")
    print(f"  Expectancy:    ${new_exp:.4f}")
    print(f"  Score:         {new_score}")
    
    print("\n" + "-" * 100)
    
    if new_pf > old_pf and new_exp > old_exp:
        print("\n🏆 WINNER: NEW (0.1/2.0) - Better profit factor AND expectancy")
        print("✅ Recommendation: Deploy NEW configuration")
    elif old_pf > new_pf and old_exp > new_exp:
        print("\n🏆 WINNER: OLD (0.5/1.5) - Better profit factor AND expectancy")
        print("⚠️  Recommendation: Revert to OLD configuration")
    else:
        print("\n⚠️  MIXED RESULTS - One config better on PF, other better on expectancy")
        print("🔍 Recommendation: Manual review required")
        
        if new_pf > 1.3 and new_exp > 0:
            print("   NEW config passes minimum thresholds (PF>1.3, E>0)")
        if old_pf > 1.3 and old_exp > 0:
            print("   OLD config passes minimum thresholds (PF>1.3, E>0)")
    
    print("\n" + "=" * 100 + "\n")
    
    # Save comparison
    comparison = {
        "generated_at": datetime.now().isoformat(),
        "old_config": "sl0.5_tp1.5",
        "new_config": "sl0.1_tp2.0",
        "old_metrics": old_m,
        "new_metrics": new_m,
        "old_bootstrap": old_bs,
        "new_bootstrap": new_bs,
        "old_gates": old_gates,
        "new_gates": new_gates,
        "old_score": old_score,
        "new_score": new_score,
        "winner": "NEW" if (new_pf > old_pf and new_exp > old_exp) else "OLD" if (old_pf > new_pf and old_exp > new_exp) else "MIXED"
    }
    
    comparison_path = Path("reports/backtest_comparison.json")
    with open(comparison_path, "w") as f:
        json.dump(comparison, f, indent=2)
    
    print(f"Comparison saved: {comparison_path}\n")

if __name__ == "__main__":
    compare_reports()
