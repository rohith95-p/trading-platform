# Operations runbook (current as of 2026-10-30)

The bot runs on the AWS Windows VPS only (never also on the PC). Account: Exness demo 198874999, server
Exness-MT5Trial11, Atlas "1 Step Access $5K" rehearsal (`ULTRA_ATLAS_MODE=1`).

## What runs
| Process | Started by | Job |
|---|---|---|
| `scripts/watchdog.py` | `start_ultra_core.bat` | Starts and restarts the trading loop, stands down while a halt is latched, sends the hourly pulse |
| `src.core.main_loop` | the watchdog | Scans every 60 s, places trades, writes `logs/heartbeat` and `logs/status.json` every scan |
| `scripts/protect_profit.py` | the watchdog, only if `ULTRA_PROTECT_PROFIT` is not `0` | Early profit-taking. **Off since 2026-10-30 (owner decision)** |

Settings live in `.env.local` (never committed): `ULTRA_ATLAS_MODE=1`, `ULTRA_TRADE_24H=1`, `ULTRA_PROTECT_PROFIT=0`,
Telegram token/chat, and on the VPS `SSL_CERT_FILE` (certifi). Optional: `ULTRA_PULSE_EVERY_H` (default 1, 0 = off),
`ULTRA_FLOAT_UPDATE_MIN` (default 30).

## Telegram messages
Only problems make a sound. Routine messages arrive silently.

| Message | Sound | What to do |
|---|---|---|
| 🟢 / 🔴 `BUY` / `SELL 0.02 lot opened` (strategy, entry price, stop, target, time, ticket, one per line) | yes | Nothing. Stop and target are already at the broker |
| ✅ / ❌ `Trade closed +$x` / `−$x` (strategy, entry and exit price with times, held, result, balance) | yes | Nothing |
| 📅 `Day summary` at 23:59 IST (every trade of the day, day net, balance; also written to `logs/trade_journal.csv`) | silent | Nothing |
| 💚 `All good · HH:00` (hourly, Mon–Fri) | silent | Nothing. **If it stops arriving, something is wrong** |

In the pulse, **Daily limit: $X left** is how much equity can still fall today before the Atlas daily rule trips. It is measured from the day's reference (the previous day's highest equity), so profit made today adds to it: up $50 today means $250 + $50 = $300 left. **Max-loss limit** is measured from the highest equity ever reached minus $500, so it does not grow with today's profit until that profit sets a new high.
| 📊 open trades, 📰 news pause, ℹ️ bot started | silent | Nothing |
| ℹ️ `Bot stopped: restarting it (attempt 1/3)` | silent | Nothing. It healed itself |
| ⚠️ MT5 connection lost / order rejected / restart attempt 2 / losses in a row | yes | Usually nothing; the message says if it needs you |
| ⚠️ `Atlas daily limit: … paused until tomorrow` | yes | Nothing. The bot restarts by itself at 05:30 IST (the new Atlas day) |
| 🚨 `Atlas safety stop` / `Bot halted` / `Bot is down: watchdog gave up` / other trades found | yes | **Act.** The message ends with 👉 and the exact step |

## When each strategy trades (IST, Mon–Fri)
| Time (IST) | Strategy | Trades/month (backtest) | Usually closes |
|---|---|---|---|
| 12:45 | Asian Range Filtered: Asian-range breakout with a size filter | ~3 | within 2–6 h |
| 12:45 | Asian Breakout: same breakout without the filter (rare) | <1 | within 5–8 h |
| 17:45 | London Momentum Tight: London/NY overlap continuation | ~5 | within 1–3 h |
| 17:45–21:30 | NY Session Reversal: NY session sweep reversal | ~4 | within 2 h (some overnight) |

Altogether about 12 trades a month (Donchian Trend was removed 2026-10-30: break-even on its own) and roughly half of weekdays get a trade. The D1 trend gate blocks trades against
the daily trend for every strategy (only sells while gold closes below its 20-day average, only buys
while above). Skipping it, as live did until 2026-10-30, was break-even in the backtests. Fridays: no new trades after 21:30 IST,
everything is closed at 22:30 IST.

## Lot size
Every trade is **one order of 0.02 lots**. Not 0.03, and not split into smaller orders. At most 3 trades can be open
at once (0.06 lots total). At 0.02 lots a $1 move in gold is $2. A typical stop-loss costs $17–35 (0.3–0.7% of $5,000)
and a take-profit pays about twice that. The size comes from `risk_rules.SIZING_LADDER` (0.02 above $800 balance).

## Commands (PowerShell on the VPS)
```powershell
# health check (read-only)
powershell -ExecutionPolicy Bypass -File C:\projects\ultra_core\scripts\vps_check.ps1
# update to the latest GitHub version and restart (keeps .env.local and logs)
powershell -ExecutionPolicy Bypass -File C:\projects\ultra_core\scripts\vps_update.ps1
# halt latch
cd C:\projects\ultra_core; venv\Scripts\python.exe -m scripts.halt status
cd C:\projects\ultra_core; venv\Scripts\python.exe -m scripts.halt clear --note "checked"
# stop the bot without touching open trades (their stop/target stay at the broker)
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
```
Do **not** create a `STOP` file to stop the bot: that closes every open trade.

## Halts
A halt is stored in `logs/HALT_LATCH.json` and survives restarts. While it is set the watchdog does not restart the
trading loop. It sends one message and then waits.

- **Atlas stop caused only by the daily-loss limit**: the latch carries an expiry at the next 00:00 UTC (05:30 IST,
  the new Atlas day). It clears itself and the watchdog restarts the bot (owner decision 2026-10-30).
- **Everything else** (total drawdown, open-trade loss, margin, a rule-engine error, risk-rules hard halt,
  `halt set`): stays until you clear it with the command above. The watchdog restarts the bot within a minute.

The Atlas peak equity and daily reference are saved in `logs/atlas_state.json` every scan, so a restart keeps the
real floors. Delete that file only when starting a brand-new Atlas account.

## Freeze
`tests/test_live_freeze.py` pins every live number (legs, magics, stops/targets, lot size, caps, Atlas thresholds,
trading hours, switch defaults). Changing any of them fails CI until that file is updated in the same commit.
