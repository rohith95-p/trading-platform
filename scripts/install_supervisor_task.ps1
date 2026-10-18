<#
 Registers a Windows Scheduled Task "UltraCoreSupervisor" that starts scripts\supervisor.py at BOOT and LOGON,
 restarts it after failure, wakes the PC for it, and keeps it running on battery.
 DEFAULT IS A DRY RUN (prints what it would do). Use -Apply to register. Use -Trade to start the bot in trade mode
 (default is measurement-only). It does not change power settings; set the PC to never sleep while plugged in yourself.
 Run from the project root:   powershell -ExecutionPolicy Bypass -File scripts\install_supervisor_task.ps1 [-Apply] [-Trade]
#>
param([switch]$Apply, [switch]$Trade)
$root = (Resolve-Path "$PSScriptRoot\..").Path
$py   = Join-Path $root "venv\Scripts\python.exe"
$modeArg = ""
if ($Trade) { $modeArg = " --trade" }
$taskArgs = "-X utf8 scripts\supervisor.py$modeArg"
$action   = New-ScheduledTaskAction -Execute $py -Argument $taskArgs -WorkingDirectory $root
$triggers = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -AtLogOn))
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -WakeToRun -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
            -MultipleInstances IgnoreNew
$modeText = "MEASUREMENT-ONLY"
if ($Trade) { $modeText = "TRADE" }
Write-Host "Task: UltraCoreSupervisor"
Write-Host "  run : $py $taskArgs"
Write-Host "  cwd : $root"
Write-Host "  mode: $modeText"
if (-not $Apply) { Write-Host "DRY RUN. Re-run with -Apply to register."; exit 0 }
Register-ScheduledTask -TaskName "UltraCoreSupervisor" -Action $action -Trigger $triggers -Settings $settings `
    -Description "Ultra Core supervisor (restarts the bot after crash/reboot; halt latch aware)" -Force | Out-Null
Write-Host "Registered. Disable the old 'UltraCoreBot' task so two launchers do not compete."
