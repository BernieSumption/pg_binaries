param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }
& (Join-Path $PSScriptRoot 'internal/dependencies/windows.ps1') -OS $OS -Arch $Arch -Workspace $Workspace
