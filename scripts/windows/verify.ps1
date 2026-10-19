param([switch]$CoreOnly)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = (Get-Command python -ErrorAction Stop).Source
$dist = Join-Path $repo 'dist/windows'
$pgVersion = $env:PG_VERSION
if (-not $pgVersion -or $pgVersion -notmatch '^\d+\.\d+$') { throw 'PG_VERSION must be set to the selected PostgreSQL minor version' }
$vectorVersion = '0.8.7'
$pgArchive = Join-Path $dist "postgresql-$pgVersion-windows-x86_64.tar.gz"
$vectorArchive = Join-Path $dist "pgvector-$vectorVersion-postgresql-$pgVersion-windows-x86_64.tar.gz"
$work = Join-Path $env:RUNNER_TEMP 'pg-binaries-windows-verify'
$pgExtract = Join-Path $work 'postgresql archive'
$vectorExtract = Join-Path $work 'pgvector archive'
$moved = Join-Path $work "relocated install/PostgreSQL $pgVersion"
$data = Join-Path $work 'database cluster'

function Assert-ArchiveHash([string]$archive) {
  $line = (Get-Content "$archive.sha256" -Raw).Trim()
  $parts = $line -split '\s+', 2
  if ($parts.Count -ne 2 -or $parts[1] -ne (Split-Path $archive -Leaf)) {
    throw "Invalid checksum companion for $archive"
  }
  $actual = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($parts[0] -ne $actual) { throw "Checksum mismatch for $archive" }
}

Assert-ArchiveHash $pgArchive
if (-not $CoreOnly) { Assert-ArchiveHash $vectorArchive }
New-Item -ItemType Directory -Force $pgExtract, (Split-Path $moved -Parent) | Out-Null
if (-not $CoreOnly) { New-Item -ItemType Directory -Force $vectorExtract | Out-Null }
tar.exe -xzf $pgArchive -C $pgExtract
if ($LASTEXITCODE -ne 0) { throw 'Failed to extract PostgreSQL archive' }
if (-not $CoreOnly) {
  tar.exe -xzf $vectorArchive -C $vectorExtract
  if ($LASTEXITCODE -ne 0) { throw 'Failed to extract pgvector archive' }
}

