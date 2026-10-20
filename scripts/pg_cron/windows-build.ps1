param(
  [Parameter(Mandatory = $true)][string]$CoreArchive,
  [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$CoreSha256,
  [Parameter(Mandatory = $true)][string]$CoreSymbolsDirectory,
  [Parameter(Mandatory = $true)][string]$SourceArchive,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [ValidateSet('15.19','16.15','17.11','18.6')][string]$PostgreSQLVersion = '18.6',
  [string]$BuildId = $env:BUILD_ID,
  [string]$SourceRevision = $env:SOURCE_REVISION
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Set-StrictMode -Version Latest

if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
  throw 'This recipe requires Windows x86-64.'
}
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$coreArchive = (Resolve-Path $CoreArchive).Path
$sourceArchive = (Resolve-Path $SourceArchive).Path
$coreSymbolsDirectory = (Resolve-Path $CoreSymbolsDirectory).Path
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
if (-not $BuildId) { $BuildId = "local-$([guid]::NewGuid().ToString('N'))" }
if ($BuildId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') { throw 'BuildId contains unsupported characters.' }
if (-not $SourceRevision) { $SourceRevision = (& git -C $repo rev-parse HEAD).Trim() }
if ($SourceRevision -notmatch '^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$') { throw 'SourceRevision must be a full Git object ID.' }

$python = (Get-Command python.exe -ErrorAction Stop).Source
$tar = (Get-Command tar.exe -ErrorAction Stop).Source
$pgVersion = $PostgreSQLVersion
$cronVersion = '1.6.8'
$sourceUrl = 'https://github.com/citusdata/pg_cron/archive/refs/tags/v1.6.8.tar.gz'
$sourceShaExpected = 'c19ab9bb35406c60fb51ecda993737c083850abe424acb6c1030439d00a1f8e4'
$coreName = "postgresql-$pgVersion-windows-x86_64.tar.gz"
if ((Split-Path $coreArchive -Leaf) -cne $coreName) { throw "Core archive must be named $coreName" }
if (-not (Test-Path "$coreArchive.sha256" -PathType Leaf)) { throw 'Selected core archive has no SHA-256 sidecar.' }
$coreSidecar = (Get-Content "$coreArchive.sha256" -Raw).Trim() -split '\s+'
if ($coreSidecar.Count -lt 2 -or $coreSidecar[-1] -cne $coreName) { throw 'Selected core archive SHA-256 sidecar is invalid.' }
$coreSha = (Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($coreSidecar[0] -notmatch '^[0-9a-fA-F]{64}$' -or $coreSha -cne $coreSidecar[0].ToLowerInvariant()) { throw 'Selected core archive SHA-256 sidecar mismatch.' }
$pinnedCoreSha = (& $python (Join-Path $repo 'tools/windows_core_pin.py') --postgresql-version $pgVersion --field sha256).Trim()
if ($LASTEXITCODE -ne 0 -or $pinnedCoreSha -cne $CoreSha256.ToLowerInvariant() -or $coreSha -cne $pinnedCoreSha) {
  throw "Core archive does not match the checked PostgreSQL $pgVersion Windows core identity."
}
$sourceSha = (Get-FileHash $sourceArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($sourceSha -cne $sourceShaExpected) { throw 'Source archive does not match the pg_cron 1.6.8 release identity.' }

$work = Join-Path $env:TEMP ("pgcron-windows-" + [guid]::NewGuid().ToString('N'))
$coreRoot = Join-Path $work 'core'
$sourceRoot = Join-Path $work 'source'
$pgRoot = Join-Path $coreRoot 'postgresql'
$cronRoot = Join-Path $sourceRoot "pg_cron-$cronVersion"
$stage = Join-Path $work 'stage/pg_cron'
New-Item -ItemType Directory -Force $coreRoot,$sourceRoot,(Join-Path $stage 'lib'),(Join-Path $stage 'share/extension'),(Join-Path $stage 'LICENSES') | Out-Null
try {
  & $tar -xzf $coreArchive -C $coreRoot
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the selected PostgreSQL core archive.' }
  $manifest = Get-Content (Join-Path $pgRoot 'manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.component -cne 'postgresql' -or $manifest.version -cne $pgVersion -or $manifest.platform -cne 'windows' -or $manifest.architecture -cne 'x86_64') {
    throw 'Core archive manifest does not match the selected PostgreSQL Windows target.'
  }
  $pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
  if (-not (Test-Path $pgConfig -PathType Leaf) -or (& $pgConfig --version) -cne "PostgreSQL $pgVersion") { throw 'Core archive pg_config identity is invalid.' }
  foreach ($required in @('include/server/postgres.h','lib/postgres.lib','lib/libpq.lib')) {
    if (-not (Test-Path (Join-Path $pgRoot $required) -PathType Leaf)) { throw "Core archive lacks required Windows development file: $required" }
  }
  $members = @(& $tar -tzf $sourceArchive)
  if ($LASTEXITCODE -ne 0 -or -not ($members | Where-Object { $_ -ceq "pg_cron-$cronVersion/Makefile.win" })) { throw 'Source archive does not contain the expected pg_cron release root and Makefile.win.' }
  & $tar -xzf $sourceArchive -C $sourceRoot
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the selected pg_cron source archive.' }
  if ((Get-Content (Join-Path $cronRoot 'pg_cron.control') -Raw) -notmatch "(?m)^default_version\s*=\s*'1\.6'\s*$") { throw 'Selected source does not identify the expected pg_cron extension version.' }
  $makefile = Join-Path $cronRoot 'Makefile.win'
  $makefileHash = (Get-FileHash $makefile -Algorithm SHA256).Hash

  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
  if (-not (Test-Path $vswhere -PathType Leaf)) { throw 'Visual Studio vswhere.exe is missing from the Windows runner.' }
  $vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $vsRoot) { throw 'The Windows runner has no x64 MSVC toolchain installation.' }
  $vcvars = Join-Path $vsRoot 'VC/Auxiliary/Build/vcvars64.bat'
  if (-not (Test-Path $vcvars -PathType Leaf)) { throw 'The x64 MSVC vcvars64.bat script is missing.' }
  $environmentScript = Join-Path $work 'load-msvc-environment.cmd'
  @('@echo off', "call `"$vcvars`" >nul", 'if errorlevel 1 exit /b %errorlevel%', 'set') | Set-Content -Encoding ascii $environmentScript
  $environmentOutput = & $env:ComSpec /d /c $environmentScript
  if ($LASTEXITCODE -ne 0) { throw 'Could not load the x64 MSVC developer environment.' }
  foreach ($line in $environmentOutput) { if ($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') } }
  foreach ($command in @('cl.exe','link.exe','nmake.exe')) { if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "MSVC prerequisite is unavailable after vcvars64: $command" } }
  $previousPgRoot = $env:PGROOT
  $previousLink = $env:LINK
  $env:PGROOT = $pgRoot
  $exports = Join-Path $repo 'scripts/pg_cron/windows-exports.def'
  $linkOptions = "/DEBUG /DEF:`"$exports`""
  $env:LINK = if ($previousLink) { "$previousLink $linkOptions" } else { $linkOptions }
  Push-Location $cronRoot
  try {
    nmake.exe /F Makefile.win 'CFLAGS=/nologo /DWIN32_NO_STATUS /Dstrcasecmp=_stricmp /I"$(INCLUDEDIR_SERVER)\port\win32_msvc" /I"$(INCLUDEDIR_SERVER)\port\win32" /I"$(INCLUDEDIR_SERVER)" /I"$(INCLUDEDIR)" /Iinclude /Isrc /Z7 /O2' "LIBS=`"$pgRoot\lib\postgres.lib`" `"$pgRoot\lib\libpq.lib`" ws2_32.lib"
    if ($LASTEXITCODE -ne 0) { throw 'pg_cron upstream Makefile.win build failed.' }
  } finally {
    Pop-Location
    $env:PGROOT = $previousPgRoot
    $env:LINK = $previousLink
  }
  if ((Get-FileHash $makefile -Algorithm SHA256).Hash -cne $makefileHash) { throw 'pg_cron build modified the upstream Makefile.win.' }
  foreach ($required in @('pg_cron.dll','pg_cron.pdb','pg_cron.control','pg_cron--1.0.sql','pg_cron--1.5--1.6.sql','LICENSE')) {
    if (-not (Test-Path (Join-Path $cronRoot $required) -PathType Leaf)) { throw "pg_cron build did not produce or retain $required." }
  }
  Copy-Item (Join-Path $cronRoot 'pg_cron.dll') (Join-Path $stage 'lib/pg_cron.dll')
  Copy-Item (Join-Path $cronRoot 'pg_cron.control') (Join-Path $stage 'share/extension/pg_cron.control')
  Copy-Item (Join-Path $cronRoot 'pg_cron--*.sql') (Join-Path $stage 'share/extension')
  Copy-Item (Join-Path $cronRoot 'LICENSE') (Join-Path $stage 'LICENSES/pg_cron.txt')
  $inventory = [ordered]@{ schema_version = 1; components = @([ordered]@{
    component = 'pg_cron'; version = $cronVersion; payload_paths = @('lib/pg_cron.dll','share/extension'); license_file = 'pg_cron.txt'
    license_source = 'https://github.com/citusdata/pg_cron/blob/v1.6.8/LICENSE'; source_url = $sourceUrl; source_sha256 = $sourceSha
    redistribution_review = [ordered]@{ status = 'resolved'; basis = 'The unmodified pg_cron 1.6.8 source archive includes the PostgreSQL License for this project. It permits binary redistribution with its copyright notice, permission paragraph and disclaimer text retained.'; source_obligation = 'none' }
  }) }
  $inventory | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $stage 'LICENSES/pg_cron-inventory.json')
  $metadata = [ordered]@{
    project = 'pg_cron'; version = $cronVersion; sql_names = @('pg_cron'); requires = @()
    configuration_prerequisites = @(
      [ordered]@{ type = 'postgresql_setting'; name = 'shared_preload_libraries'; value = 'pg_cron' },
      [ordered]@{ type = 'postgresql_setting'; name = 'cron.use_background_workers'; value = 'on' })
    runtime_prerequisites = @(); build_id = $BuildId; source_revision = $SourceRevision
    postgresql_version = $pgVersion; platform = 'windows'; architecture = 'x86_64'
    source = [ordered]@{ url = $sourceUrl; sha256 = $sourceSha }
    core_archive = [ordered]@{ basename = $coreName; sha256 = $coreSha }
    build_configuration = "pg_cron-1.6.8;postgresql-core=$pgVersion;builder=windows-runner;compiler=MSVC;debug-symbols=CodeView"
  }
  $packageRoot = Join-Path $work 'archive'
  New-Item -ItemType Directory -Force $packageRoot | Out-Null
  $metadata | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $packageRoot 'metadata.json')
  Move-Item $stage (Join-Path $packageRoot 'pg_cron')
  $archiveName = "pg_cron-$cronVersion-postgresql-$pgVersion-windows-x86_64.tar.gz"
  $archivePath = Join-Path $OutputDirectory $archiveName
  if (Test-Path $archivePath) { Remove-Item $archivePath -Force }
  & $tar -czf $archivePath -C $packageRoot pg_cron metadata.json
  if ($LASTEXITCODE -ne 0) { throw 'Failed to create the pg_cron Windows archive.' }
  $archiveSha = (Get-FileHash $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
  "$archiveSha  $archiveName" | Set-Content -Encoding ascii "$archivePath.sha256"
  & $python (Join-Path $repo 'tools/create_windows_symbols.py') $coreArchive $archivePath --staged-pdbs $coreSymbolsDirectory $cronRoot --output-dir (Join-Path $OutputDirectory 'debug-symbols')
  if ($LASTEXITCODE -ne 0) { throw 'Could not bind the packaged PostgreSQL and pg_cron modules to matching PDBs.' }
  Write-Host "Built $archivePath"
} finally {
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
