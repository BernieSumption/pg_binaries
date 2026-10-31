param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
. (Join-Path $PSScriptRoot 'internal/dependencies/windows.ps1')
$pgConfig = Join-Path $Workspace 'postgresql/bin/pg_config.exe'
if (-not (Test-Path $pgConfig -PathType Leaf)) { throw "PostgreSQL pg_config is missing: $pgConfig" }
$pins = Get-PgJsonschemaToolchainPins
Initialize-PgJsonschemaWindowsToolchain $Workspace $pins $pgConfig