$pgRoot = Join-Path $pgExtract 'postgresql'
$vectorRoot = Join-Path $vectorExtract 'pgvector'
$metadataPath = Join-Path $vectorExtract 'metadata.json'
if (-not (Test-Path $pgRoot -PathType Container) -or
    @(Get-ChildItem $pgExtract -Force | Where-Object Name -ne 'postgresql').Count -ne 0) {
  throw 'PostgreSQL archive top-level layout is invalid'
}
if (-not $CoreOnly -and (-not (Test-Path $vectorRoot -PathType Container) -or
    -not (Test-Path $metadataPath -PathType Leaf) -or
    @(Get-ChildItem $vectorExtract -Force | Where-Object { $_.Name -notin @('pgvector', 'metadata.json') }).Count -ne 0)) {
  throw 'pgvector archive top-level layout is invalid'
}
$pgManifest = Get-Content (Join-Path $pgRoot 'manifest.json') -Raw | ConvertFrom-Json
if ($pgManifest.schema_version -ne 1 -or $pgManifest.component -ne 'postgresql' -or
    $pgManifest.version -ne $pgVersion -or $pgManifest.postgresql_version -ne $pgVersion -or
    $pgManifest.platform -ne 'windows' -or $pgManifest.architecture -ne 'x86_64') {
  throw 'PostgreSQL manifest does not match this verification target'
}
$controls = @(Get-ChildItem (Join-Path $pgRoot 'share/extension/*.control') -File | ForEach-Object BaseName | Sort-Object)
if ($controls.Count -eq 0 -or @($pgManifest.included_extensions).Count -ne $controls.Count -or
    (Compare-Object $controls @($pgManifest.included_extensions))) {
  throw 'Built-in extension inventory does not match the extracted archive'
}
if ($CoreOnly) {
  if ($pgVersion -eq '16.15') {
    & $python (Join-Path $repo 'tools/check_windows_git_source_identity.py') --postgresql-version $pgVersion --core-manifest (Join-Path $pgRoot 'manifest.json')
    if ($LASTEXITCODE -ne 0) { throw 'Packaged PostgreSQL Git source identity differs from the selected upstream release tag' }
  } else {
    & $python (Join-Path $repo 'tools/check_source_identity.py') --platform windows --postgresql-version $pgVersion --core-manifest (Join-Path $pgRoot 'manifest.json')
    if ($LASTEXITCODE -ne 0) { throw 'Packaged PostgreSQL source identity differs from the selected archive' }
  }
} else {
  $vectorMetadata = Get-Content $metadataPath -Raw | ConvertFrom-Json
  if ($pgVersion -eq '16.15') {
    & $python (Join-Path $repo 'tools/check_windows_git_source_identity.py') --postgresql-version $pgVersion --core-manifest (Join-Path $pgRoot 'manifest.json') --vector-metadata $metadataPath
    if ($LASTEXITCODE -ne 0) { throw 'Packaged source identity differs from the selected upstream Git tag or pgvector archive' }
  } else {
    & $python (Join-Path $repo 'tools/check_source_identity.py') --platform windows --postgresql-version $pgVersion --core-manifest (Join-Path $pgRoot 'manifest.json') --vector-metadata $metadataPath
    if ($LASTEXITCODE -ne 0) { throw 'Packaged source identity differs from the selected archives' }
  }
}
if ($pgVersion -eq '16.15') {
  & $python (Join-Path $repo 'tools/stage_windows_postgres_import_library.py') --library-directory (Join-Path $pgRoot 'lib') --verify-manifest (Join-Path $pgRoot 'manifest.json')
  if ($LASTEXITCODE -ne 0) { throw 'The PostgreSQL 16 Windows import-library alias is missing or mismatched' }
} elseif ($null -ne $pgManifest.windows_import_library) {
  throw 'Unexpected Windows import-library alias metadata for this PostgreSQL version'
}
if (-not $CoreOnly) {
foreach ($field in @('project', 'version', 'sql_names', 'requires', 'configuration_prerequisites', 'runtime_prerequisites')) {
  if ($null -eq $vectorMetadata.$field) { throw "pgvector metadata is missing $field" }
}
if ($vectorMetadata.project -ne 'pgvector' -or $vectorMetadata.version -ne $vectorVersion -or
    @($vectorMetadata.sql_names) -notcontains 'vector') { throw 'pgvector metadata does not match this verification target' }
foreach ($field in @('sql_names', 'requires', 'configuration_prerequisites', 'runtime_prerequisites')) {
  if ($vectorMetadata.$field -isnot [System.Array]) { throw "pgvector metadata field $field must be an array" }
}
if (@($vectorMetadata.sql_names).Count -ne 1 -or @($vectorMetadata.requires).Count -ne 0 -or
    @($vectorMetadata.configuration_prerequisites).Count -ne 0 -or
    @($vectorMetadata.runtime_prerequisites).Count -ne 0) { throw 'pgvector metadata prerequisites or SQL names are unexpected' }
}
if ($pgManifest.build_id -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$' -or
    $pgManifest.source_revision -notmatch '^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$' -or
    -not $pgManifest.build_configuration) { throw 'PostgreSQL build provenance is missing or invalid' }
