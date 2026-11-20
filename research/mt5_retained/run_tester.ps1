param(
    [Parameter(Mandatory=$true)][string]$Terminal,
    [Parameter(Mandatory=$true)][ValidateSet('portfolio','filtered','breakout','london')][string]$Roster,
    [Parameter(Mandatory=$true)][int]$Year,
    [string]$FromDate,
    [string]$ToDate,
    [string]$Phase='evaluation',
    [int]$Mask=7,
    [switch]$PayoutGuard,
    [ValidateSet('uniform','phase_split')][string]$Policy='uniform',
    [ValidatePattern('^[a-zA-Z0-9]+$')][string]$Attempt,
    [switch]$Compile
)
$ErrorActionPreference='Stop'
if($Year -notin 2025,2026){throw 'This research batch covers 2025 and 2026 only.'}
$terminalRoot=(Resolve-Path -LiteralPath $Terminal).Path
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$resultDir=Join-Path $root 'research/results/retained_mt5'
if($PayoutGuard -or $Attempt){$resultDir=Join-Path $root 'research/results/guarded_retained_mt5'}
$exe=Join-Path $terminalRoot 'terminal64.exe'
if(Get-Process terminal64 -ErrorAction SilentlyContinue | Where-Object Path -eq $exe){throw 'Selected isolated tester is already running.'}
$sourceDir=Join-Path $terminalRoot 'MQL5/Experts/RetainedResearch'
New-Item -ItemType Directory -Force $sourceDir,$resultDir | Out-Null
if($Compile){
 Get-ChildItem -LiteralPath $PSScriptRoot -File | Where-Object Extension -in '.mqh','.mq5' | Copy-Item -Destination $sourceDir -Force
 $editor=Join-Path $terminalRoot 'MetaEditor64.exe'
 $src=Join-Path $sourceDir 'RetainedAtlas.mq5'
 $log=Join-Path $terminalRoot 'retained_compile.log'
 $p=Start-Process $editor -ArgumentList '/portable',("/compile:"+$src),("/log:"+$log) -WindowStyle Hidden -PassThru
 $p.WaitForExit()
 $end=(Get-Content $log -Tail 1)
 if($end -notmatch '0 errors'){Get-Content $log -Tail 20;throw 'Compilation failed.'}
 $end
}
if(!(Test-Path "$sourceDir/RetainedAtlas.ex5")){throw 'EA binary missing.'}
$id=@{portfolio=0;filtered=1;breakout=2;london=3}[$Roster]
$suffix=if($Phase -eq 'evaluation'){''}else{"_$Phase"}
$name="${Year}_${Roster}${suffix}"
if(($PayoutGuard -or $Attempt) -and $Mask -ne 7){$name+='_mask'+$Mask}
if($Policy -eq 'phase_split'){$name+='_phase_split'}
if($Attempt){$name+='_'+$Attempt}
$base=if($PayoutGuard){'guarded_'+$name}else{'retained_'+$name}
$preset=$base+'.set'
$recordId="RetainedRun_"+[guid]::NewGuid().ToString("N")
@("RecordID=$recordId"; "Roster=$id"; "Mask=$Mask"; ("PayoutGuard="+$PayoutGuard.IsPresent.ToString().ToLowerInvariant()); ("FundedProtector="+($Phase -eq 'funded').ToString().ToLowerInvariant())) | Set-Content (Join-Path $terminalRoot "MQL5/Profiles/Tester/$preset") -Encoding Unicode
if(!$FromDate){$FromDate="$Year.01.01"}
if(!$ToDate){$ToDate=if($Year -eq 2026){'2026.11.01'}else{([string]($Year+1))+'.01.01'}}
$lev=if($Phase -eq 'funded'){'1:50'}else{'1:100'}
$profile=Get-Content (Join-Path $terminalRoot 'arch48_default.ini') -Raw
$values=@{Expert='RetainedResearch\RetainedAtlas.ex5';ExpertParameters=$preset;Report=$base;FromDate=$FromDate;ToDate=$ToDate;Leverage=$lev}
foreach($k in $values.Keys){$profile=[regex]::Replace($profile,("(?m)^"+$k+"=[^\r\n]*"),($k+'='+$values[$k]))}
if($profile -notmatch 'Expert=RetainedResearch' -or $profile -notmatch 'Model=4' -or $profile -notmatch 'AllowLiveTrading=0'){throw 'Tester configuration mismatch.'}
$cfg=Join-Path $terminalRoot ($base+'.ini')
$profile | Set-Content $cfg
$time=(Get-Date)
$proc=Start-Process $exe -ArgumentList '/portable',("/config:"+$cfg) -WindowStyle Hidden -PassThru
$proc.WaitForExit()
$html=Get-Item (Join-Path $terminalRoot ($base+'.htm'))
if($html.LastWriteTime -lt $time -or $html.Length -lt 10000){throw 'New complete report missing.'}
$report=Get-Content $html.FullName -Raw -Encoding Unicode
if(!$report.Contains("M15 ($FromDate - $ToDate)") -or !$report.Contains('100% real ticks')){throw "Tester did not complete the requested real-tick period for $name."}
$report.Replace($base+'-', $name+'-').Replace($base+'.png',$name+'.png') | Set-Content (Join-Path $resultDir ($name+'.htm')) -Encoding Unicode
Get-ChildItem -Path (Join-Path $terminalRoot ($base+'*.png')) | ForEach-Object {Copy-Item $_.FullName (Join-Path $resultDir ($_.Name.Replace($base,$name))) -Force}
$common=Join-Path $env:APPDATA 'MetaQuotes/Terminal/Common/Files'
$leverage=if($Phase -eq 'funded'){50}else{100}
$prefix=if($PayoutGuard){"GuardedAtlas_${Mask}_"}else{"RetainedAtlas_"}
$startDate=[DateTimeOffset]::ParseExact($FromDate,'yyyy.MM.dd',[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::AssumeUniversal)
$dealFile=Get-ChildItem $common -File -Filter "${prefix}${id}_*_${leverage}.csv" | Where-Object {
  $epoch=[long](($_.BaseName -split '_')[-2])
  $_.LastWriteTime -ge $time -and $epoch -ge $startDate.ToUnixTimeSeconds() -and $epoch -lt $startDate.AddDays(5).ToUnixTimeSeconds()
} | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$uniqueFile=Get-Item (Join-Path $common ($recordId+'.csv')) -ErrorAction SilentlyContinue
if($uniqueFile){$dealFile=$uniqueFile}
if(!$dealFile){throw 'Missing native deal export.'}
if($dealFile){Copy-Item $dealFile.FullName (Join-Path $resultDir ($name+'_deals.csv')) -Force}
Write-Output "Finished $name"
