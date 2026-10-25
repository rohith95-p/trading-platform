"""
Export Backtest Trades to CSV
Loads trade data from checkpoint files and exports to detailed CSV
"""

import pickle
import json
import csv
from pathlib import Path
from datetime import datetime

def export_trades_to_csv(checkpoint_file, output_csv):
    """Export trades from checkpoint pickle file to CSV"""
    
    print(f"Loading: {checkpoint_file}")
    
    # Load checkpoint data
    with open(checkpoint_file, 'rb') as f:
        data = pickle.load(f)
    
    trades = data.get('trades', [])
    
    if not trades:
        print(f"  ❌ No trades found in {checkpoint_file}")
        return 0
    
    print(f"  Found {len(trades)} trades")
    
    # Define CSV columns
    fieldnames = [
        'trade_id',
        'entry_time',
        'entry_datetime',
        'exit_time',
        'exit_datetime',
        'direction',
        'entry_price',
        'exit_price',
        'lots',
        'gross_pl',
        'net_pl',
        'pips',
        'strategy',
        'exit_reason',
        'duration_minutes',
        'trade_result',
        'return_r',
    ]
    
    # Write CSV
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for idx, trade in enumerate(trades, 1):
            entry_dt = datetime.utcfromtimestamp(trade['entry_time'])
            exit_dt = datetime.utcfromtimestamp(trade['exit_time'])
            
            duration = (trade['exit_time'] - trade['entry_time']) / 60  # minutes
            
            # Calculate pips (for XAUUSD, 1 pip = 0.01)
            pips = abs(trade['exit_price'] - trade['entry_price']) / 0.01
            if not trade['is_buy']:
                pips = -pips if trade['net_pl'] < 0 else pips
            else:
                pips = pips if trade['net_pl'] > 0 else -pips
            
            # Trade result
            if trade['net_pl'] > 0:
                result = 'WIN'
            elif trade['net_pl'] < 0:
                result = 'LOSS'
            else:
                result = 'SCRATCH'
            
            # Calculate R-multiple (rough estimate based on net P&L)
            # Assuming 0.01 lots = $1 per pip for XAUUSD
            r_mult = trade['net_pl'] / abs(trade['net_pl']) if trade['net_pl'] != 0 else 0
            
            row = {
                'trade_id': idx,
                'entry_time': trade['entry_time'],
                'entry_datetime': entry_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'exit_time': trade['exit_time'],
                'exit_datetime': exit_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'direction': 'BUY' if trade['is_buy'] else 'SELL',
                'entry_price': round(trade['entry_price'], 2),
                'exit_price': round(trade['exit_price'], 2),
                'lots': trade['lots'],
                'gross_pl': round(trade['gross_pl'], 2),
                'net_pl': round(trade['net_pl'], 2),
                'pips': round(pips, 1),
                'strategy': trade['strategy'],
                'exit_reason': trade['exit_reason'],
                'duration_minutes': round(duration, 1),
                'trade_result': result,
                'return_r': round(r_mult, 2),
            }
            
            writer.writerow(row)
    
    print(f"  ✅ Exported to: {output_csv}")
    return len(trades)

