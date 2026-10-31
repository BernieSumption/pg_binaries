param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
$source = Join-Path $Workspace 'sources/hypopg'
$pgRoot = Join-Path $Workspace 'postgresql'
$pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
foreach ($path in @($source, $pgRoot, $pgConfig)) {
    if (-not (Test-Path $path)) { throw "Required HypoPG build input is missing: $path" }
}

$control = Join-Path $source 'hypopg.control'
$versionLine = Select-String -Path $control -Pattern "^default_version\s*=\s*'([^']+)'\s*$"
if (-not $versionLine) { throw 'HypoPG control file has no default_version' }
$version = $versionLine.Matches[0].Groups[1].Value

function Get-PgConfigValue([string]$Option) {
    $value = (& $pgConfig $Option).Trim()
    if ($LASTEXITCODE -ne 0) { throw "pg_config $Option failed" }
    return $value
}

function Get-RelativePath([string]$Root, [string]$Path) {
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd([char[]]@('\','/'))
    $fullPath = [IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($rootPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "PostgreSQL installation path is outside the workspace: $Path"
    }
    return $fullPath.Substring($rootPath.Length + 1)
}

function Split-Flags([string]$Text) {
    $tokens = [Collections.Generic.List[string]]::new()
    foreach ($match in [regex]::Matches($Text, '"([^"]*)"|(\S+)')) {
        if ($match.Groups[1].Success) { $tokens.Add($match.Groups[1].Value) }
        else { $tokens.Add($match.Groups[2].Value) }
    }
    return $tokens.ToArray()
}

$makefilePath = Join-Path $source 'Makefile'
$makefile = Get-Content $makefilePath -Raw
$logicalMakefile = $makefile -replace "\\\r?\n[ \t]*", ' '
if ($logicalMakefile -notmatch '(?m)^MODULE_big\s*=\s*hypopg\s*$' -or
    $logicalMakefile -notmatch '(?m)^EXTENSION\s*=\s*hypopg\s*$') {
    throw 'Upstream Makefile no longer declares the expected HypoPG module and extension'
}
$objectMatch = [regex]::Match($logicalMakefile, '(?m)^OBJS\s*=\s*([^\r\n]+)')
if (-not $objectMatch.Success) { throw 'Could not find the upstream HypoPG OBJS list' }
$objects = @($objectMatch.Groups[1].Value.Trim() -split '\s+' | Where-Object { $_ })
if (-not $objects.Count -or @($objects | Where-Object { $_ -notmatch '^[A-Za-z0-9_./]+\.o$' -or $_ -match '(^|/)\.\.?(/|$)' }).Count) {
    throw 'The upstream HypoPG OBJS list contains an unsupported or empty source entry'
}
if (@($objects | Select-Object -Unique).Count -ne $objects.Count) { throw 'The upstream HypoPG OBJS list contains duplicates' }

$pgInclude = Get-PgConfigValue '--includedir-server'
$pgPublicInclude = Get-PgConfigValue '--includedir'
$pgLibDir = Get-PgConfigValue '--libdir'
$pgLibrary = Join-Path $pgLibDir 'postgres.lib'
$moduleDir = Get-PgConfigValue '--pkglibdir'
$sharedDir = Get-PgConfigValue '--sharedir'
if (-not (Test-Path $pgInclude -PathType Container) -or -not (Test-Path $pgLibrary -PathType Leaf)) {
    throw 'The PostgreSQL development tree lacks server headers or lib/postgres.lib'
}

$compiler = (Get-Command 'cl.exe' -ErrorAction Stop).Source
$linker = (Get-Command 'link.exe' -ErrorAction Stop).Source
if ($env:VSCMD_ARG_TGT_ARCH -and $env:VSCMD_ARG_TGT_ARCH -ne 'x64') { throw 'MSVC must target x64 for the Windows package' }
$cflags = @(Split-Flags (Get-PgConfigValue '--cflags'))
$cppflags = @(Split-Flags (Get-PgConfigValue '--cppflags'))
$build = Join-Path $Workspace 'build/hypopg'
$payload = Join-Path $Workspace 'payload'
New-Item -ItemType Directory -Force $build,$payload | Out-Null
$compiledObjects = @()
foreach ($objectName in $objects) {
    $relativeSource = $objectName.Substring(0, $objectName.Length - 2) + '.c'
    $sourcePath = Join-Path $source ($relativeSource -replace '/', '\')
    if (-not (Test-Path $sourcePath -PathType Leaf)) { throw "Upstream HypoPG source is missing: $relativeSource" }
    $objectPath = Join-Path $build (($relativeSource -replace '[/\\]', '_') -replace '\.c$', '.obj')
    $arguments = @('/nologo','/c','/MD','/O2','/DWIN32','/D_WINDOWS','/D_CRT_SECURE_NO_WARNINGS') + $cppflags + $cflags + @(
        "/I$pgInclude", "/I$(Join-Path $pgInclude 'port/win32')", "/I$(Join-Path $pgInclude 'port/win32_msvc')",
        "/I$pgPublicInclude", "/I$source", "/Fo$objectPath", $sourcePath
    )
    & $compiler @arguments
    if ($LASTEXITCODE -ne 0) { throw "MSVC compilation failed for HypoPG source $relativeSource" }
    $compiledObjects += $objectPath
}

$dll = Join-Path $build 'hypopg.dll'
& $linker '/nologo' '/DLL' '/MACHINE:X64' "/OUT:$dll" $compiledObjects "/LIBPATH:$(Split-Path $pgLibrary -Parent)" 'postgres.lib'
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $dll -PathType Leaf)) { throw 'MSVC failed to link hypopg.dll' }

$moduleRelative = Get-RelativePath $pgRoot $moduleDir
$sharedRelative = Get-RelativePath $pgRoot $sharedDir
$modulePayload = Join-Path $payload $moduleRelative
$extensionPayload = Join-Path (Join-Path $payload $sharedRelative) 'extension'
New-Item -ItemType Directory -Force $modulePayload,$extensionPayload | Out-Null
Copy-Item $dll (Join-Path $modulePayload 'hypopg.dll')
Copy-Item $control $extensionPayload -Force
$sqlFiles = @(Get-ChildItem $source -File -Filter 'hypopg--*.sql')
if (-not $sqlFiles.Count) { throw 'Upstream HypoPG source contains no versioned SQL files' }
Copy-Item $sqlFiles.FullName $extensionPayload
