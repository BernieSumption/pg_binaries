param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
. (Join-Path $PSScriptRoot 'internal/dependencies/windows.ps1')
$source = Join-Path $Workspace 'sources/pg_jsonschema'
$pgRoot = Join-Path $Workspace 'postgresql'
$pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
foreach ($path in @($source, $pgConfig)) {
    if (-not (Test-Path $path)) { throw "Required pg_jsonschema build input is missing: $path" }
}

$pins = Get-PgJsonschemaToolchainPins
$rustVersion = $pins['rust_version']
$null = Set-PgJsonschemaWindowsEnvironment $Workspace $pins
$rustup = Join-Path $env:CARGO_HOME 'bin/rustup.exe'

$pgVersion = (& $pgConfig '--version').Trim()
$versionMatch = [regex]::Match($pgVersion, '^PostgreSQL\s+(\d+)')
if ($LASTEXITCODE -ne 0 -or -not $versionMatch.Success) { throw "Could not determine PostgreSQL major version from pg_config: $pgVersion" }
$pgFeature = "pg$($versionMatch.Groups[1].Value)"
$buildHook = Join-Path $PSScriptRoot 'internal/build.rs'
$sourceHook = Join-Path $source 'build.rs'
if (-not (Test-Path $sourceHook -PathType Leaf) -or
    (Get-FileHash $buildHook -Algorithm SHA256).Hash -ne (Get-FileHash $sourceHook -Algorithm SHA256).Hash) {
    Copy-Item $buildHook $sourceHook -Force
}

Push-Location $source
try {
    & $rustup 'run' $rustVersion 'cargo' 'pgrx' 'install' '--release' '--no-default-features' '--features' $pgFeature '--pg-config' $pgConfig
    if ($LASTEXITCODE -ne 0) { throw "cargo pgrx install failed for $pgFeature" }
} finally {
    Pop-Location
}

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
Copy-Item (Join-Path $moduleDir 'pg_jsonschema.dll') $modulePayload -Force
Copy-Item (Join-Path $sharedDir 'extension/pg_jsonschema.control') $extensionPayload -Force
Get-ChildItem (Join-Path $sharedDir 'extension') -File -Filter 'pg_jsonschema*.sql' |
    Copy-Item -Destination $extensionPayload -Force
