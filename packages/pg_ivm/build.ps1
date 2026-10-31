param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
$source = Join-Path $Workspace 'sources/pg_ivm'
$pgRoot = Join-Path $Workspace 'postgresql'
$pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
$moduleDefinition = Join-Path $PSScriptRoot 'internal/windows-exports.def'
foreach ($path in @($source, $pgConfig, $moduleDefinition)) {
    if (-not (Test-Path $path)) { throw "Required pg_ivm build input is missing: $path" }
}

$control = Join-Path $source 'pg_ivm.control'
$versionLine = Select-String -Path $control -Pattern "^default_version\s*=\s*'([^']+)'\s*$"
if (-not $versionLine) { throw 'pg_ivm control file has no default_version' }
$version = $versionLine.Matches[0].Groups[1].Value
$meson = (Get-Command 'meson.exe' -ErrorAction SilentlyContinue)
if (-not $meson) { $meson = Get-Command 'meson' -ErrorAction Stop }
if (-not (Get-Command 'ninja.exe' -ErrorAction SilentlyContinue) -and -not (Get-Command 'ninja' -ErrorAction SilentlyContinue)) {
    throw 'Ninja is unavailable in the Windows development environment'
}
if ($env:VSCMD_ARG_TGT_ARCH -and $env:VSCMD_ARG_TGT_ARCH -ne 'x64') { throw 'MSVC must target x64 for the Windows package' }

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
$moduleRelative = Get-RelativePath $moduleDir
$sharedRelative = Get-RelativePath $sharedDir
$payload = Join-Path $Workspace 'payload'
$modulePayload = Join-Path $payload $moduleRelative
$extensionPayload = Join-Path (Join-Path $payload $sharedRelative) 'extension'
New-Item -ItemType Directory -Force $modulePayload,$extensionPayload | Out-Null

$build = Join-Path $Workspace 'build/pg_ivm'
$mesonFile = Join-Path $source 'meson.build'
$mesonText = [IO.File]::ReadAllText($mesonFile)
$modulePath = ([IO.Path]::GetFullPath($moduleDefinition) -replace '\\', '/')
if ($modulePath.Contains("'")) { throw 'pg_ivm module definition path cannot contain a single quote' }
$targetPattern = '(?m)^([ \t]*)install[ \t]*:[ \t]*true[ \t]*,'
$moduleLinkArgument = "link_args: ['/DEF:$modulePath'],"
if (-not $mesonText.Contains($moduleLinkArgument)) {
    if ([regex]::Matches($mesonText, $targetPattern).Count -ne 1) {
        throw 'Could not find the expected pg_ivm Meson shared-module target'
    }
    $newline = if ($mesonText.Contains("`r`n")) { "`r`n" } else { "`n" }
    $targetReplacement = "`$1$moduleLinkArgument$newline`$0"
    $mesonText = [regex]::Replace($mesonText, $targetPattern, $targetReplacement)
    [IO.File]::WriteAllText($mesonFile, $mesonText, [Text.UTF8Encoding]::new($false))
}
$env:PATH = "$(Join-Path $pgRoot 'bin');$env:PATH"
$previousCC = $env:CC
$env:CC = 'cl'
Push-Location $source
try {
    if (Test-Path (Join-Path $build 'meson-private/coredata.dat')) {
        & $meson.Source 'setup' '--reconfigure' $build "--prefix=$pgRoot" '--libdir=lib' '-Dbuildtype=release'
    } else {
        & $meson.Source 'setup' $build "--prefix=$pgRoot" '--libdir=lib' '-Dbuildtype=release'
    }
    if ($LASTEXITCODE -ne 0) { throw 'pg_ivm Meson configuration failed' }
    & $meson.Source 'compile' '-C' $build
    if ($LASTEXITCODE -ne 0) { throw 'pg_ivm upstream Meson build failed' }
} finally {
    Pop-Location
    $env:CC = $previousCC
}

Copy-Item (Join-Path $build 'pg_ivm.dll') (Join-Path $modulePayload 'pg_ivm.dll') -Force
Copy-Item $control $extensionPayload -Force
Copy-Item (Join-Path $source 'pg_ivm*.sql') $extensionPayload -Force
