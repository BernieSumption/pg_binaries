$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$pgVersion = $env:PG_VERSION
if (-not $pgVersion -or $pgVersion -notmatch '^\d+\.\d+$') { throw 'PG_VERSION must be set to a PostgreSQL minor version selected by tools/plan_work.py' }
$vectorVersion = '0.8.7'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$sourceRevision = $env:SOURCE_REVISION
if (-not $sourceRevision) { $sourceRevision = $env:GITHUB_SHA }
if (-not $sourceRevision) { $sourceRevision = (& git -C $repo rev-parse HEAD).Trim() }
if ($sourceRevision -notmatch '^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$') {
  throw "SOURCE_REVISION must be a full Git object ID: $sourceRevision"
}
$buildId = $env:BUILD_ID
if (-not $buildId) {
  if ($env:GITHUB_RUN_ID) {
    $runAttempt = if ($env:GITHUB_RUN_ATTEMPT) { $env:GITHUB_RUN_ATTEMPT } else { '1' }
    $buildId = "github-$($env:GITHUB_RUN_ID)-$runAttempt"
  } else {
    $buildId = "local-$([guid]::NewGuid().ToString('N'))"
  }
}
if ($buildId -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$') {
  throw 'BUILD_ID may contain only letters, digits, dot, underscore and hyphen'
}
$buildConfiguration = "postgresql-$pgVersion;pgvector-$vectorVersion;builder=windows-runner;meson=debugoptimized;postgresql=icu,lz4,zstd,zlib,openssl,libxml,libxslt,no-uuid,no-readline;compiler=MSVC;pgvector=debug-symbols;runtime=vcpkg-and-msvc-dlls"
$work = Join-Path $env:RUNNER_TEMP 'pg-binaries-windows-build'
$dist = Join-Path $repo 'dist/windows'
$vcpkgRoot = $env:VCPKG_INSTALLATION_ROOT
if (-not $vcpkgRoot) { throw 'VCPKG_INSTALLATION_ROOT is missing' }
$vcpkg = Join-Path $vcpkgRoot 'installed/x64-windows'
$pgSourceArchive = Join-Path $work "postgresql-$pgVersion.tar.gz"
$vectorSourceArchive = Join-Path $work "pgvector-$vectorVersion.tar.gz"
$pgSource = Join-Path $work "postgresql-$pgVersion"
$vectorSource = Join-Path $work "pgvector-$vectorVersion"
$pgBuild = Join-Path $work 'pg-build'
$pgInstall = Join-Path $work 'postgresql'
$vectorPackage = Join-Path $work 'pgvector'
$vectorArchiveRoot = Join-Path $work 'pgvector-archive'

