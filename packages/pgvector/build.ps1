param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
$source = Join-Path $Workspace 'sources/pgvector'
$pgRoot = Join-Path $Workspace 'postgresql'
$pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
$makefile = Join-Path $source 'Makefile.win'
if (-not (Test-Path $makefile -PathType Leaf)) { throw 'Pinned pgvector source has no Makefile.win' }
if (-not (Test-Path $pgConfig -PathType Leaf)) { throw 'PostgreSQL development pg_config.exe is missing' }

$controlVersion = (Select-String -Path (Join-Path $source 'vector.control') -Pattern "^default_version\s*=\s*'([^']+)'\s*$").Matches[0].Groups[1].Value
$makefileVersion = (Select-String -Path $makefile -Pattern '^EXTVERSION\s*=\s*(\S+)').Matches[0].Groups[1].Value
if ($controlVersion -cne $makefileVersion) { throw 'pgvector Makefile.win and control file versions differ' }
if ($env:VSCMD_ARG_TGT_ARCH -and $env:VSCMD_ARG_TGT_ARCH -ne 'x64') { throw 'MSVC must target x64 for the Windows package' }
if (-not (Get-Command 'nmake.exe' -ErrorAction SilentlyContinue)) { throw 'nmake.exe is unavailable in the MSVC environment' }

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

$previousPgRoot = $env:PGROOT
$env:PGROOT = $pgRoot
Push-Location $source
try {
    & nmake.exe /F Makefile.win all 'PG_CFLAGS=/Z7 /O2 /fp:fast'
    if ($LASTEXITCODE -ne 0) { throw 'pgvector upstream Makefile.win build failed' }
} finally {
    Pop-Location
    $env:PGROOT = $previousPgRoot
}

Copy-Item (Join-Path $source 'vector.dll') (Join-Path $modulePayload 'vector.dll') -Force
Copy-Item (Join-Path $source 'vector.control') $extensionPayload -Force
Copy-Item (Join-Path $source 'sql/vector--*.sql') $extensionPayload -Force
