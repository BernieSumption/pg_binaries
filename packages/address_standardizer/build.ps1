param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
$source = Join-Path $Workspace 'sources/address_standardizer'
$pgRoot = Join-Path $Workspace 'postgresql'
$pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
$dependencies = Join-Path $Workspace 'build/dependencies'
foreach ($path in @($source, $pgConfig, (Join-Path $dependencies 'include/pcre2.h'),
        (Join-Path $dependencies 'lib/pcre2-8-static.lib'))) {
    if (-not (Test-Path $path)) { throw "Required Address Standardizer build input is missing: $path" }
}

$control = Join-Path $source 'address_standardizer.control'
$versionLine = Select-String -Path $control -Pattern "^default_version\s*=\s*'([^']+)'\s*$"
if (-not $versionLine) { throw 'Address Standardizer control file has no default_version' }
$version = $versionLine.Matches[0].Groups[1].Value
$makefile = Get-Content (Join-Path $source 'Makefile') -Raw
if ($makefile -notmatch '(?m)^MODULE_big\s*=\s*\$\(EXTENSION\)\s*$' -or
    $makefile -notmatch '(?m)^SRCS\s*=\s*\$\(wildcard src/\*\.c\)\s*$' -or
    $makefile -notmatch '(?m)^SHLIB_LINK\s*\+=\s*-lpcre2-8\s*$') {
    throw 'Pinned Address Standardizer Makefile no longer declares the expected module sources or PCRE2 link'
}

$dataDir = Join-Path $source 'data'
New-Item -ItemType Directory -Force $dataDir | Out-Null
function Write-ConcatenatedSql([string[]]$Inputs, [string]$Output) {
    $contents = [Text.StringBuilder]::new()
    foreach ($input in $Inputs) {
        $inputPath = Join-Path $dataDir ($input -replace '/', '\')
        if (-not (Test-Path $inputPath -PathType Leaf)) {
            $inputPath = Join-Path $source ($input -replace '/', '\')
        }
        if (-not (Test-Path $inputPath -PathType Leaf)) { throw "SQL input is missing: $input" }
        [void]$contents.Append([IO.File]::ReadAllText($inputPath))
    }
    [IO.File]::WriteAllText((Join-Path $dataDir $Output), $contents.ToString(), [Text.UTF8Encoding]::new($false))
}
Write-ConcatenatedSql @('sql/01_types.sql','sql/12_functions.sql') 'address_standardizer_core.sql'
Write-ConcatenatedSql @('address_standardizer_core.sql') "address_standardizer--$version.sql"
Write-ConcatenatedSql @('sql/12_functions.sql') "address_standardizer--ANY--$version.sql"
Write-ConcatenatedSql @('sql/13_us_lex.sql','sql/14_us_gaz.sql','sql/15_us_rules.sql','sql/16_data_extension.sql') 'address_standardizer_data_us_core.sql'
Write-ConcatenatedSql @('address_standardizer_data_us_core.sql') "address_standardizer_data_us--$version.sql"
Write-ConcatenatedSql @('address_standardizer_data_us_core.sql') "address_standardizer_data_us--ANY--$version.sql"

$pgVersion = (& $pgConfig '--version').Trim()
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL pg_config failed' }
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
$payload = Join-Path $Workspace 'payload'
$modulePayload = Join-Path $payload (Get-RelativePath $moduleDir)
$extensionPayload = Join-Path (Join-Path $payload (Get-RelativePath $sharedDir)) 'extension'
New-Item -ItemType Directory -Force $modulePayload,$extensionPayload | Out-Null

$sources = @(Get-ChildItem (Join-Path $source 'src') -File -Filter '*.c' | Sort-Object Name |
    ForEach-Object { "src/$($_.Name)" })
$parserPath = Join-Path $source 'src/address_parser.c'
$parserText = [IO.File]::ReadAllText($parserPath)
$legacyDebugMacro = '#define DBG(format, arg...) do { ; } while (0)'
$portableDebugMacro = '#define DBG(...) do { ; } while (0)'
$legacyMacroCount = [regex]::Matches($parserText, [regex]::Escape($legacyDebugMacro)).Count
$portableMacroCount = [regex]::Matches($parserText, [regex]::Escape($portableDebugMacro)).Count
if ($legacyMacroCount -eq 1 -and $portableMacroCount -eq 0) {
    $parserText = $parserText.Replace($legacyDebugMacro, $portableDebugMacro)
    [IO.File]::WriteAllText($parserPath, $parserText, [Text.UTF8Encoding]::new($false))
} elseif ($legacyMacroCount -ne 0 -or $portableMacroCount -ne 1) {
    throw 'Pinned Address Standardizer debug macro no longer matches the expected Windows compatibility patch'
}
$entryPoints = @{
    'address_parser.c' = @('parse_address','strip_explicit_country')
    'address_standardizer.c' = @('debug_standardize_address','standardize_address','standardize_address1')
}
foreach ($file in $entryPoints.Keys) {
    $sourcePath = Join-Path $source "src/$file"
    $sourceText = [IO.File]::ReadAllText($sourcePath)
    $originalText = $sourceText
    foreach ($entryPoint in $entryPoints[$file]) {
        $plainPrototype = "Datum $entryPoint(PG_FUNCTION_ARGS);"
        $exportedPrototype = "extern PGDLLEXPORT Datum $entryPoint(PG_FUNCTION_ARGS);"
        $plainCount = [regex]::Matches($sourceText, '(?m)^' + [regex]::Escape($plainPrototype) + '\r?$').Count
        $exportedCount = [regex]::Matches($sourceText, '(?m)^' + [regex]::Escape($exportedPrototype) + '\r?$').Count
        if ($plainCount -eq 1 -and $exportedCount -eq 0) {
            $sourceText = $sourceText.Replace($plainPrototype, $exportedPrototype)
        } elseif ($plainCount -ne 0 -or $exportedCount -ne 1) {
            throw "Pinned Address Standardizer declaration for $entryPoint does not match the expected Windows compatibility patch"
        }
    }
    if ($sourceText -cne $originalText) {
        [IO.File]::WriteAllText($sourcePath, $sourceText, [Text.UTF8Encoding]::new($false))
    }
}
$compileDirectory = Join-Path $Workspace 'build/address_standardizer'
$asVersionDefine = 'AS_VERSION=\"' + $version + '\"'
& (Join-Path $repo 'platforms/windows/build-module.ps1') -PostgreSQL $pgRoot -SourceDirectory $source `
    -Module 'address_standardizer' -Sources $sources -OutputDirectory $compileDirectory `
    -IncludeDirectories @((Join-Path $dependencies 'include')) `
    -Defines @($asVersionDefine,'PCRE_VERSION=2','PCRE2_STATIC') `
    -LibraryDirectories @((Join-Path $dependencies 'lib')) -AdditionalLibraries @('pcre2-8-static.lib')

Copy-Item (Join-Path $compileDirectory 'address_standardizer.dll') (Join-Path $modulePayload 'address_standardizer.dll') -Force
foreach ($name in @('address_standardizer.control','address_standardizer_data_us.control')) {
    Copy-Item (Join-Path $source $name) $extensionPayload -Force
}
foreach ($name in @(
    "address_standardizer--$version.sql", "address_standardizer--ANY--$version.sql",
    "address_standardizer_data_us--$version.sql", "address_standardizer_data_us--ANY--$version.sql"
)) {
    Copy-Item (Join-Path $dataDir $name) $extensionPayload -Force
}
