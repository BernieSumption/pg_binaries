param(
  [Parameter(Mandatory = $true)][string]$CoreArchive,
  [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$CoreSha256,
  [Parameter(Mandatory = $true)][string]$CoreSymbolsDirectory,
  [Parameter(Mandatory = $true)][string]$SourceArchive,
  [Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+$')][string]$PostgreSQLVersion,
  [Parameter(Mandatory = $true)][ValidatePattern('^\d+(\.\d+)+$')][string]$PgvectorVersion,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
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
$expectedCoreName = "postgresql-$PostgreSQLVersion-windows-x86_64.tar.gz"
if ((Split-Path $coreArchive -Leaf) -cne $expectedCoreName) { throw "Core archive must be named $expectedCoreName" }
if (-not (Test-Path "$coreArchive.sha256" -PathType Leaf)) { throw 'Selected core archive has no SHA-256 sidecar.' }
$coreSidecar = (Get-Content "$coreArchive.sha256" -Raw).Trim() -split '\s+'
if ($coreSidecar.Count -lt 2 -or $coreSidecar[-1] -cne (Split-Path $coreArchive -Leaf)) { throw 'Selected core archive SHA-256 sidecar is invalid.' }
if ($coreSidecar[0] -notmatch '^[0-9a-fA-F]{64}$' -or (Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant() -cne $coreSidecar[0].ToLowerInvariant()) { throw 'Selected core archive SHA-256 sidecar mismatch.' }
$coreSha = (Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant()
$sourceSha = (Get-FileHash $sourceArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($coreSha -cne $CoreSha256.ToLowerInvariant()) { throw 'Core archive hash differs from the separately selected SHA-256.' }

$work = Join-Path $env:TEMP ("pgvector-windows-" + [guid]::NewGuid().ToString('N'))
$coreRoot = Join-Path $work 'core'
$sourceRoot = Join-Path $work 'source'
$pgRoot = Join-Path $coreRoot 'postgresql'
$vectorRoot = Join-Path $sourceRoot "pgvector-$PgvectorVersion"
$stage = Join-Path $work 'stage/pgvector'
New-Item -ItemType Directory -Force $coreRoot,$sourceRoot,(Join-Path $stage 'lib'),(Join-Path $stage 'share/extension') | Out-Null
try {
  & $tar -xzf $coreArchive -C $coreRoot
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the selected PostgreSQL core archive.' }
  $manifestPath = Join-Path $pgRoot 'manifest.json'
  if (-not (Test-Path $manifestPath -PathType Leaf)) { throw 'Core archive has no postgresql/manifest.json.' }
  $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
  if ($manifest.component -cne 'postgresql' -or $manifest.version -cne $PostgreSQLVersion -or $manifest.platform -cne 'windows' -or $manifest.architecture -cne 'x86_64') {
    throw 'Core archive manifest does not match the selected PostgreSQL Windows target.'
  }
  $pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
  if (-not (Test-Path $pgConfig -PathType Leaf) -or (& $pgConfig --version) -cne "PostgreSQL $PostgreSQLVersion") { throw 'Core archive pg_config identity is invalid.' }
  if (-not (Test-Path (Join-Path $pgRoot 'include/server/postgres.h') -PathType Leaf)) { throw 'Core archive lacks PostgreSQL server development headers.' }
  if (-not (Test-Path (Join-Path $pgRoot 'lib/postgres.lib') -PathType Leaf)) { throw 'Core archive lacks lib/postgres.lib required by pgvector Makefile.win.' }

  $sourceIdentity = (& $python (Join-Path $repo 'tools/source_archive.py') pgvector $PgvectorVersion tar.gz --field url | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve the selected pgvector source identity.' }
  $expectedSourceSha = (& $python (Join-Path $repo 'tools/source_archive.py') pgvector $PgvectorVersion tar.gz --field sha256 | Out-String).Trim()
  if ($LASTEXITCODE -ne 0 -or $sourceSha -cne $expectedSourceSha) { throw 'Source archive does not match the selected pgvector release identity.' }
  $members = @(& $tar -tzf $sourceArchive)
  if ($LASTEXITCODE -ne 0 -or -not ($members | Where-Object { $_ -match "^pgvector-$([regex]::Escape($PgvectorVersion))/Makefile.win$" })) { throw 'Source archive does not contain the expected pgvector release root.' }
  & $tar -xzf $sourceArchive -C $sourceRoot
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the selected pgvector source archive.' }
  if (-not (Test-Path (Join-Path $vectorRoot 'Makefile.win') -PathType Leaf)) { throw 'Selected pgvector source has no Makefile.win.' }

  $makefile = Join-Path $vectorRoot 'Makefile.win'
  $makefileHash = (Get-FileHash $makefile -Algorithm SHA256).Hash
  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
  if (-not (Test-Path $vswhere -PathType Leaf)) { throw 'Visual Studio vswhere.exe is missing from the Windows runner.' }
  $vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $vsRoot) { throw 'The Windows runner has no x64 MSVC toolchain installation.' }
  $vcvars = Join-Path $vsRoot 'VC/Auxiliary/Build/vcvars64.bat'
  if (-not (Test-Path $vcvars -PathType Leaf)) { throw 'The x64 MSVC vcvars64.bat script is missing.' }
  $environmentScript = Join-Path $work 'load-msvc-environment.cmd'
  @('@echo off', "call `"$vcvars`" >nul", 'if errorlevel 1 exit /b %errorlevel%', 'set') |
    Set-Content -Encoding ascii $environmentScript
  $environmentOutput = & $env:ComSpec /d /c $environmentScript
  if ($LASTEXITCODE -ne 0) { throw 'Could not load the x64 MSVC developer environment.' }
  foreach ($line in $environmentOutput) {
    if ($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') }
  }
  foreach ($command in @('cl.exe','link.exe','nmake.exe')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "MSVC prerequisite is unavailable after vcvars64: $command" }
  }
  $previousPgRoot = $env:PGROOT
  $previousLink = $env:LINK
  $env:PGROOT = $pgRoot
  $env:LINK = if ($previousLink) { "$previousLink /DEBUG" } else { '/DEBUG' }
  Push-Location $vectorRoot
  try {
    nmake.exe /F Makefile.win 'PG_CFLAGS=/Z7 /O2 /fp:fast'
    if ($LASTEXITCODE -ne 0) { throw 'pgvector upstream Makefile.win build failed.' }
  } finally {
    Pop-Location
    $env:PGROOT = $previousPgRoot
    $env:LINK = $previousLink
  }
  if ((Get-FileHash $makefile -Algorithm SHA256).Hash -cne $makefileHash) { throw 'pgvector build modified the upstream Makefile.win.' }
  foreach ($required in @('vector.dll','vector.pdb','vector.control')) {
    if (-not (Test-Path (Join-Path $vectorRoot $required) -PathType Leaf)) { throw "pgvector build did not produce $required." }
  }
  Copy-Item (Join-Path $vectorRoot 'vector.dll') (Join-Path $stage 'lib/vector.dll')
  Copy-Item (Join-Path $vectorRoot 'vector.control') (Join-Path $stage 'share/extension/vector.control')
  Copy-Item (Join-Path $vectorRoot 'sql/vector--*.sql') (Join-Path $stage 'share/extension')
  & $python (Join-Path $repo 'tools/license_pointer.py') write $stage pgvector
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the pgvector licence pointer.' }
  $metadata = [ordered]@{
    project = 'pgvector'; version = $PgvectorVersion; sql_names = @('vector')
    requires = @(); configuration_prerequisites = @(); runtime_prerequisites = @()
    postgresql_version = $PostgreSQLVersion
    build_id = $BuildId; source_revision = $SourceRevision
    source_archive = [ordered]@{ url = $sourceIdentity; sha256 = $sourceSha }
    core_archive = [ordered]@{ basename = (Split-Path $coreArchive -Leaf); sha256 = $coreSha }
    build_configuration = "pgvector-$PgvectorVersion;postgresql-core=$PostgreSQLVersion;builder=windows-runner;compiler=MSVC;debug-symbols=CodeView"
    platform = 'windows'; architecture = 'x86_64'
  }
  $packageRoot = Join-Path $work 'archive'
  New-Item -ItemType Directory -Force $packageRoot | Out-Null
  $metadata | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $packageRoot 'metadata.json')
  Move-Item $stage (Join-Path $packageRoot 'pgvector')
  $archiveName = "pgvector-$PgvectorVersion-postgresql-$PostgreSQLVersion-windows-x86_64.tar.gz"
  $archivePath = Join-Path $OutputDirectory $archiveName
  if (Test-Path $archivePath) { Remove-Item $archivePath -Force }
  & $tar -czf $archivePath -C $packageRoot pgvector metadata.json
  if ($LASTEXITCODE -ne 0) { throw 'Failed to create the pgvector Windows archive.' }
  & $python (Join-Path $repo 'tools/license_pointer.py') verify $archivePath pgvector
  if ($LASTEXITCODE -ne 0) { throw 'pgvector archive licence pointer verification failed.' }
  $archiveSha = (Get-FileHash $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
  "$archiveSha  $archiveName" | Set-Content -Encoding ascii "$archivePath.sha256"
  & $python (Join-Path $repo 'tools/create_windows_symbols.py') $coreArchive $archivePath --staged-pdbs $coreSymbolsDirectory $vectorRoot --output-dir (Join-Path $OutputDirectory 'debug-symbols')
  if ($LASTEXITCODE -ne 0) { throw 'Could not bind the packaged PostgreSQL and pgvector modules to matching PDBs.' }
  Write-Host "Built $archivePath"
} finally {
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
