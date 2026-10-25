"""
Quick backtest: EMA200 D1 gate vs EMA20 D1 gate
Compare performance metrics for XAUUSD trading with different EMA periods
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(parent_dir))
os.chdir(parent_dir)

import numpy as np
import pandas as pd
from src.data.fetcher import Fetcher
from src.strategies.portfolio_v5_6_leg import portfolio_v5
from src.core.risk_calc import RiskCalc
import MetaTrader5 as mt5

# Config
SYMBOL = "XAUUSDm"
START_BALANCE = 2000.0
SL_ATR = 0.5
TP_ATR = 1.5
SESSION_MULT = 1.0
RISK_PCT = 2.0


def calc_ema(closes: np.ndarray, period: int) -> np.ndarray:
    ema = np.full_like(closes, np.nan, dtype=float)
    if len(closes) >= period:
        multiplier = 2.0 / (period + 1.0)
        ema[period - 1] = np.mean(closes[:period])
        for i in range(period, len(closes)):
            ema[i] = (closes[i] - ema[i - 1]) * multiplier + ema[i - 1]
    return ema


def backtest_with_ema(ema_period: int):
    """Run backtest with specified EMA period for D1 gate"""
    
    if not mt5.initialize():
        print(f"MT5 init failed")
        return None
    
    fetcher = Fetcher(SYMBOL)
    risk = RiskCalc(SYMBOL)
    
    # Get data
    m15_rates = fetcher.get_rates_m15(bars=20000)
    d1_rates = fetcher.get_rates_d1(bars=500)
    
    if m15_rates is None or d1_rates is None:
        print("Failed to fetch data")
        mt5.shutdown()
        return None
    
    print(f"\n{'='*60}")
    print(f"Testing D1 EMA{ema_period} Gate")
    print(f"{'='*60}")
    print(f"M15 bars: {len(m15_rates)}, D1 bars: {len(d1_rates)}")
    
    # Calculate D1 EMA
    d1_closes = d1_rates["close"]
    d1_ema = calc_ema(d1_closes, ema_period)
    
    # Results storage
    trades = []
    balance = START_BALANCE
    peak = START_BALANCE
    max_dd = 0.0
    
    # Simulate trading
    for i in range(300, len(m15_rates) - 10):  # Leave room for indicators
        m15_window = m15_rates[i-300:i+1]
        
        # Get D1 bias
        d1_idx = len(d1_rates) - (len(m15_rates) - i) // 96 - 1
        if d1_idx < 0 or d1_idx >= len(d1_ema) - 2:
            continue
            
        d1_bias = None
        if not np.isnan(d1_ema[d1_idx]):
            d1_bias = "BULLISH" if d1_closes[d1_idx] > d1_ema[d1_idx] else "BEARISH"
        
        # Get signals from portfolio
        signals = []
        for strategy in portfolio_v5:
            sig = strategy.check(m15_window)
            if sig:
                signals.append((strategy.name, sig))
        
        # Process signals with D1 gate
        for strat_name, signal in signals:
            # Apply D1 gate
            if d1_bias:
                if signal.is_buy and d1_bias == "BEARISH":
                    continue  # Blocked
                if not signal.is_buy and d1_bias == "BULLISH":
                    continue  # Blocked
            
            # Calculate position size
            atr14 = risk.calc_atr(m15_window, 14)
            if atr14 < 0.01:
                continue
            
            sl_pips = SL_ATR * atr14 * SESSION_MULT
            tp_pips = TP_ATR * atr14 * SESSION_MULT
            
            pos_size = risk.calc_size_by_risk_pct(
                balance, RISK_PCT, sl_pips
            )
            
            if pos_size < 0.01:
                continue
            
            # Simulate outcome (simplified: use TP or SL hit)
            # For backtest, assume win if price moves TP distance before SL
            entry_price = m15_rates[i]["close"]
            
            # Look ahead to see outcome (up to 100 bars)
            win = False
            for j in range(i+1, min(i+100, len(m15_rates))):
                if signal.is_buy:
                    if m15_rates[j]["high"] >= entry_price + tp_pips:
                        win = True
                        break
                    if m15_rates[j]["low"] <= entry_price - sl_pips:
                        break
                else:
                    if m15_rates[j]["low"] <= entry_price - tp_pips:
                        win = True
                        break
                    if m15_rates[j]["high"] >= entry_price + sl_pips:
                        break
            
            # Calculate P&L
            if win:
                pnl = pos_size * tp_pips * 100  # $100 per lot per point
            else:
                pnl = -pos_size * sl_pips * 100
            
            balance += pnl
            
            # Track drawdown
            if balance > peak:
                peak = balance
            dd_pct = ((peak - balance) / peak) * 100
            if dd_pct > max_dd:
                max_dd = dd_pct
            
            trades.append({
                'time': m15_rates[i]['time'],
                'strategy': strat_name,
                'direction': 'BUY' if signal.is_buy else 'SELL',
                'd1_bias': d1_bias,
                'pnl': pnl,
                'balance': balance,
                'win': win
            })
    
    mt5.shutdown()
    
    # Calculate stats
    if not trades:
        print("No trades executed!")
        return None
    
    df = pd.DataFrame(trades)
    wins = df[df['win'] == True]
    losses = df[df['win'] == False]
    
    win_rate = len(wins) / len(df) * 100
    total_pnl = balance - START_BALANCE
    
    gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    
    # Count blocked trades (approximate by checking bias distribution)
    buys = df[df['direction'] == 'BUY']
    sells = df[df['direction'] == 'SELL']
    
    results = {
        'ema_period': ema_period,
        'total_trades': len(df),
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'final_balance': balance,
        'max_dd_pct': max_dd,
        'profit_factor': profit_factor,
        'buys': len(buys),
        'sells': len(sells),
        'gross_profit': gross_profit,
        'gross_loss': gross_loss
    }
    
    return results


def print_comparison(r1, r2):
    """Print side-by-side comparison"""
    print(f"\n{'='*70}")
    print(f"COMPARISON: EMA{r1['ema_period']} vs EMA{r2['ema_period']}")
    print(f"{'='*70}")
    print(f"{'Metric':<25} {'EMA' + str(r1['ema_period']):<20} {'EMA' + str(r2['ema_period']):<20} {'Winner':<10}")
    print(f"{'-'*70}")
    
    metrics = [
        ('Total Trades', 'total_trades', 'higher'),
        ('Win Rate %', 'win_rate', 'higher'),
        ('Total P&L $', 'total_pnl', 'higher'),
        ('Final Balance $', 'final_balance', 'higher'),
        ('Max DD %', 'max_dd_pct', 'lower'),
        ('Profit Factor', 'profit_factor', 'higher'),
        ('BUY Trades', 'buys', 'neutral'),
        ('SELL Trades', 'sells', 'neutral'),
    ]
    
    for label, key, better in metrics:
        v1 = r1[key]
        v2 = r2[key]
        
        if better == 'higher':
            winner = 'EMA' + str(r1['ema_period']) if v1 > v2 else 'EMA' + str(r2['ema_period'])
        elif better == 'lower':
            winner = 'EMA' + str(r1['ema_period']) if v1 < v2 else 'EMA' + str(r2['ema_period'])
        else:
            winner = '-'
        
        # Format values
        if 'pct' in key or 'rate' in key or 'factor' in key:
            v1_str = f"{v1:.2f}"
            v2_str = f"{v2:.2f}"
        elif 'pnl' in key or 'balance' in key:
            v1_str = f"${v1:.2f}"
            v2_str = f"${v2:.2f}"
        else:
            v1_str = f"{int(v1)}"
            v2_str = f"{int(v2)}"
        
        print(f"{label:<25} {v1_str:<20} {v2_str:<20} {winner:<10}")
    
    print(f"{'='*70}\n")


if __name__ == "__main__":
    print("Starting EMA comparison backtest...")
    print("This will take 1-2 minutes...\n")
    
    # Test EMA20 (current)
    results_20 = backtest_with_ema(20)
    
    # Test EMA200 (proposed)
    results_200 = backtest_with_ema(200)
    
    if results_20 and results_200:
        print_comparison(results_20, results_200)
        
        # Recommendation
        print("\nRECOMMENDATION:")
        if results_200['profit_factor'] > results_20['profit_factor']:
            improvement = ((results_200['profit_factor'] - results_20['profit_factor']) / results_20['profit_factor']) * 100
            print(f"✓ EMA200 is BETTER: PF improved by {improvement:.1f}%")
            print(f"  Switch to EMA200 for D1 gate")
        else:
            decline = ((results_20['profit_factor'] - results_200['profit_factor']) / results_20['profit_factor']) * 100
            print(f"✗ EMA200 is WORSE: PF declined by {decline:.1f}%")
            print(f"  Keep EMA20 for D1 gate")
