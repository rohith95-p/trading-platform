# Update Ultra Core on the Windows VPS from GitHub (no git needed), then restart the bot.
#
#   powershell -ExecutionPolicy Bypass -File C:\projects\ultra_core\scripts\vps_update.ps1
#
# Keeps .env.local, logs\ and venv\ untouched. Open trades keep their stop and target at the broker
# while the bot is down for the few seconds of the restart. Never use the STOP file for this: it closes trades.
$ErrorActionPreference = "Stop"
$root = "C:\projects\ultra_core"
$repo = "rohith95-p/trading-platform"
$zip = Join-Path $env:TEMP "ultra_core_master.zip"
$tmp = Join-Path $env:TEMP "ultra_core_update"

$sha = (Invoke-RestMethod "https://api.github.com/repos/$repo/commits/master").sha
Write-Host "Latest version on GitHub: $($sha.Substring(0, 7))"
Invoke-WebRequest "https://github.com/$repo/archive/$sha.zip" -OutFile $zip
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive $zip $tmp -Force
$src = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName

Write-Host "Stopping the bot..."
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 3

robocopy $src $root /E /XD venv logs .git research /XF .env.local /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "copy failed (robocopy exit $LASTEXITCODE)" }
Set-Content (Join-Path $root "VERSION.txt") $sha
& (Join-Path $root "venv\Scripts\python.exe") -m pip install -q -r (Join-Path $root "requirements.txt")

Write-Host "Starting the bot..."
Start-Process (Join-Path $root "start_ultra_core.bat")
Write-Host "Updated to $($sha.Substring(0, 7)). Run scripts\vps_check.ps1 in 2 minutes to confirm."
