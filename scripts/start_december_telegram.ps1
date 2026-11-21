# Install the demo notifications as a separate task in the MT5 user's session.
[CmdletBinding()]
param(
    [Parameter(Mandatory)][long]$ExpectedLogin,
    [Parameter(Mandatory)][string]$ExpectedServer,
    [string]$ExistingInstall = 'C:\projects\ultra_core'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$settings = Join-Path $ExistingInstall '.env.local'
$python = Join-Path $ExistingInstall 'venv\Scripts\python.exe'
$pythonw = Join-Path $ExistingInstall 'venv\Scripts\pythonw.exe'
$terminals = @(Get-Process terminal64 -ErrorAction SilentlyContinue)
if ($terminals.Count -ne 1 -or !$terminals[0].Path) {
    throw 'Expected one running MT5 terminal in this session.'
}
$terminal = $terminals[0].Path
$output = Join-Path $repo 'logs\december'
Push-Location $repo
try {
    & $python -m scripts.december_telegram --settings $settings --probe
    if ($LASTEXITCODE -ne 0) { throw 'Telegram bot or configured chat could not be reached.' }
} finally {
    Pop-Location
}
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$name = 'UltraCoreDecemberTelegram'
$existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
if ($existing.State -eq 'Running') {
    throw 'The December Telegram task is already running.'
}
$arguments = '-m scripts.december_telegram --settings "{0}" --terminal "{1}" --expected-login {2} --expected-server "{3}" --output "{4}"' -f $settings,$terminal,$ExpectedLogin,$ExpectedServer,$output
$action = New-ScheduledTaskAction -Execute $pythonw -Argument $arguments -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive
$taskSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Principal $principal -Settings $taskSettings -Force | Out-Null
Start-ScheduledTask -TaskName $name
Get-ScheduledTask -TaskName $name | Select-Object TaskName, State
