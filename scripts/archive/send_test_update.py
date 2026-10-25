from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import sys
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(Path(__file__).resolve().parents[1])

from src.core import alerts
import MetaTrader5 as mt5

IST = timezone(timedelta(hours=5, minutes=30))

if not mt5.initialize():
    print('MT5 init failed')
    exit(1)

account_info = mt5.account_info()
balance = account_info.balance
equity = account_info.equity

positions = mt5.positions_get(symbol='XAUUSDm')
num_positions = len(positions) if positions else 0
floating_pnl = sum(p.profit for p in positions) if positions else 0.0

# Get today's trades
today_str = datetime.now(IST).strftime('%Y-%m-%d')
trade_log_path = Path(f'logs/trades/{today_str}.jsonl')
day_pnl = 0.0
day_trades = 0

if trade_log_path.exists():
    with open(trade_log_path, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                trade = json.loads(line)
                if trade.get('kind') == 'closed':
                    day_pnl += trade.get('profit', 0.0)
                    day_trades += 1

time_str = datetime.now(IST).strftime('%I:%M %p')
pnl_emoji = '📈' if day_pnl > 0 else '📉' if day_pnl < 0 else '➖'

msg = (
    f'<b>⏰ TEST UPDATE - {time_str} IST</b>\n\n'
    f'🤖 Bot: 🟢 Running\n'
    f'💰 Balance: <b>${balance:.2f}</b>\n'
    f'💵 Equity: ${equity:.2f}\n\n'
    f'{pnl_emoji} <b>Day P&L: ${day_pnl:+.2f}</b>\n'
    f'📊 Trades: {day_trades}\n'
    f'📍 Open: {num_positions}\n'
    f'🔄 Floating: ${floating_pnl:+.2f}'
)

alerts.send(msg, severity=alerts.INFO)
print('✓ Test update sent to Telegram')
print(msg.replace('<b>', '').replace('</b>', ''))

mt5.shutdown()
