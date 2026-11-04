# One-screen health check for the bot on the VPS. Read-only: it never trades or changes anything.
#
#   powershell -ExecutionPolicy Bypass -File C:\projects\ultra_core\scripts\vps_check.ps1
$root = "C:\projects\ultra_core"
Set-Location $root
$py = Join-Path $root "venv\Scripts\python.exe"
$bad = @()

$cmds = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object { $_.CommandLine }
$wd = @($cmds | Where-Object { $_ -match "watchdog" }).Count
$ml = @($cmds | Where-Object { $_ -match "src\.core\.main_loop" }).Count
$pp = @($cmds | Where-Object { $_ -match "protect_profit" }).Count
# a venv python shows up twice (launcher + interpreter), so 2 lines = 1 copy
Write-Host ("Watchdog copies  : {0}" -f [math]::Ceiling($wd / 2))
Write-Host ("Trading loop     : {0}" -f $(if ($ml -gt 0) { "running" } else { "NOT running" }))
Write-Host ("Profit protector : {0}" -f $(if ($pp -gt 0) { "running" } else { "off" }))
if ($wd -eq 0) { $bad += "watchdog not running: start start_ultra_core.bat" }
if ($wd -gt 2) { $bad += "more than one watchdog: stop all python and start the bot once" }
if ($ml -eq 0) { $bad += "trading loop not running" }

$hb = Join-Path $root "logs\heartbeat"
if (Test-Path $hb) {
    $age = [int]((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds
    Write-Host "Last scan        : $age s ago"
    if ($age -gt 180) { $bad += "no scan for $age s" }
} else { $bad += "no heartbeat file" }

if (Test-Path (Join-Path $root "logs\HALT_LATCH.json")) {
    $bad += "HALTED: " + (Get-Content (Join-Path $root "logs\HALT_LATCH.json") -Raw)
}
if (Test-Path (Join-Path $root "STOP")) { $bad += "STOP file present (bot will not trade)" }

Select-String "ULTRA_TRADE_24H|ULTRA_PROTECT_PROFIT|ULTRA_ATLAS_MODE" .env.local | ForEach-Object { Write-Host ("Setting          : " + $_.Line) }
if (Test-Path VERSION.txt) { Write-Host ("Code version     : " + (Get-Content VERSION.txt).Substring(0, 7)) }

& $py -c "import MetaTrader5 as m; ok=m.initialize(); t=m.terminal_info() if ok else None; a=m.account_info() if ok else None; print('MT5              :', 'connected' if t and t.connected else 'NOT connected', '| algo trading', 'on' if t and t.trade_allowed else 'OFF'); print('Account          :', (f'{a.login} {a.server} | balance {a.balance:,.2f} | equity {a.equity:,.2f}') if a else 'none'); [print('Open trade       :', ('BUY', 'SELL')[p.type], p.volume, p.comment, 'P/L', round(p.profit, 2)) for p in (m.positions_get() or [])]; m.shutdown()"

# Bar feed freshness. The terminal can hold a live tick stream while its bar
# history is hours behind (seen 2026-11-04). The bot then fails its own liveness
# check and skips every signal evaluation, while the process, the heartbeat and
# the MT5 connection all look perfectly healthy -- which is why this check used
# to say ALL GOOD through three days with a missed trade.
$barAge = & $py -c "import MetaTrader5 as m, datetime as d; m.initialize(); r=m.copy_rates_from_pos('XAUUSDm', m.TIMEFRAME_M15, 0, 1); print(-1 if r is None or not len(r) else int(d.datetime.now(d.timezone.utc).timestamp()-int(r[-1]['time']))); m.shutdown()"
$barAge = [int]$barAge
if ($barAge -lt 0) {
    Write-Host "Newest M15 bar   : NONE"
    $bad += "the terminal has no M15 bars: open an XAUUSDm M15 chart so it downloads history"
} else {
    Write-Host ("Newest M15 bar   : {0} min old" -f [int]($barAge / 60))
    $dow = (Get-Date).ToUniversalTime().DayOfWeek
    $hr = (Get-Date).ToUniversalTime().Hour
    $marketOpen = -not ($dow -eq "Saturday" -or ($dow -eq "Sunday" -and $hr -lt 22) -or ($dow -eq "Friday" -and $hr -ge 21) -or ($hr -eq 21))
    if ($marketOpen -and $barAge -gt 1500) {
        $bad += "candle feed is STALE ($([int]($barAge/60)) min): the bot is skipping every signal. Open an XAUUSDm M15 chart in MT5, or restart the terminal"
    }
}

# What the bot itself said about its data recently.
if (Test-Path logs\main_loop.log) {
    $skips = @(Select-String -Path logs\main_loop.log -Pattern "LIVENESS CHECK FAILED|NO USABLE M15 DATA" -ErrorAction SilentlyContinue | Select-Object -Last 1)
    if ($skips.Count -gt 0) { Write-Host ("Last data skip   : " + $skips[0].Line.Trim()) }
    $sigs = @(Select-String -Path logs\main_loop.log -Pattern "BLOCKED|blocked" -ErrorAction SilentlyContinue | Select-Object -Last 3)
    foreach ($x in $sigs) { Write-Host ("Recent block     : " + $x.Line.Trim()) }
}

Write-Host "--- last 5 log lines ---"
Get-Content logs\main_loop.log -Tail 5
Write-Host "------------------------"
if ($bad.Count -eq 0) { Write-Host "RESULT: ALL GOOD" -ForegroundColor Green }
else { Write-Host "RESULT: PROBLEM" -ForegroundColor Red; $bad | ForEach-Object { Write-Host " - $_" -ForegroundColor Red } }
