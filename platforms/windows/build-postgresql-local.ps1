param(
    [Parameter(Mandatory = $true)][string]$Workspace,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string]$SourceCache = (Join-Path $env:LOCALAPPDATA 'pg-binaries/sources')
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'environment.ps1')
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = Join-Path $env:PG_WINDOWS_TOOLS 'python/python.exe'
& $python (Join-Path $repo 'build.py') --target windows-x86_64 postgresql-build $Workspace --source-cache $SourceCache
if ($LASTEXITCODE) { throw 'PostgreSQL build failed' }
& $python (Join-Path $repo 'build.py') --target windows-x86_64 postgresql-package $Workspace $OutputDirectory
if ($LASTEXITCODE) { throw 'PostgreSQL packaging failed' }
