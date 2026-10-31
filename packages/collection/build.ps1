param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
$source = Join-Path $Workspace 'sources/collection'
$pgRoot = Join-Path $Workspace 'postgresql'
$pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
$makefile = Join-Path $source 'Makefile'
foreach ($path in @($source, $pgConfig, $makefile)) {
    if (-not (Test-Path $path)) { throw "Required pgcollection build input is missing: $path" }
}

$makefileText = Get-Content $makefile -Raw
$logicalMakefile = $makefileText -replace "\\\r?\n[ \t]*", ' '
if ($logicalMakefile -notmatch '(?m)^MODULE_big\s*=\s*\$\(EXTENSION\)\s*$' -or
    $logicalMakefile -notmatch '(?m)^EXTENSION\s*=\s*collection\s*$') {
    throw 'Pinned pgcollection Makefile no longer declares the expected module and extension'
}
$versionMatch = [regex]::Match($logicalMakefile, '(?m)^EXTVERSION\s*=\s*(\S+)')
$objectsMatch = [regex]::Match($logicalMakefile, '(?m)^OBJS\s*=\s*([^\r\n]+)')
if (-not $versionMatch.Success -or -not $objectsMatch.Success) { throw 'Could not read pgcollection version or object list from its Makefile' }
$version = $versionMatch.Groups[1].Value
$objects = @($objectsMatch.Groups[1].Value.Trim() -split '\s+' | Where-Object { $_ })
if (-not $objects.Count -or @($objects | Where-Object { $_ -notmatch '^[A-Za-z0-9_./]+\.o$' -or $_ -match '(^|/)\.\.?(/|$)' }).Count) {
    throw 'The upstream pgcollection object list contains an unsupported or empty source entry'
}
if (@($objects | Select-Object -Unique).Count -ne $objects.Count) { throw 'The upstream pgcollection object list contains duplicates' }

$controlTemplate = Join-Path $source 'collection.control.in'
$headerTemplate = Join-Path $source 'include/collection_config.h.in'
if (-not (Test-Path $controlTemplate -PathType Leaf) -or -not (Test-Path $headerTemplate -PathType Leaf)) {
    throw 'Upstream pgcollection control or configuration template is missing'
}
$control = Join-Path $source 'collection.control'
$header = Join-Path $source 'include/collection_config.h'
$controlText = [IO.File]::ReadAllText($controlTemplate).Replace('EXTVERSION', $version).Replace('EXTNAME', 'collection')
$headerText = [IO.File]::ReadAllText($headerTemplate).Replace('EXTVERSION', $version).Replace('EXTNAME', 'collection')
[IO.File]::WriteAllText($control, $controlText, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText($header, $headerText, [Text.UTF8Encoding]::new($false))

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

$sources = @($objects | ForEach-Object { $_.Substring(0, $_.Length - 2) + '.c' })
$compileDirectory = Join-Path $Workspace 'build/collection'
& (Join-Path $repo 'platforms/windows/build-module.ps1') -PostgreSQL $pgRoot -SourceDirectory $source `
    -Module 'collection' -Sources $sources -OutputDirectory $compileDirectory `
    -IncludeDirectories @((Join-Path $source 'include')) -Defines @('HASH_BLOOM=16')

Copy-Item (Join-Path $compileDirectory 'collection.dll') (Join-Path $modulePayload 'collection.dll') -Force
Copy-Item $control $extensionPayload -Force
Copy-Item (Join-Path $source 'sql/collection*.sql') $extensionPayload -Force
