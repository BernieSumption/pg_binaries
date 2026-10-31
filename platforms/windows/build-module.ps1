param(
    [Parameter(Mandatory = $true)][string]$PostgreSQL,
    [Parameter(Mandatory = $true)][string]$SourceDirectory,
    [Parameter(Mandatory = $true)][string]$Module,
    [Parameter(Mandatory = $true)][string[]]$Sources,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string[]]$IncludeDirectories = @(),
    [string[]]$Defines = @(),
    [string[]]$LibraryDirectories = @(),
    [string[]]$AdditionalLibraries = @()
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$pgConfig = Join-Path $PostgreSQL 'bin/pg_config.exe'
$dependencyInclude = Join-Path $PostgreSQL 'dependencies/include'
if (-not (Test-Path $dependencyInclude -PathType Container)) {
    throw "PostgreSQL development dependency headers are missing: $dependencyInclude"
}
function Get-PgConfigValue([string]$Option) {
    $value = (& $pgConfig $Option).Trim()
    if ($LASTEXITCODE -ne 0) { throw "pg_config $Option failed" }
    return $value
}
function Split-Flags([string]$Text) {
    $tokens = [Collections.Generic.List[string]]::new()
    foreach ($match in [regex]::Matches($Text, '"([^"]*)"|(\S+)')) {
        if ($match.Groups[1].Success) { $tokens.Add($match.Groups[1].Value) }
        else { $tokens.Add($match.Groups[2].Value) }
    }
    return $tokens.ToArray()
}

$serverInclude = Get-PgConfigValue '--includedir-server'
$publicInclude = Get-PgConfigValue '--includedir'
$libDir = Get-PgConfigValue '--libdir'
$compiler = (Get-Command 'cl.exe' -ErrorAction Stop).Source
$linker = (Get-Command 'link.exe' -ErrorAction Stop).Source
if ($env:VSCMD_ARG_TGT_ARCH -and $env:VSCMD_ARG_TGT_ARCH -ne 'x64') { throw 'MSVC must target x64 for Windows modules' }
$commonFlags = @('/nologo','/c','/MD','/O2','/DWIN32','/D_WINDOWS','/D_CRT_SECURE_NO_WARNINGS')
$pgFlags = @(Split-Flags (Get-PgConfigValue '--cppflags')) + @(Split-Flags (Get-PgConfigValue '--cflags'))
$includeFlags = @("/I$serverInclude", "/I$(Join-Path $serverInclude 'port/win32')",
    "/I$(Join-Path $serverInclude 'port/win32_msvc')", "/I$publicInclude", "/I$dependencyInclude")
$includeFlags += @($IncludeDirectories | ForEach-Object { "/I$_" })
$defineFlags = @($Defines | ForEach-Object { "/D$_" })
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$compiledObjects = @()
foreach ($relativeSource in $Sources) {
    if ($relativeSource -notmatch '^[A-Za-z0-9_./]+\.c$' -or $relativeSource -match '(^|/)\.\.?(/|$)') {
        throw "Unsupported module source path: $relativeSource"
    }
    $sourcePath = Join-Path $SourceDirectory ($relativeSource -replace '/', '\')
    $objectName = (($relativeSource -replace '[/\\]', '_') -replace '\.c$', '.obj')
    $objectPath = Join-Path $OutputDirectory $objectName
    $arguments = $commonFlags + $pgFlags + $includeFlags + $defineFlags + @("/I$SourceDirectory", "/Fo$objectPath", $sourcePath)
    & $compiler @arguments
    if ($LASTEXITCODE -ne 0) { throw "MSVC compilation failed for $Module source $relativeSource" }
    $compiledObjects += $objectPath
}

$dll = Join-Path $OutputDirectory "$Module.dll"
$linkArguments = @('/nologo','/DLL','/MACHINE:X64',"/OUT:$dll") + $compiledObjects + @("/LIBPATH:$libDir")
$linkArguments += @($LibraryDirectories | ForEach-Object { "/LIBPATH:$_" })
$linkArguments += @('postgres.lib') + $AdditionalLibraries
& $linker @linkArguments
if ($LASTEXITCODE -ne 0) { throw "MSVC linking failed for $Module" }
