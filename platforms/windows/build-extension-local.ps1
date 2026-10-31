param(
    [Parameter(Mandatory = $true)][string]$Package,
    [Parameter(Mandatory = $true)][string]$DevelopmentArchive,
    [Parameter(Mandatory = $true)][string]$Workspace,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string]$SourceCache
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'environment.ps1')
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (-not $SourceCache) { $SourceCache = Join-Path $env:PG_WINDOWS_TOOLS 'sources' }
$python = Join-Path $env:PG_WINDOWS_TOOLS 'python/python.exe'
& $python (Join-Path $repo 'build.py') --target windows-x86_64 extension-build $Package $DevelopmentArchive $OutputDirectory --workspace $Workspace --source-cache $SourceCache --reuse-workspace
if ($LASTEXITCODE) { throw "Extension build failed: $Package" }
