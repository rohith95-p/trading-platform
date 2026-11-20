param([int]$Year=2026,[int]$Mask=7,[string]$From,[switch]$Funded,[switch]$Compile,[switch]$Probe,[string]$Label="joint",[string]$TerminalName="Joint")
$ErrorActionPreference='Stop'
$terminal=Join-Path $env:TEMP ("UltraEAReview20261120/"+$TerminalName)
$out=Join-Path $PSScriptRoot '../results/mt5_joint'
$dest=Join-Path $terminal 'MQL5/Experts/JointResearch'
New-Item -ItemType Directory -Path $dest,$out -Force | Out-Null
if($Compile) {
  Copy-Item "$PSScriptRoot/Joint.mq5","$PSScriptRoot/LunaNotifications.mqh","$PSScriptRoot/../mt5_retained/RetainedAtlas.mq5","$PSScriptRoot/../mt5_retained/NativeSignals.mqh","$PSScriptRoot/../mt5_retained/RetainedNews.mqh" $dest -Force
  $src=Join-Path $dest "RetainedAtlas.mq5"
  (Get-Content $src -Raw).Replace("GuardedAtlas_","JointExport_") | Set-Content $src
  $p=Start-Process "$terminal/MetaEditor64.exe" -ArgumentList '/portable',("/compile:"+$dest+"/Joint.mq5"),("/log:"+$terminal+"/joint_compile.log") -WindowStyle Hidden -PassThru
  $p.WaitForExit()
  Get-Content "$terminal/joint_compile.log" -Tail 2
  if((Get-Content "$terminal/joint_compile.log" -Tail 1) -notmatch '0 errors'){throw 'Joint compile failed'}
}
$phase=if($Funded){'funded'}else{'evaluation'}
$id="${Label}_${Year}_${Mask}_${phase}"
if(!$From){$From="$Year.01.01"}
$to=if($Year -eq 2026){'2026.11.01'}else{'2026.01.01'}
$lev=if($Funded){50}else{100}
@("Roster=0"; "Mask=$Mask"; "PayoutGuard=true"; ("FundedProtector="+$Funded.IsPresent.ToString().ToLower()); "CopyLuna=true"; ("ChartProbe="+$Probe.IsPresent.ToString().ToLower())) | Set-Content "$terminal/MQL5/Profiles/Tester/$id.set" -Encoding Unicode
$profile=Get-Content "$terminal/arch48_default.ini" -Raw
$values=@{Expert='JointResearch\Joint.ex5';ExpertParameters="$id.set";Report=$id;FromDate=$From;ToDate=$to;Leverage="1:$lev"}
foreach($k in $values.Keys){$profile=[regex]::Replace($profile,("(?m)^"+$k+"=[^\r\n]*"),($k+'='+$values[$k]))}
if($profile -notmatch 'Model=4' -or $profile -notmatch 'AllowLiveTrading=0'){throw 'Tester-only setup required'}
$profile | Set-Content "$terminal/$id.ini"
$start=Get-Date
$p=Start-Process "$terminal/terminal64.exe" -ArgumentList '/portable',("/config:"+(Get-Item "$terminal/$id.ini").FullName) -WindowStyle Hidden -PassThru
$p.WaitForExit()
$report=Get-Item "$terminal/$id.htm"
if($report.LastWriteTime -lt $start){throw 'Stale report'}
$html=Get-Content $report.FullName -Raw -Encoding Unicode
if(!$html.Contains("M15 ($From - $to)") -or !$html.Contains('100% real ticks')){throw 'Incomplete real tick test'}
Copy-Item $report.FullName $out -Force
Get-ChildItem "$terminal/$id*.png" | Copy-Item -Destination $out -Force
$common=Join-Path $env:APPDATA 'MetaQuotes/Terminal/Common/Files'
$file=Get-ChildItem $common -Filter "JointAtlas_${Mask}_*_${lev}.csv" | Where-Object LastWriteTime -ge $start | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(!$file){throw 'Missing export'}
Copy-Item $file.FullName "$out/${id}_deals.csv" -Force
$log=Get-ChildItem "$terminal/Tester/logs" -Filter '*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if($log){Select-String -Path $log.FullName -Pattern 'JOINT_COUNTS' | Select-Object -Last 1 | % Line | Set-Content "$out/${id}_journal.txt"}