if (@($pgManifest.os_prerequisites).Count -ne 0 -or
    @($pgManifest.bundled_msvc_runtime_dlls).Count -eq 0 -or
    @($pgManifest.bundled_msvc_runtime_dlls) -notcontains 'vcruntime140.dll') {
  throw 'The PostgreSQL archive does not declare an application-local Visual C++ runtime'
}
foreach ($name in @($pgManifest.bundled_msvc_runtime_dlls)) {
  if ($name -notmatch '^(?i:(?:vcruntime|msvcp|concrt|vcomp|mfc|atl)\d[^\\/]*\.dll)$' -or
      -not (Test-Path (Join-Path $pgRoot "bin/$name") -PathType Leaf)) {
    throw "The declared Visual C++ runtime DLL is missing or invalid: $name"
  }
}
$msvcNotice = 'LICENSE-Microsoft-Visual-C++-Runtime.md'
if (-not (Test-Path (Join-Path $pgRoot "bin/$msvcNotice") -PathType Leaf) -or
    -not (Test-Path (Join-Path $pgRoot "LICENSES/$msvcNotice") -PathType Leaf)) {
  throw 'The Visual C++ runtime notice is missing'
}
if (-not $CoreOnly) { foreach ($field in @('build_id', 'source_revision', 'build_configuration', 'platform', 'architecture')) {
  if ($vectorMetadata.$field -cne $pgManifest.$field) { throw "pgvector build provenance differs from PostgreSQL: $field" }
} }
if (-not (Test-Path (Join-Path $pgRoot 'manifest.json')) -or
    -not (Test-Path (Join-Path $pgRoot 'LICENSES/PostgreSQL.txt')) -or
    (-not $CoreOnly -and -not (Test-Path (Join-Path $vectorRoot 'LICENSES/pgvector.txt'))) -or
    -not (Test-Path (Join-Path $pgRoot 'LICENSES/dependencies/icu.txt'))) { throw 'A required license text is missing' }

