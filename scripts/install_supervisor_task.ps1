<#
 Registers a Windows Scheduled Task "UltraCoreSupervisor" that starts scripts\supervisor.py at LOGON (and at BOOT when
 run from an elevated/administrator shell), restarts it after failure, wakes the PC for it, and keeps it running on battery.
 DEFAULT IS A DRY RUN (prints what it would do). Use -Apply to register. Use -Trade to start the bot in trade mode
 (default is measurement-only). It does not change power settings; set the PC to never sleep while plugged in yourself.
 The script VERIFIES the task exists after registering and reports honestly if it does not.
 Run from the project root:   powershell -ExecutionPolicy Bypass -File scripts\install_supervisor_task.ps1 [-Apply] [-Trade]
#>
param([switch]$Apply, [switch]$Trade)
$root = (Resolve-Path "$PSScriptRoot\..").Path
$py   = Join-Path $root "venv\Scripts\python.exe"
$modeArg = ""
if ($Trade) { $modeArg = " --trade" }
$taskArgs = "-X utf8 scripts\supervisor.py$modeArg"
$action   = New-ScheduledTaskAction -Execute $py -Argument $taskArgs -WorkingDirectory $root
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

$desc = "Ultra Core supervisor (restarts the bot after crash/reboot; halt latch aware)"
# Self-relaunch (2026-10-21): the task died with the PC's sleep/off and only a logon trigger existed. A 5-minute repeating
# trigger relaunches it; MultipleInstances=IgnoreNew keeps it to a single supervisor while one is running.
$repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$registered = $false
# 1) logon + boot (boot trigger needs administrator rights)
try {
    $both = @((New-ScheduledTaskTrigger -AtStartup), (New-ScheduledTaskTrigger -AtLogOn), $repeat)
    Register-ScheduledTask -TaskName "UltraCoreSupervisor" -Action $action -Trigger $both -Settings $settings -Description $desc -Force -ErrorAction Stop | Out-Null
    $registered = $true
    Write-Host "Registered with triggers: AtStartup + AtLogOn"
} catch {
    Write-Host "Boot trigger not permitted (needs an administrator shell): $($_.Exception.Message)"
}
# 2) fall back to logon only (works for the current user without elevation)
if (-not $registered) {
    try {
        $logon = @((New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME), $repeat)
        Register-ScheduledTask -TaskName "UltraCoreSupervisor" -Action $action -Trigger $logon -Settings $settings -Description $desc -Force -ErrorAction Stop | Out-Null
        $registered = $true
        Write-Host "Registered with trigger: AtLogOn only. Re-run from an administrator shell to add the AtStartup (boot) trigger."
    } catch {
        Write-Host "Registration FAILED: $($_.Exception.Message)"
    }
}
$t = Get-ScheduledTask -TaskName "UltraCoreSupervisor" -ErrorAction SilentlyContinue
if ($null -eq $t) { Write-Host "VERIFY: task UltraCoreSupervisor does NOT exist."; exit 1 }
Write-Host "VERIFY: task exists, state=$($t.State)"
Write-Host "Disable the old 'UltraCoreBot' task so two launchers do not compete."