def create_summary_csv(config_name, trades_count, report_path, summary_csv):
    """Create summary statistics CSV"""
    
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    core = report['core_metrics']
    bootstrap = report.get('bootstrap', {})
    monte_carlo = report.get('monte_carlo', {})
    
    # Read enhanced metrics if available
    enhanced_path = Path("reports/enhanced_metrics_comparison.json")
    calmar = omega = sortino = 0
    if enhanced_path.exists():
        with open(enhanced_path, 'r') as f:
            enhanced = json.load(f)
            if 'old_config' in enhanced and config_name in enhanced['old_config']['config']:
                metrics = enhanced['old_config']
            elif 'new_config' in enhanced and config_name in enhanced['new_config']['config']:
                metrics = enhanced['new_config']
            else:
                metrics = {}
            
            calmar = metrics.get('calmar_ratio', 0)
            omega = metrics.get('omega_ratio', 0)
            sortino = metrics.get('sortino_ratio', 0)
    
    summary_data = [
        ['CONFIGURATION', config_name],
        ['Generated', report['generated_at']],
        [''],
        ['=== CORE METRICS ===', ''],
        ['Total Trades', core['trades']],
        ['Winning Trades', core['wins']],
        ['Losing Trades', core['losses']],
        ['Win Rate %', round(core['win_rate'], 2)],
        [''],
        ['=== PERFORMANCE ===', ''],
        ['Profit Factor', round(core['profit_factor'], 3)],
        ['Net P&L', f"${core['net_pl']:.2f}"],
        ['Gross Profit', f"${core['gross_profit']:.2f}"],
        ['Gross Loss', f"${core['gross_loss']:.2f}"],
        ['Expectancy/trade', f"${core['expectancy']:.4f}"],
        [''],
        ['=== TRADE STATS ===', ''],
        ['Avg Win', f"${core['avg_win']:.2f}"],
        ['Avg Loss', f"${abs(core['avg_loss']):.2f}"],
        ['Payoff Ratio', f"{core['payoff_ratio']:.2f}x"],
        [''],
        ['=== RISK METRICS ===', ''],
        ['Max Drawdown', f"${core['max_drawdown']:.2f}"],
        ['Max Drawdown %', f"{core['max_drawdown_pct']:.2f}%"],
        ['Return %', f"{core['return_pct']:.2f}%"],
        ['End Balance', f"${core['end_balance']:.2f}"],
        [''],
        ['=== ADVANCED METRICS ===', ''],
        ['Calmar Ratio', round(calmar, 3)],
        ['Omega Ratio', round(omega, 3)],
        ['Sortino Ratio', round(sortino, 3)],
        [''],
        ['=== BOOTSTRAP (5000 resamples) ===', ''],
        ['Mean Expectancy', f"${bootstrap.get('mean', 0):.4f}"],
        ['5th Percentile', f"${bootstrap.get('p05', 0):.4f}"],
        ['95th Percentile', f"${bootstrap.get('p95', 0):.4f}"],
        ['P(negative)', f"{bootstrap.get('prob_negative', 0):.2%}"],
        [''],
        ['=== MONTE CARLO (5000 paths) ===', ''],
        ['Median Max DD', f"${monte_carlo.get('median_max_dd', 0):.2f}"],
        ['95th Pct Max DD', f"${monte_carlo.get('p95_max_dd', 0):.2f}"],
        ['P(50% drawdown)', f"{monte_carlo.get('prob_50pct_drawdown', 0):.2%}"],
        ['P(end below start)', f"{monte_carlo.get('prob_final_below_start', 0):.2%}"],
    ]
    
    with open(summary_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Metric', 'Value'])
        writer.writerows(summary_data)
    
    print(f"  ✅ Summary saved: {summary_csv}")

def create_strategy_breakdown_csv(report_path, strategy_csv):
    """Create per-strategy breakdown CSV"""
    
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    by_strategy = report.get('by_strategy', {})
    
    if not by_strategy:
        print(f"  ⚠️  No per-strategy data found")
        return
    
    fieldnames = [
        'strategy',
        'trades',
        'wins',
        'win_rate',
        'profit_factor',
        'net_pl',
        'gross_profit',
        'gross_loss',
    ]
    
    with open(strategy_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for strategy, stats in sorted(by_strategy.items(), key=lambda x: x[1]['net_pl'], reverse=True):
            writer.writerow({
                'strategy': strategy,
                'trades': stats['trades'],
                'wins': stats['wins'],
                'win_rate': round(stats['win_rate'], 2),
                'profit_factor': round(stats['profit_factor'], 3),
                'net_pl': round(stats['net_pl'], 2),
                'gross_profit': round(stats['gross_profit'], 2),
                'gross_loss': round(stats['gross_loss'], 2),
            })
    
    print(f"  ✅ Strategy breakdown saved: {strategy_csv}")

def main():
    print("=" * 100)
    print("EXPORTING BACKTEST TRADES TO CSV")
    print("=" * 100)
    
    # Output directory
    output_dir = Path("reports/csv_exports")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    configs = [
        {
            'name': 'OLD (0.5 SL / 1.5 TP)',
            'checkpoint': 'reports/backtest_checkpoints/checkpoint_portfolio_sl0.5_tp1.5.pkl',
            'report': 'reports/backtest_portfolio_sl0.5_tp1.5.json',
            'prefix': 'old_sl05_tp15'
        },
        {
            'name': 'NEW (0.1 SL / 2.0 TP)',
            'checkpoint': 'reports/backtest_checkpoints/checkpoint_portfolio_sl0.1_tp2.0.pkl',
            'report': 'reports/backtest_portfolio_sl0.1_tp2.0.json',
            'prefix': 'new_sl01_tp20'
        }
    ]
    
    for config in configs:
        print(f"\n{'='*100}")
        print(f"Processing: {config['name']}")
        print(f"{'='*100}")
        
        checkpoint_file = Path(config['checkpoint'])
        report_file = Path(config['report'])
        
        if not checkpoint_file.exists():
            print(f"  ❌ Checkpoint not found: {checkpoint_file}")
            continue
        
        if not report_file.exists():
            print(f"  ❌ Report not found: {report_file}")
            continue
        
        # Export trades
        trades_csv = output_dir / f"{config['prefix']}_all_trades.csv"
        trades_count = export_trades_to_csv(checkpoint_file, trades_csv)
        
        # Export summary
        summary_csv = output_dir / f"{config['prefix']}_summary.csv"
        create_summary_csv(config['prefix'], trades_count, report_file, summary_csv)
        
        # Export strategy breakdown
        strategy_csv = output_dir / f"{config['prefix']}_by_strategy.csv"
        create_strategy_breakdown_csv(report_file, strategy_csv)
    
    # Create comparison CSV
    print(f"\n{'='*100}")
    print("Creating comparison CSV...")
    print(f"{'='*100}")
    
    comparison_csv = output_dir / "comparison_summary.csv"
    
    comparison_data = [
        ['Metric', 'OLD (0.5/1.5)', 'NEW (0.1/2.0)', 'Change %', 'Winner'],
    ]
    
    # Load both reports
    old_report_path = Path('reports/backtest_portfolio_sl0.5_tp1.5.json')
    new_report_path = Path('reports/backtest_portfolio_sl0.1_tp2.0.json')
    
    if old_report_path.exists() and new_report_path.exists():
        with open(old_report_path, 'r') as f:
            old = json.load(f)['core_metrics']
        with open(new_report_path, 'r') as f:
            new = json.load(f)['core_metrics']
        
        metrics_to_compare = [
            ('Total Trades', 'trades', ''),
            ('Win Rate %', 'win_rate', '%'),
            ('Profit Factor', 'profit_factor', ''),
            ('Net P&L', 'net_pl', '$'),
            ('Expectancy/trade', 'expectancy', '$'),
            ('Avg Win', 'avg_win', '$'),
            ('Avg Loss', 'avg_loss', '$'),
            ('Payoff Ratio', 'payoff_ratio', 'x'),
            ('Max Drawdown %', 'max_drawdown_pct', '%'),
            ('Return %', 'return_pct', '%'),
        ]
        
        for label, key, unit in metrics_to_compare:
            old_val = old[key]
            new_val = new[key]
            
            change = ((new_val - old_val) / abs(old_val) * 100) if old_val != 0 else 0
            
            # Determine winner
            if key in ['max_drawdown_pct', 'avg_loss']:
                winner = 'OLD' if old_val < new_val else 'NEW'
            else:
                winner = 'NEW' if new_val > old_val else 'OLD'
            
            old_str = f"{unit}{old_val:.2f}" if unit else f"{old_val:.3f}"
            new_str = f"{unit}{new_val:.2f}" if unit else f"{new_val:.3f}"
            
            comparison_data.append([
                label,
                old_str,
                new_str,
                f"{change:+.1f}%",
                winner
            ])
        
        with open(comparison_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(comparison_data)
        
        print(f"  ✅ Comparison saved: {comparison_csv}")
    
    print(f"\n{'='*100}")
    print("EXPORT COMPLETE!")
    print(f"{'='*100}")
    print(f"\nAll CSV files saved to: {output_dir.absolute()}")
    print(f"\nFiles created:")
    for csv_file in sorted(output_dir.glob("*.csv")):
        file_size = csv_file.stat().st_size / 1024  # KB
        print(f"  - {csv_file.name} ({file_size:.1f} KB)")
    print(f"\n{'='*100}\n")

if __name__ == "__main__":
    main()