$licenseInventoryPath = Join-Path $pgRoot 'LICENSES/inventory.json'
$vectorLicenseInventoryPath = Join-Path $vectorRoot 'LICENSES/pgvector-inventory.json'
if (-not (Test-Path $licenseInventoryPath -PathType Leaf) -or
    (-not $CoreOnly -and (-not (Test-Path $vectorLicenseInventoryPath -PathType Leaf) -or
    (Test-Path (Join-Path $vectorRoot 'LICENSES/inventory.json'))))) {
  throw 'Required licence inventories are missing or use colliding names'
}
$licenseInventories = @([ordered]@{ root = $pgRoot; path = $licenseInventoryPath; expected = @('postgresql', 'bundled-runtime-dependencies', 'Microsoft Visual C++ runtime') })
if (-not $CoreOnly) { $licenseInventories += [ordered]@{ root = $vectorRoot; path = $vectorLicenseInventoryPath; expected = @('pgvector') } }
foreach ($inventorySpec in $licenseInventories) {
  $inventory = Get-Content $inventorySpec.path -Raw | ConvertFrom-Json
  if ($inventory.schema_version -ne 1 -or @($inventory.components).Count -ne $inventorySpec.expected.Count) {
    throw "Licence inventory schema or component count is invalid: $($inventorySpec.path)"
  }
  $actualComponents = @($inventory.components | ForEach-Object component | Sort-Object)
  $expectedComponents = @($inventorySpec.expected | Sort-Object)
  if (Compare-Object $actualComponents $expectedComponents) { throw "Licence inventory components differ from the packaged payload: $($inventorySpec.path)" }
  foreach ($component in $inventory.components) {
    if (-not $component.version -or @($component.payload_paths).Count -eq 0 -or
        -not $component.license_file -or -not $component.redistribution_review.basis -or
        $component.redistribution_review.status -notin @('resolved', 'pending')) {
      throw "Licence component has incomplete identity or review: $($component.component)"
    }
    $licensePaths = @($component.license_file)
    if ($null -ne $component.additional_license_files) {
      $licensePaths += @($component.additional_license_files)
    }
    foreach ($licensePath in $licensePaths) {
      $relativeLicense = $licensePath -replace '^LICENSES/', ''
      $fullLicense = Join-Path $inventorySpec.root "LICENSES/$relativeLicense"
      if (-not (Test-Path $fullLicense -PathType Leaf) -or (Get-Item $fullLicense).Length -eq 0) {
        throw "Declared licence evidence is missing or empty: $licensePath"
      }
    }
    foreach ($payloadPath in $component.payload_paths) {
      if (-not (Test-Path (Join-Path $inventorySpec.root $payloadPath))) {
        throw "Licence component payload path is missing: $payloadPath"
      }
    }
  }
}
$coreLicenseInventory = Get-Content $licenseInventoryPath -Raw | ConvertFrom-Json
$runtimeReview = @($coreLicenseInventory.components | Where-Object component -eq 'bundled-runtime-dependencies')[0].redistribution_review
if ($runtimeReview.status -ne 'pending') { throw 'Windows dependency redistribution review must remain pending until package mapping and terms are established' }
$vcpkgMapPath = Join-Path $pgRoot 'LICENSES/vcpkg-dll-map.json'
if (-not (Test-Path $vcpkgMapPath -PathType Leaf)) { throw 'Bundled vcpkg DLL ownership map is missing' }
$vcpkgMap = Get-Content $vcpkgMapPath -Raw | ConvertFrom-Json
if ($vcpkgMap.schema_version -ne 1 -or @($vcpkgMap.components).Count -eq 0) {
  throw 'Bundled vcpkg DLL ownership map is empty or invalid'
}
$mappedDlls = @($vcpkgMap.components | ForEach-Object dll | Sort-Object)
$declaredDlls = @($pgManifest.bundled_runtime_dlls | Sort-Object)
if (Compare-Object $mappedDlls $declaredDlls) { throw 'vcpkg ownership map does not cover exactly the bundled runtime DLLs' }
foreach ($entry in $vcpkgMap.components) {
  if ($entry.dll -notmatch '^[A-Za-z0-9._-]+\.dll$' -or
      $entry.port -notmatch '^[A-Za-z0-9._-]+$' -or
      -not $entry.version -or $null -eq $entry.port_version -or
      $entry.triplet -ne 'x64-windows' -or
      $entry.copyright_file -ne "share/$($entry.port)/copyright") {
    throw "Invalid vcpkg ownership map entry: $($entry.dll)"
  }
  $dllPath = Join-Path $pgRoot "bin/$($entry.dll)"
  $noticePath = Join-Path $pgRoot "LICENSES/dependencies/$($entry.port).txt"
  if ((Get-FileHash $dllPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.dll_sha256 -or
      (Get-FileHash $noticePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.copyright_sha256) {
    throw "vcpkg DLL or notice bytes differ from the ownership map: $($entry.dll)"
  }
}
$msvcComponent = @($coreLicenseInventory.components | Where-Object component -eq 'Microsoft Visual C++ runtime')[0]
if ($msvcComponent.redistribution_review.status -ne 'resolved' -or
    $msvcComponent.version -notmatch '(?i)vcruntime140\.dll=\S+') {
  throw 'Visual C++ runtime inventory lacks the reviewed runtime and version evidence'
}
if (-not $CoreOnly) {
  $vectorInventory = Get-Content $vectorLicenseInventoryPath -Raw | ConvertFrom-Json
  if (@($vectorInventory.components)[0].redistribution_review.status -ne 'resolved') { throw 'pgvector redistribution review is unresolved' }
}

$coreEntries = @{}
Get-ChildItem $pgRoot -Force -Recurse | ForEach-Object {
  $relative = $_.FullName.Substring($pgRoot.Length).TrimStart('\', '/')
  if ($relative) { $coreEntries[$relative.ToLowerInvariant()] = $_.PSIsContainer }
}
if (-not $CoreOnly) { Get-ChildItem $vectorRoot -Force -Recurse | ForEach-Object {
  $relative = $_.FullName.Substring($vectorRoot.Length).TrimStart('\', '/')
  $key = $relative.ToLowerInvariant()
  if ($relative -and $coreEntries.ContainsKey($key) -and
      (-not $_.PSIsContainer -or -not $coreEntries[$key])) { throw "Payload path collision: $relative" }
} }
if (-not $CoreOnly) { Get-ChildItem $vectorRoot -File -Recurse | ForEach-Object {
  $relative = $_.FullName.Substring($vectorRoot.Length).TrimStart('\', '/')
  $destination = Join-Path $pgRoot $relative
  New-Item -ItemType Directory -Force (Split-Path $destination -Parent) | Out-Null
  Copy-Item $_.FullName $destination
} }
if (-not $CoreOnly -and ((Test-Path (Join-Path $pgRoot 'metadata.json')) -or -not (Test-Path $metadataPath))) {
  throw 'Extension metadata must remain outside the PostgreSQL prefix'
}

$env:PGHOST = '127.0.0.1'
$env:PGPORT = '55432'
$env:PGUSER = 'postgres'
$env:PGDATABASE = 'postgres'
$env:PGSSLMODE = 'disable'
$initialData = Join-Path $work 'initial database cluster'
$initialBin = Join-Path $pgRoot 'bin'
$env:PATH = "$initialBin;$env:SystemRoot\System32;$env:SystemRoot"
& (Join-Path $initialBin 'initdb.exe') -D $initialData -U postgres -A trust --encoding=UTF8 --no-instructions
$initialStarted = $false
try {
  & (Join-Path $initialBin 'pg_ctl.exe') -D $initialData -l (Join-Path $work 'postgres-before-move.log') -o "-h 127.0.0.1 -p $env:PGPORT" -w start
  $initialStarted = $true
  $initialPsql = Join-Path $initialBin 'psql.exe'
  $initialVersion = (& $initialPsql -At -c 'SHOW server_version').Trim()
  $initialQuery = (& $initialPsql -At -c 'SELECT 1').Trim()
  if ($initialVersion -ne $pgVersion -or $initialQuery -ne '1') { throw 'Pre-move PostgreSQL smoke check failed' }
  if (-not $CoreOnly) {
    & $initialPsql -X -v ON_ERROR_STOP=1 -c "CREATE EXTENSION vector; CREATE TABLE pilot_vectors (id integer PRIMARY KEY, embedding vector(3)); INSERT INTO pilot_vectors VALUES (1, '[1,0,0]'), (2, '[0,1,0]'), (3, '[0,0,1]'); CREATE INDEX pilot_vectors_hnsw ON pilot_vectors USING hnsw (embedding vector_l2_ops);"
    $nearest = (& $initialPsql -At -c "SELECT id FROM pilot_vectors ORDER BY embedding <-> '[1,0,0]'::vector LIMIT 1").Trim()
    if ($nearest -ne '1') { throw "Pre-move pgvector query returned $nearest, expected 1" }
  }
} finally {
  if ($initialStarted) { & (Join-Path $initialBin 'pg_ctl.exe') -D $initialData -m immediate -w stop }
}

Move-Item $pgRoot $moved

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
if (-not (Test-Path $vswhere -PathType Leaf)) { throw 'Visual Studio vswhere is unavailable for PE inspection' }
$vsRoot = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if ($LASTEXITCODE -ne 0 -or -not $vsRoot) { throw 'Visual Studio C++ tools are unavailable for PE inspection' }
$toolset = Get-ChildItem (Join-Path $vsRoot 'VC/Tools/MSVC') -Directory |
  Sort-Object Name -Descending | Select-Object -First 1
if (-not $toolset) { throw 'Visual Studio C++ toolset is unavailable for PE inspection' }
$dumpbin = Join-Path $toolset.FullName 'bin/Hostx64/x64/dumpbin.exe'
if (-not (Test-Path $dumpbin -PathType Leaf)) { throw 'Visual Studio dumpbin is unavailable for PE inspection' }
$staticReport = if ($env:PE_STATIC_ANALYSIS_REPORT) { $env:PE_STATIC_ANALYSIS_REPORT } else { Join-Path $work 'static-analysis.json' }
New-Item -ItemType Directory -Force (Split-Path $staticReport -Parent) | Out-Null
$peArgs = @($moved, '--dumpbin', $dumpbin, '--archive', $pgArchive, '--report', $staticReport)
if (-not $CoreOnly) { $peArgs += @('--archive', $vectorArchive) }
& $python (Join-Path $repo 'tools/check_pe_dependencies.py') @peArgs
if ($LASTEXITCODE -ne 0) { throw 'Packaged PE static analysis failed' }

$bin = Join-Path $moved 'bin'
$env:PATH = "$bin;$env:SystemRoot\System32;$env:SystemRoot"
$initdb = Join-Path $bin 'initdb.exe'
$pgCtl = Join-Path $bin 'pg_ctl.exe'
$psql = Join-Path $bin 'psql.exe'
$pgDump = Join-Path $bin 'pg_dump.exe'
$pgRestore = Join-Path $bin 'pg_restore.exe'

& $initdb -D $data -U postgres -A trust --encoding=UTF8 --no-instructions
. (Join-Path $PSScriptRoot 'tls-fixtures.ps1')
New-PilotTlsFixtures (Join-Path $data 'tls')
@'
shared_preload_libraries = 'pg_stat_statements'
wal_level = logical
ssl = on
ssl_cert_file = 'tls/server.crt'
ssl_key_file = 'tls/server.key'
ssl_ca_file = 'tls/ca.crt'
'@ | Add-Content -Encoding ascii (Join-Path $data 'postgresql.conf')
@'
hostssl all all 127.0.0.1/32 cert
hostnossl all all 127.0.0.1/32 trust
'@ | Set-Content -Encoding ascii (Join-Path $data 'pg_hba.conf')
$started = $false
try {
  & $pgCtl -D $data -l (Join-Path $work 'postgres.log') -o "-h 127.0.0.1 -p $env:PGPORT" -w start
  $started = $true
  $reported = (& $psql -At -c 'SHOW server_version').Trim()
  if ($reported -ne $pgVersion) { throw "Server reports $reported, expected $pgVersion" }
  $basicQuery = (& $psql -At -c 'SELECT 1').Trim()
  if ($basicQuery -ne '1') { throw "PostgreSQL query returned $basicQuery, expected 1" }

  & $psql -X -v ON_ERROR_STOP=1 -f (Join-Path $repo 'tests/schema.sql')
  & $psql -X -v ON_ERROR_STOP=1 -f (Join-Path $repo 'tests/builtins/basic.sql')
  & $psql -X -v ON_ERROR_STOP=1 -v "loopback_conninfo=host=127.0.0.1 port=$env:PGPORT dbname=postgres sslmode=disable" -v loopback_host=127.0.0.1 -v "loopback_port=$env:PGPORT" -f (Join-Path $repo 'tests/builtins/loopback.sql')
  $fixturePath = (Join-Path $repo 'tests/builtins/file_fdw.csv').Replace('\', '/')
  & $psql -X -v ON_ERROR_STOP=1 -v "fixture_path=$fixturePath" -f (Join-Path $repo 'tests/builtins/fixture.sql')
  $builtInSuites = @('preloaded', 'wal')
  if ($pgVersion.StartsWith('18.')) { $builtInSuites += 'logical' }
  if ($pgVersion.StartsWith('15.') -or $pgVersion.StartsWith('16.')) { $builtInSuites += 'legacy' }
  foreach ($suite in $builtInSuites) {
    & $psql -X -v ON_ERROR_STOP=1 -f (Join-Path $repo "tests/builtins/$suite.sql")
  }
  $notifications = (& $psql -X -v ON_ERROR_STOP=1 -f (Join-Path $repo 'tests/builtins/tcn.sql')) -join "`n"
  Write-Host $notifications
  if (-not $notifications.Contains('Asynchronous notification "tcn" with payload ""builtin_tcn",I,"id"=''91''"')) {
    throw 'tcn did not deliver the expected insert notification'
  }
  $tlsEnvironment = @{}
  foreach ($name in @('PGSSLMODE', 'PGSSLROOTCERT', 'PGSSLCERT', 'PGSSLKEY')) {
    $tlsEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
  }
  try {
    $env:PGSSLMODE = 'verify-ca'
    $env:PGSSLROOTCERT = Join-Path $data 'tls/ca.crt'
    $env:PGSSLCERT = Join-Path $data 'tls/client.crt'
    $env:PGSSLKEY = Join-Path $data 'tls/client.key'
    & $psql -X -v ON_ERROR_STOP=1 -f (Join-Path $repo 'tests/builtins/ssl.sql')
  } finally {
    foreach ($name in $tlsEnvironment.Keys) {
      [Environment]::SetEnvironmentVariable($name, $tlsEnvironment[$name], 'Process')
    }
  }
  $collationSql = @'
CREATE COLLATION pilot_icu (provider = icu, locale = 'en-US-u-ks-level2', deterministic = false);
SELECT 'a' COLLATE pilot_icu < 'B' COLLATE pilot_icu;
DO $$
DECLARE host_locale text;
BEGIN
  SELECT datcollate INTO host_locale FROM pg_database WHERE datname = current_database();
  EXECUTE format('CREATE COLLATION pilot_libc (provider = libc, locale = %L)', host_locale);
END $$;
SELECT 'a' COLLATE pilot_libc < 'b' COLLATE pilot_libc;
'@
  & $psql -X -v ON_ERROR_STOP=1 -c $collationSql
  $xmlResult = (& $psql -X -At -v ON_ERROR_STOP=1 -c "SELECT (xpath('/x/text()', '<x>ok</x>'::xml))[1]::text").Trim()
  if ($xmlResult -ne 'ok') { throw "XML schema operation returned $xmlResult, expected ok" }

  $compressionSql = @'
CREATE TABLE pilot_compression (id integer PRIMARY KEY, payload text COMPRESSION lz4);
INSERT INTO pilot_compression VALUES (1, repeat('compress me ', 5000));
SELECT pg_column_compression(payload) FROM pilot_compression;
SET wal_compression = zstd;
SHOW wal_compression;
'@
  & $psql -X -v ON_ERROR_STOP=1 -c $compressionSql
  $method = (& $psql -At -c 'SELECT pg_column_compression(payload) FROM pilot_compression').Trim()
  if ($method -ne 'lz4') { throw "TOAST compression returned $method, expected lz4" }
  $dumpMethods = @('gzip', 'lz4', 'zstd')
  if ($pgVersion.StartsWith('15.')) { $dumpMethods = @('6') }
  foreach ($method in $dumpMethods) {
    $dump = Join-Path $work "pilot-$method.dump"
    & $pgDump -Fc -Z $method -f $dump postgres
    & $pgRestore -l $dump | Out-Null
  }

  if (-not $CoreOnly) {
    & $psql -X -v ON_ERROR_STOP=1 -f (Join-Path $repo 'tests/extensions/pgvector.sql')
    $installed = (& $psql -At -c "SELECT extversion FROM pg_extension WHERE extname = 'vector'").Trim()
    if ($installed -ne $vectorVersion) { throw "pgvector reports $installed, expected $vectorVersion" }
  }
  & $psql -X -v ON_ERROR_STOP=1 -f (Join-Path $repo 'tests/builtins/coverage.sql')
  $restoreDump = Join-Path $work 'restorable.dump'
  $restoreCompression = 'zstd'
  if ($pgVersion.StartsWith('15.')) { $restoreCompression = '6' }
  & $pgDump -Fc -Z $restoreCompression -f $restoreDump postgres
  & $psql -X -v ON_ERROR_STOP=1 -c 'CREATE DATABASE restored'
  & $pgRestore --exit-on-error -d restored $restoreDump
  $restoredCount = (& $psql -X -At -d restored -c 'SELECT pilot.active_item_count(1)').Trim()
  if ($restoredCount -ne '1') { throw "Restored schema check failed: $restoredCount" }
  if (-not $CoreOnly) {
    $restoredNearest = (& $psql -X -At -d restored -c "SELECT id FROM pilot_vectors ORDER BY embedding <-> '[1,0,0]'::vector LIMIT 1").Trim()
    if ($restoredNearest -ne '1') { throw "Restored vector check failed: $restoredNearest" }
  }
  & $psql -X -v ON_ERROR_STOP=1 -c 'CREATE DATABASE surgery_check'
  & $psql -X -v ON_ERROR_STOP=1 -d surgery_check -f (Join-Path $repo 'tests/builtins/surgery.sql')
  if ($CoreOnly) { Write-Host "Verified PostgreSQL $reported on Windows $([Environment]::OSVersion.Version) after archive relocation" }
  else { Write-Host "Verified PostgreSQL $reported and pgvector $installed on Windows $([Environment]::OSVersion.Version) after archive relocation" }
} finally {
  if ($started) { & $pgCtl -D $data -m fast -w stop }
}
