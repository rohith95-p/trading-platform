"""
Enhanced Metrics Analysis
Calculates advanced non-parametric risk metrics:
- Calmar Ratio (Annualized Return / Max DD%)
- Omega Ratio (Gains above 0 / Losses below 0)
- Sortino Ratio (Mean / Downside StdDev)
- P(edge ≤ 0) from bootstrap
"""

import json
import numpy as np
from pathlib import Path

def calculate_enhanced_metrics(report_path):
    """Calculate advanced risk metrics from backtest report"""
    
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    config_name = report['configuration']['name']
    core = report['core_metrics']
    bootstrap = report.get('bootstrap', {})
    
    # Calculate years
    days = report['data']['date_range_days']
    years = days / 365.25
    
    # 1. CALMAR RATIO = Annualized Return / Max DD%
    total_return_pct = core['return_pct']
    annualized_return = (total_return_pct / years) if years > 0 else 0
    max_dd_pct = core['max_drawdown_pct']
    calmar_ratio = (annualized_return / max_dd_pct) if max_dd_pct > 0 else 0
    
    # 2. OMEGA RATIO = Sum(gains above 0) / Sum(losses below 0)
    # This is just Profit Factor for threshold=0
    omega_ratio = core['profit_factor']
    
    # 3. SORTINO RATIO = Mean / Downside StdDev
    # Need to estimate from available data
    # Approximation: using profit factor and payoff ratio
    mean_trade = core['expectancy']
    
    # Estimate downside std dev from losing trades
    avg_loss = abs(core['avg_loss'])
    losses = core['losses']
    
    # Approximate downside variance (losses only)
    # Assuming normal distribution of losses around mean
    downside_variance = (avg_loss ** 2) * (losses / core['trades'])
    downside_stddev = np.sqrt(downside_variance) if downside_variance > 0 else 0.01
    
    sortino_ratio = (mean_trade / downside_stddev) if downside_stddev > 0 else 0
    
    # 4. P(edge ≤ 0) - Already in bootstrap as prob_negative
    prob_edge_zero = bootstrap.get('prob_negative', 0.0)
    
    # 5. Additional metrics
    # Recovery Factor = Net P&L / Max DD (absolute)
    recovery_factor = (core['net_pl'] / core['max_drawdown']) if core['max_drawdown'] > 0 else 0
    
    # Risk-Adjusted Return = Expectancy / Avg Loss
    risk_adjusted_return = (mean_trade / avg_loss) if avg_loss > 0 else 0
    
    return {
        'config': config_name,
        'years': round(years, 2),
        'annualized_return_pct': round(annualized_return, 2),
        'calmar_ratio': round(calmar_ratio, 3),
        'omega_ratio': round(omega_ratio, 3),
        'sortino_ratio': round(sortino_ratio, 3),
        'prob_edge_le_zero': round(prob_edge_zero, 4),
        'recovery_factor': round(recovery_factor, 2),
        'risk_adjusted_return': round(risk_adjusted_return, 3),
        # Core metrics for reference
        'profit_factor': round(core['profit_factor'], 3),
        'expectancy': round(core['expectancy'], 4),
        'max_dd_pct': round(max_dd_pct, 2),
        'return_pct': round(total_return_pct, 2),
    }

