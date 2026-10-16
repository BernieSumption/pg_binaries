$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$pgVersion = '18.6'
$vectorVersion = '0.8.7'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
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
Invoke-WebRequest "https://ftp.postgresql.org/pub/source/v$pgVersion/postgresql-$pgVersion.tar.gz" -OutFile $pgSourceArchive
Invoke-WebRequest "https://github.com/pgvector/pgvector/archive/refs/tags/v$vectorVersion.tar.gz" -OutFile $vectorSourceArchive
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
  '-Dreadline=disabled',
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
  included_extensions = $builtins
  source_sha256 = (Get-FileHash $pgSourceArchive -Algorithm SHA256).Hash.ToLowerInvariant()
  runtime_dependencies = @('ICU', 'LZ4', 'Zstandard', 'zlib', 'OpenSSL')
  bundled_runtime_dlls = $bundledRuntimeDlls
  os_prerequisites = @('Microsoft Visual C++ 2015-2022 Redistributable (x64)')
}
$pgManifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $pgInstall 'manifest.json')

$env:PGROOT = $pgInstall
$vectorMakefile = Join-Path $vectorSource 'Makefile.win'
$makefileText = Get-Content $vectorMakefile -Raw
$compileRule = 'CFLAGS = $(CFLAGS) $(PG_CFLAGS)'
$linkRule = '$(CC) $(CFLAGS) $(OBJS) $(LIBS) /link /DLL /OUT:$(SHLIB)'
if (-not $makefileText.Contains($compileRule) -or -not $makefileText.Contains($linkRule)) {
  throw 'pgvector Makefile.win debug build rules have changed'
}
$makefileText = $makefileText.Replace($compileRule, "$compileRule /Z7")
$makefileText = $makefileText.Replace($linkRule, $linkRule.Replace('/link /DLL', '/link /DEBUG /DLL'))
Set-Content -Path $vectorMakefile -Value $makefileText -Encoding ascii -NoNewline
Push-Location $vectorSource
try {
  nmake /F Makefile.win
} finally {
  Pop-Location
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
}
$vectorMetadata | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $work 'metadata.json')
New-Item -ItemType Directory -Force $vectorArchiveRoot | Out-Null
Move-Item $vectorPackage (Join-Path $vectorArchiveRoot 'pgvector')
Move-Item (Join-Path $work 'metadata.json') (Join-Path $vectorArchiveRoot 'metadata.json')

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
