# Compile the pinned December demo EA for an already connected MT5 terminal.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][long]$ExpectedLogin,
    [Parameter(Mandatory)][string]$ExpectedServer,
    [string]$Python = 'C:\projects\ultra_core\venv\Scripts\python.exe'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$terminals = @(Get-Process terminal64 -ErrorAction SilentlyContinue)
if ($terminals.Count -ne 1 -or !$terminals[0].Path) {
    throw 'Expected one already-running MT5 terminal.'
}
$terminal = $terminals[0].Path
$editor = Join-Path (Split-Path -Parent $terminal) 'MetaEditor64.exe'
if (!(Test-Path -LiteralPath $editor -PathType Leaf)) { throw 'MetaEditor is missing.' }
$probe = @'
import json
import sys
import MetaTrader5 as mt5
if not mt5.initialize(sys.argv[1], timeout=5000):
    raise SystemExit('MT5 connection refused')
try:
    a, t = mt5.account_info(), mt5.terminal_info()
    p, o = mt5.positions_get(), mt5.orders_get()
    s = mt5.symbol_info('XAUUSDm')
    if not (a and t and t.connected and a.trade_mode == 0 and a.margin_mode == 2
            and a.currency == 'USD' and a.login == int(sys.argv[2]) and a.server == sys.argv[3]):
        raise SystemExit('Expected connected, USD hedging demo account')
    if p is None or o is None or p or o:
        raise SystemExit('Existing exposure or unknown orders')
    if not s or (s.digits, s.trade_contract_size, s.volume_min, s.volume_step) != (3, 100, .01, .01):
        raise SystemExit('Gold contract does not match the tested volume and price units')
    print(json.dumps({'data_path': t.data_path, 'algo': t.trade_allowed, 'leverage': a.leverage}))
finally:
    mt5.shutdown()
'@
$profile = (& $Python -c $probe $terminal $ExpectedLogin $ExpectedServer | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0 -or !$profile.data_path) { throw 'Read-only demo preflight failed.' }
$expertDir = Join-Path $profile.data_path 'MQL5/Experts/UltraCoreDecember'
$presetDir = Join-Path $profile.data_path 'MQL5/Presets'
New-Item -ItemType Directory -Force $expertDir,$presetDir | Out-Null
foreach ($name in 'DecemberAccessDemo.mq5','RetainedAtlas.mq5','NativeSignals.mqh','RetainedNews.mqh') {
    Copy-Item -LiteralPath (Join-Path $repo "research/mt5_retained/$name") -Destination $expertDir -Force
}
$source = Join-Path $expertDir 'DecemberAccessDemo.mq5'
$log = Join-Path $expertDir ("compile_" + [guid]::NewGuid().ToString('N') + '.log')
$p = Start-Process $editor -ArgumentList ('/compile:"'+$source+'"'),('/log:"'+$log+'"') -WindowStyle Hidden -PassThru
if (!$p.WaitForExit(20000)) { throw 'MetaEditor did not finish within 20 seconds.' }
if (!(Select-String -LiteralPath $log -Pattern '0 errors, 0 warnings')) {
    Get-Content -LiteralPath $log -Tail 12
    throw 'December demo EA failed compilation.'
}
@("ExpectedDemoLogin=$ExpectedLogin", "ExpectedDemoServer=$ExpectedServer", 'Roster=0',
  'Mask=5', 'PayoutGuard=false', 'FundedProtector=false') |
    Set-Content -LiteralPath (Join-Path $presetDir 'UltraCoreDecember.set') -Encoding Unicode
Write-Output "DECEMBER_EA_COMPILED DEMO_VERIFIED=true BROKER_LEVERAGE=$($profile.leverage) MT5_ALGO=$($profile.algo)"
Write-Output 'Navigator: Expert Advisors > UltraCoreDecember > DecemberAccessDemo'
Write-Output 'Preset: UltraCoreDecember.set'