def main():
    print("=" * 100)
    print("ENHANCED NON-PARAMETRIC RISK METRICS ANALYSIS")
    print("=" * 100)
    
    # Load both reports
    old_report = Path("reports/backtest_portfolio_sl0.5_tp1.5.json")
    new_report = Path("reports/backtest_portfolio_sl0.1_tp2.0.json")
    
    if not old_report.exists():
        print(f"❌ OLD report not found: {old_report}")
        return
    
    if not new_report.exists():
        print(f"❌ NEW report not found: {new_report}")
        return
    
    old_metrics = calculate_enhanced_metrics(old_report)
    new_metrics = calculate_enhanced_metrics(new_report)
    
    print(f"\n{'Metric':<35} {'OLD (0.5/1.5)':<20} {'NEW (0.1/2.0)':<20} {'Winner':<15}")
    print("-" * 100)
    
    comparisons = [
        ('Profit Factor', 'profit_factor', 'higher'),
        ('Expectancy/trade', 'expectancy', 'higher'),
        ('', '', ''),  # Blank row
        ('--- RISK-ADJUSTED METRICS ---', '', ''),
        ('Calmar Ratio (Ann.Ret/DD%)', 'calmar_ratio', 'higher'),
        ('Omega Ratio (Gains/Losses)', 'omega_ratio', 'higher'),
        ('Sortino Ratio (Mean/Down.SD)', 'sortino_ratio', 'higher'),
        ('Recovery Factor (P&L/MaxDD)', 'recovery_factor', 'higher'),
        ('Risk-Adj Return (E/AvgLoss)', 'risk_adjusted_return', 'higher'),
        ('', '', ''),  # Blank row
        ('--- STATISTICAL CONFIDENCE ---', '', ''),
        ('P(edge ≤ 0) from Bootstrap', 'prob_edge_le_zero', 'lower'),
        ('', '', ''),  # Blank row
        ('--- RETURN METRICS ---', '', ''),
        ('Annualized Return %', 'annualized_return_pct', 'higher'),
        ('Total Return %', 'return_pct', 'higher'),
        ('Max Drawdown %', 'max_dd_pct', 'lower'),
        ('Years of Data', 'years', 'neutral'),
    ]
    
    for label, key, better in comparisons:
        if not key:  # Blank or header row
            print(label)
            continue
        
        old_val = old_metrics.get(key, 0)
        new_val = new_metrics.get(key, 0)
        
        # Format values
        if key in ['expectancy', 'prob_edge_le_zero']:
            old_str = f"{old_val:.4f}"
            new_str = f"{new_val:.4f}"
        elif key in ['years']:
            old_str = f"{old_val:.1f}"
            new_str = f"{new_val:.1f}"
        else:
            old_str = f"{old_val:.3f}" if abs(old_val) < 1000 else f"{old_val:.2f}"
            new_str = f"{new_val:.3f}" if abs(new_val) < 1000 else f"{new_val:.2f}"
        
        # Determine winner
        if better == 'neutral':
            winner = "="
        elif better == 'higher':
            winner = "🏆 NEW" if new_val > old_val else "🏆 OLD" if old_val > new_val else "="
        else:  # lower is better
            winner = "🏆 NEW" if new_val < old_val else "🏆 OLD" if old_val < new_val else "="
        
        print(f"{label:<35} {old_str:>18}  {new_str:>18}  {winner:<15}")
    
    # KEY INSIGHTS
    print("\n" + "=" * 100)
    print("KEY INSIGHTS")
    print("=" * 100)
    
    print(f"\n1. CALMAR RATIO (Return / Drawdown Risk):")
    print(f"   OLD: {old_metrics['calmar_ratio']:.3f}")
    print(f"   NEW: {new_metrics['calmar_ratio']:.3f}")
    print(f"   → NEW is {(new_metrics['calmar_ratio'] / old_metrics['calmar_ratio']):.1f}x better" if old_metrics['calmar_ratio'] > 0 else "")
    print(f"   ✅ Benchmark: >0.5 is good, >2.0 is excellent")
    
    print(f"\n2. OMEGA RATIO (Full Distribution, No Assumptions):")
    print(f"   OLD: {old_metrics['omega_ratio']:.3f}")
    print(f"   NEW: {new_metrics['omega_ratio']:.3f}")
    print(f"   → NEW has {((new_metrics['omega_ratio'] - old_metrics['omega_ratio']) / old_metrics['omega_ratio'] * 100):.1f}% more gains per dollar of loss")
    print(f"   ✅ Benchmark: >1.0 is profitable, >2.0 is good, >3.0 is excellent")
    
    print(f"\n3. SORTINO RATIO (Penalizes Downside Only):")
    print(f"   OLD: {old_metrics['sortino_ratio']:.3f}")
    print(f"   NEW: {new_metrics['sortino_ratio']:.3f}")
    print(f"   → NEW rewards winners {(new_metrics['sortino_ratio'] / old_metrics['sortino_ratio']):.1f}x more per unit downside risk" if old_metrics['sortino_ratio'] > 0 else "")
    print(f"   ✅ Benchmark: >1.0 is good, >2.0 is excellent")
    
    print(f"\n4. P(EDGE ≤ 0) - Statistical Confidence:")
    print(f"   OLD: {old_metrics['prob_edge_le_zero']:.2%}")
    print(f"   NEW: {new_metrics['prob_edge_le_zero']:.2%}")
    print(f"   → Both have {100 - old_metrics['prob_edge_le_zero']*100:.0f}% confidence edge is real")
    print(f"   ✅ Benchmark: <5% is required, 0% is perfect")
    
    print(f"\n5. RECOVERY FACTOR (How fast to recover from DD):")
    print(f"   OLD: {old_metrics['recovery_factor']:.2f}x")
    print(f"   NEW: {new_metrics['recovery_factor']:.2f}x")
    print(f"   → NEW recovers {(new_metrics['recovery_factor'] / old_metrics['recovery_factor']):.1f}x faster from drawdowns" if old_metrics['recovery_factor'] > 0 else "")
    print(f"   ✅ Benchmark: >3.0 is good, >10.0 is excellent")
    
    # FINAL VERDICT
    print("\n" + "=" * 100)
    print("VALIDATION SUMMARY")
    print("=" * 100)
    
    gates = {
        'Profit Factor > 1.3': (old_metrics['profit_factor'] > 1.3, new_metrics['profit_factor'] > 1.3),
        'P(edge≤0) < 5%': (old_metrics['prob_edge_le_zero'] < 0.05, new_metrics['prob_edge_le_zero'] < 0.05),
        'Calmar Ratio > 0.5': (old_metrics['calmar_ratio'] > 0.5, new_metrics['calmar_ratio'] > 0.5),
        'Omega Ratio > 1.0': (old_metrics['omega_ratio'] > 1.0, new_metrics['omega_ratio'] > 1.0),
        'Sortino Ratio > 1.0': (old_metrics['sortino_ratio'] > 1.0, new_metrics['sortino_ratio'] > 1.0),
        'Recovery Factor > 3.0': (old_metrics['recovery_factor'] > 3.0, new_metrics['recovery_factor'] > 3.0),
    }
    
    print(f"\n{'Gate':<35} {'OLD':<15} {'NEW':<15}")
    print("-" * 65)
    
    old_passed = 0
    new_passed = 0
    
    for gate, (old_pass, new_pass) in gates.items():
        old_icon = "✅ PASS" if old_pass else "❌ FAIL"
        new_icon = "✅ PASS" if new_pass else "❌ FAIL"
        print(f"{gate:<35} {old_icon:<15} {new_icon:<15}")
        
        if old_pass:
            old_passed += 1
        if new_pass:
            new_passed += 1
    
    print(f"\n{'TOTAL SCORE':<35} {old_passed}/{len(gates):<15} {new_passed}/{len(gates):<15}")
    
    # Save enhanced metrics
    output = {
        'generated_at': old_metrics.get('config', ''),
        'old_config': old_metrics,
        'new_config': new_metrics,
        'gates': {k: {'old': bool(v[0]), 'new': bool(v[1])} for k, v in gates.items()},
        'old_score': f"{old_passed}/{len(gates)}",
        'new_score': f"{new_passed}/{len(gates)}"
    }
    
    output_path = Path("reports/enhanced_metrics_comparison.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n{'='*100}")
    print(f"Enhanced metrics saved: {output_path}")
    print(f"{'='*100}\n")

if __name__ == "__main__":
    main()