New-Item -ItemType Directory -Force $work, $dist | Out-Null
$sourceTool = Join-Path $repo 'tools/source_archive.py'
$pgSourceUrl = (& python $sourceTool postgresql $pgVersion tar.gz --field url).Trim()
$pgSourceSha256 = (& python $sourceTool postgresql $pgVersion tar.gz --field sha256).Trim()
$vectorSourceUrl = (& python $sourceTool pgvector $vectorVersion tar.gz --field url).Trim()
$vectorSourceSha256 = (& python $sourceTool pgvector $vectorVersion tar.gz --field sha256).Trim()
Invoke-WebRequest $pgSourceUrl -OutFile $pgSourceArchive
Invoke-WebRequest $vectorSourceUrl -OutFile $vectorSourceArchive
if ((Get-FileHash $pgSourceArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pgSourceSha256) {
  throw 'PostgreSQL source archive SHA-256 differs from selected source identity'
}
if ((Get-FileHash $vectorSourceArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $vectorSourceSha256) {
  throw 'pgvector source archive SHA-256 differs from selected source identity'
}
tar -xzf $pgSourceArchive -C $work
tar -xzf $vectorSourceArchive -C $work

$env:PKG_CONFIG_PATH = (Join-Path $vcpkg 'lib/pkgconfig')
$env:CMAKE_PREFIX_PATH = $vcpkg
$env:PATH = "$(Join-Path $vcpkg 'bin');$env:PATH"

$mesonArgs = @(
  'setup', $pgBuild, $pgSource,
  "--prefix=$pgInstall", '--buildtype=debugoptimized',
  '-Dicu=enabled', '-Dlz4=enabled', '-Dzstd=enabled',
  '-Dzlib=enabled', '-Dssl=openssl', '-Dlibxml=enabled', '-Dlibxslt=enabled',
  '-Duuid=none', '-Dreadline=disabled',
  '-Dplperl=disabled', '-Dplpython=disabled', '-Dpltcl=disabled',
  "-Dextra_include_dirs=$(Join-Path $vcpkg 'include')",
  "-Dextra_lib_dirs=$(Join-Path $vcpkg 'lib')"
)
meson @mesonArgs
meson compile -C $pgBuild
meson install -C $pgBuild

# Place redistributable dependency DLLs with PostgreSQL binaries, where the
# Windows loader will find them without vcpkg or the builder's PATH.
$bundledRuntimeDlls = @(Get-ChildItem (Join-Path $vcpkg 'bin') -Filter '*.dll' -File | Select-Object -ExpandProperty Name)
Copy-Item (Join-Path $vcpkg 'bin/*.dll') (Join-Path $pgInstall 'bin')

$pgLicenses = Join-Path $pgInstall 'LICENSES'
New-Item -ItemType Directory -Force $pgLicenses | Out-Null
Copy-Item (Join-Path $pgSource 'COPYRIGHT') (Join-Path $pgLicenses 'PostgreSQL.txt')
$dependencyLicenses = Join-Path $pgLicenses 'dependencies'
New-Item -ItemType Directory -Force $dependencyLicenses | Out-Null
Get-ChildItem (Join-Path $vcpkg 'share') -Directory | ForEach-Object {
  $copyright = Join-Path $_.FullName 'copyright'
  if (Test-Path $copyright) {
    Copy-Item $copyright (Join-Path $dependencyLicenses "$($_.Name).txt")
  }
}
$builtins = @(& python (Join-Path $repo 'tools/discover_builtins.py') $pgInstall | ConvertFrom-Json)

$pgManifest = [ordered]@{
  schema_version = 1
  component = 'postgresql'
  version = $pgVersion
  postgresql_version = $pgVersion
  platform = 'windows'
  architecture = 'x86_64'
  build_id = $buildId
  source_revision = $sourceRevision
  source_archive = [ordered]@{ url = $pgSourceUrl; sha256 = $pgSourceSha256 }
  build_configuration = $buildConfiguration
  included_extensions = $builtins
  source_sha256 = $pgSourceSha256
  runtime_dependencies = @('ICU', 'LZ4', 'Zstandard', 'zlib', 'OpenSSL')
  bundled_runtime_dlls = $bundledRuntimeDlls
  os_prerequisites = @()
}

$env:PGROOT = $pgInstall
$vectorMakefile = Join-Path $vectorSource 'Makefile.win'
$vectorMakefileHash = (Get-FileHash $vectorMakefile -Algorithm SHA256).Hash
$previousLink = $env:LINK
$env:LINK = if ($previousLink) { "$previousLink /DEBUG" } else { '/DEBUG' }
Push-Location $vectorSource
try {
  nmake /F Makefile.win 'PG_CFLAGS=/Z7 /O2 /fp:fast'
  if ($LASTEXITCODE -ne 0) { throw 'pgvector upstream Makefile.win build failed' }
} finally {
  Pop-Location
  $env:LINK = $previousLink
}
if ((Get-FileHash $vectorMakefile -Algorithm SHA256).Hash -ne $vectorMakefileHash) {
  throw 'pgvector upstream Makefile.win changed during the build'
}
if (-not (Test-Path (Join-Path $vectorSource 'vector.pdb'))) {
  throw 'pgvector build produced no vector.pdb'
}
New-Item -ItemType Directory -Force (Join-Path $vectorPackage 'lib'), (Join-Path $vectorPackage 'share/extension'), (Join-Path $vectorPackage 'LICENSES') | Out-Null
Copy-Item (Join-Path $vectorSource 'vector.dll') (Join-Path $vectorPackage 'lib/vector.dll')
Copy-Item (Join-Path $vectorSource 'vector.control') (Join-Path $vectorPackage 'share/extension/vector.control')
Copy-Item (Join-Path $vectorSource 'sql/vector--*.sql') (Join-Path $vectorPackage 'share/extension')
Copy-Item (Join-Path $vectorSource 'LICENSE') (Join-Path $vectorPackage 'LICENSES/pgvector.txt')
$vectorMetadata = [ordered]@{
  project = 'pgvector'
  version = $vectorVersion
  sql_names = @('vector')
  requires = @()
  configuration_prerequisites = @()
  runtime_prerequisites = @()
  build_id = $buildId
  source_revision = $sourceRevision
  source_archive = [ordered]@{ url = $vectorSourceUrl; sha256 = $vectorSourceSha256 }
  build_configuration = $buildConfiguration
  platform = 'windows'
  architecture = 'x86_64'
}
$vectorMetadata | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $work 'metadata.json')
New-Item -ItemType Directory -Force $vectorArchiveRoot | Out-Null
Move-Item $vectorPackage (Join-Path $vectorArchiveRoot 'pgvector')
Move-Item (Join-Path $work 'metadata.json') (Join-Path $vectorArchiveRoot 'metadata.json')

$msvcRuntimeDlls = @(& (Join-Path $PSScriptRoot 'bundle-msvc-runtime.ps1') -PostgresRoot $pgInstall -ExtensionRoot (Join-Path $vectorArchiveRoot 'pgvector') -NoticeTemplate (Join-Path $PSScriptRoot 'MSVC-RUNTIME.md'))
$pgManifest['bundled_msvc_runtime_dlls'] = $msvcRuntimeDlls
$pgManifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $pgInstall 'manifest.json')

$pgArchive = Join-Path $dist "postgresql-$pgVersion-windows-x86_64.tar.gz"
$vectorArchive = Join-Path $dist "pgvector-$vectorVersion-postgresql-$pgVersion-windows-x86_64.tar.gz"
if (Test-Path $pgArchive) { Remove-Item $pgArchive -Force }
if (Test-Path $vectorArchive) { Remove-Item $vectorArchive -Force }
tar.exe -czf $pgArchive -C $work postgresql
if ($LASTEXITCODE -ne 0) { throw 'Failed to create PostgreSQL tar.gz archive' }
tar.exe -czf $vectorArchive -C $vectorArchiveRoot pgvector metadata.json
if ($LASTEXITCODE -ne 0) { throw 'Failed to create pgvector tar.gz archive' }
foreach ($archive in @($pgArchive, $vectorArchive)) {
  $hash = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $(Split-Path $archive -Leaf)" | Set-Content -Encoding ascii "$archive.sha256"
}
python (Join-Path $repo 'tools/create_windows_symbols.py') $pgArchive $vectorArchive --staged-pdbs $pgBuild $vectorSource --output-dir (Join-Path $dist 'debug-symbols')
if ($LASTEXITCODE -ne 0) { throw 'Failed to index matching Windows PDB files' }
Write-Host "Built $pgArchive and $vectorArchive"
