# Operations runbook

The runtime inventory below describes the October 30, 2026 rehearsal on the AWS Windows VPS, using Exness demo and the stored Atlas Access $5K profile. Confirm the account and process identity on the VPS before maintenance. [Atlas rule verification](ATLAS_RULES_VERIFICATION.md)

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

| 📊 open trades, 📰 news pause, ℹ️ bot started | silent | Nothing |
| ℹ️ `Bot stopped: restarting it (attempt 1/3)` | silent | Nothing. It healed itself |
| ⚠️ MT5 connection lost / order rejected / restart attempt 2 / losses in a row | yes | Usually nothing; the message says if it needs you |
| ⚠️ `Atlas daily limit: … paused until tomorrow` | yes | Nothing. The bot restarts by itself at 05:30 IST (the new Atlas day) |
| 🚨 `Atlas safety stop` / `Bot halted` / `Bot is down: watchdog gave up` / other trades found | yes | **Act.** The message ends with 👉 and the exact step |

The pulse's **Daily limit** and **Max-loss limit** show the runtime's remaining equity headroom under its stored rule profile. Compare those limits with the account dashboard before relying on them. [Atlas rule verification](ATLAS_RULES_VERIFICATION.md)

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

## Stage a pinned VPS release

Use the downloaded GitHub revision ZIP, its exact commit, and the SHA-256 received from the release owner. These commands inspect and stage code. Production activation and account-state recovery have separate procedures. [Deployment readiness](DEPLOYMENT_READINESS.md) · [Atlas state recovery](ATLAS_STATE_RECOVERY.md)

```powershell
Set-Location C:\projects\ultra_core
powershell -NoProfile -File scripts\vps_check.ps1
.\venv\Scripts\python.exe -m scripts.halt status

$revision = '<full 40-character commit SHA>'
$archive = '<absolute path to downloaded revision ZIP>'
$archiveSha = '<verified 64-character SHA-256>'
powershell -NoProfile -File scripts\vps_update.ps1 -Revision $revision -ArchivePath $archive -ArchiveSha256 $archiveSha
.\venv\Scripts\python.exe scripts\demo_release.py --verify-release "release_staging\$revision"
```

The `STOP` file requests liquidation of open trades. For a maintenance shutdown, identify the exact watchdog and trading-loop processes on the VPS and follow the account-state procedure.

## Halts
A halt is stored in `logs/HALT_LATCH.json` and survives restarts. While it is set the watchdog does not restart the
trading loop. It sends one message and then waits.

- **Atlas stop caused only by the daily-loss limit**: the latch carries an expiry at the next 00:00 UTC (05:30 IST,
  the new Atlas day). It clears itself and the watchdog restarts the bot (owner decision 2026-10-30).
- **Everything else** (total drawdown, open-trade loss, margin, a rule-engine error, risk-rules hard halt,
  `halt set`): stays latched until an operator clears it after investigating. The watchdog can restart the bot once the latch clears.

The Atlas peak equity and daily reference are saved in `logs/atlas_state.json` every scan. **Do not delete or reset this file to make startup pass.** The18 November2026 schema2 implementation requires account/server/program/phase/rule binding and refuses missing, corrupt or legacy unbound history. Prepare an explicitly reviewed offline migration using [ATLAS_STATE_RECOVERY.md](ATLAS_STATE_RECOVERY.md) before upgrading an established account. No automatic phase change or fresh reset is allowed.

## Freeze
`tests/test_live_freeze.py` pins every live number (legs, magics, stops/targets, lot size, caps, Atlas thresholds,
trading hours, switch defaults). Changing any of them fails CI until that file is updated in the same commit.
