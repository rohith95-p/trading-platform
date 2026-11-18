# Prepare an immutable, pinned release. NEVER stops/starts services or changes live code.
# Supply a locally downloaded GitHub revision ZIP and its independently verified SHA256.
# Activation/rollback switching remains blocked until dedicated demo verification.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)] [ValidatePattern('^[0-9a-f]{40}$')] [string]$Revision,
    [Parameter(Mandatory=$true)] [ValidatePattern('^[0-9a-fA-F]{64}$')] [string]$ArchiveSha256,
    [Parameter(Mandatory=$true)] [string]$ArchivePath,
    [string]$Root = 'C:\projects\ultra_core'
)
$ErrorActionPreference = 'Stop'
$resolvedRoot = (Resolve-Path -LiteralPath $Root).Path
$archive = (Resolve-Path -LiteralPath $ArchivePath).Path
$py = Join-Path $resolvedRoot 'venv\Scripts\python.exe'
$script = Join-Path $PSScriptRoot 'demo_release.py'
if (-not (Test-Path -LiteralPath $py -PathType Leaf)) { throw 'Project interpreter not found' }
& $py $script --root $resolvedRoot --archive $archive --revision $Revision --archive-sha256 $ArchiveSha256
if ($LASTEXITCODE -ne 0) { throw 'Release preparation refused; live files were not changed' }
Write-Host 'Prepared only. No process was stopped or started. No production release was activated.'
