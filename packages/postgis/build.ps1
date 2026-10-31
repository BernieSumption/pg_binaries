param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'internal/dependencies/windows-environment.ps1')
Invoke-PostGISWindowsRecipe $OS $Arch $Workspace (Join-Path $PSScriptRoot 'internal/windows-build.sh')
