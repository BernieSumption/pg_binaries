param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
$source = Join-Path $Workspace 'sources/pgaudit'
$pgRoot = Join-Path $Workspace 'postgresql'
$pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
$makefile = Join-Path $source 'Makefile'
foreach ($path in @($source, $pgConfig, $makefile)) {
    if (-not (Test-Path $path)) { throw "Required pgAudit build input is missing: $path" }
}
if ((Get-Content $makefile -Raw) -notmatch '(?m)^MODULE_big\s*=\s*pgaudit\s*$' -or
    (Get-Content $makefile -Raw) -notmatch '(?m)^EXTENSION\s*=\s*pgaudit\s*$') {
    throw 'Pinned pgAudit Makefile no longer declares the expected module and extension'
}
$control = Join-Path $source 'pgaudit.control'
$versionLine = Select-String -Path $control -Pattern "^default_version\s*=\s*'([^']+)'\s*$"
if (-not $versionLine) { throw 'pgAudit control file has no default_version' }
$version = $versionLine.Matches[0].Groups[1].Value

$moduleDir = (& $pgConfig '--pkglibdir').Trim()
$sharedDir = (& $pgConfig '--sharedir').Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not read PostgreSQL installation paths from pg_config' }
$rootPath = [IO.Path]::GetFullPath($pgRoot).TrimEnd([char[]]@('\','/'))
function Get-RelativePath([string]$Path) {
    $fullPath = [IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($rootPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "PostgreSQL installation path is outside the workspace: $Path"
    }
    return $fullPath.Substring($rootPath.Length + 1)
}
$modulePayload = Join-Path (Join-Path $Workspace 'payload') (Get-RelativePath $moduleDir)
$extensionPayload = Join-Path (Join-Path (Join-Path $Workspace 'payload') (Get-RelativePath $sharedDir)) 'extension'
New-Item -ItemType Directory -Force $modulePayload,$extensionPayload | Out-Null

$compileDirectory = Join-Path $Workspace 'build/pgaudit'
& (Join-Path $repo 'platforms/windows/build-module.ps1') -PostgreSQL $pgRoot -SourceDirectory $source `
    -Module 'pgaudit' -Sources @('pgaudit.c') -OutputDirectory $compileDirectory

Copy-Item (Join-Path $compileDirectory 'pgaudit.dll') (Join-Path $modulePayload 'pgaudit.dll') -Force
Copy-Item $control $extensionPayload -Force
Copy-Item (Join-Path $source 'pgaudit*.sql') $extensionPayload -Force
