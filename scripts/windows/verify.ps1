$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$dist = Join-Path $repo 'dist/windows'
$pgVersion = '18.6'
$vectorVersion = '0.8.7'
$pgArchive = Join-Path $dist "postgresql-$pgVersion-windows-x86_64.zip"
$vectorArchive = Join-Path $dist "pgvector-$vectorVersion-postgresql-$pgVersion-windows-x86_64.zip"
$work = Join-Path $env:RUNNER_TEMP 'pg-binaries-windows-verify'
$unpacked = Join-Path $work 'unpacked'
$moved = Join-Path $work 'relocated install/PostgreSQL 18.6'
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
Assert-ArchiveHash $vectorArchive
New-Item -ItemType Directory -Force $unpacked, (Split-Path $moved -Parent) | Out-Null
Expand-Archive $pgArchive -DestinationPath $unpacked
Expand-Archive $vectorArchive -DestinationPath $unpacked
Move-Item (Join-Path $unpacked 'postgresql') $moved

$pgManifest = Get-Content (Join-Path $moved 'manifest.json') -Raw | ConvertFrom-Json
$vectorRoot = Join-Path $unpacked 'pgvector'
$vectorManifest = Get-Content (Join-Path $vectorRoot 'manifest.json') -Raw | ConvertFrom-Json
if ($pgManifest.schema_version -ne 1 -or $vectorManifest.schema_version -ne 1 -or
    $pgManifest.component -ne 'postgresql' -or $vectorManifest.component -ne 'pgvector' -or
    $pgManifest.version -ne $pgVersion -or $vectorManifest.version -ne $vectorVersion -or
    $pgManifest.postgresql_version -ne $vectorManifest.postgresql_version -or
    $pgManifest.platform -ne 'windows' -or $vectorManifest.platform -ne 'windows' -or
    $pgManifest.architecture -ne 'x86_64' -or $vectorManifest.architecture -ne 'x86_64') {
  throw 'Archive manifests do not match this verification target'
}
if (-not (Test-Path (Join-Path $moved 'LICENSES/PostgreSQL.txt')) -or
    -not (Test-Path (Join-Path $vectorRoot 'LICENSES/pgvector.txt')) -or
    -not (Test-Path (Join-Path $moved 'LICENSES/dependencies/icu.txt'))) {
  throw 'A required license text is missing'
}

Copy-Item (Join-Path $vectorRoot 'lib/vector.dll') (Join-Path $moved 'lib/vector.dll')
Copy-Item (Join-Path $vectorRoot 'share/extension/*') (Join-Path $moved 'share/extension')

$bin = Join-Path $moved 'bin'
$env:PATH = "$bin;$env:SystemRoot\System32;$env:SystemRoot"
$env:PGHOST = '127.0.0.1'
$env:PGPORT = '55432'
$env:PGUSER = 'postgres'
$env:PGDATABASE = 'postgres'
$initdb = Join-Path $bin 'initdb.exe'
$pgCtl = Join-Path $bin 'pg_ctl.exe'
$psql = Join-Path $bin 'psql.exe'
$pgDump = Join-Path $bin 'pg_dump.exe'
$pgRestore = Join-Path $bin 'pg_restore.exe'

& $initdb -D $data -U postgres -A trust --no-instructions
$started = $false
try {
  & $pgCtl -D $data -l (Join-Path $work 'postgres.log') -o "-h 127.0.0.1 -p $env:PGPORT" -w start
  $started = $true
  $reported = (& $psql -At -c 'SHOW server_version').Trim()
  if ($reported -ne $pgVersion) { throw "Server reports $reported, expected $pgVersion" }

  & $psql -X -v ON_ERROR_STOP=1 -f (Join-Path $repo 'tests/schema.sql')
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
  foreach ($method in @('gzip', 'lz4', 'zstd')) {
    $dump = Join-Path $work "pilot-$method.dump"
    & $pgDump -Fc -Z $method -f $dump postgres
    & $pgRestore -l $dump | Out-Null
  }

  $vectorSql = @'
CREATE EXTENSION vector;
CREATE TABLE pilot_vectors (id integer PRIMARY KEY, embedding vector(3));
INSERT INTO pilot_vectors VALUES (1, '[1,0,0]'), (2, '[0,1,0]'), (3, '[0,0,1]');
CREATE INDEX pilot_vectors_hnsw ON pilot_vectors USING hnsw (embedding vector_l2_ops);
SELECT id, embedding <-> '[1,0,0]'::vector AS distance FROM pilot_vectors ORDER BY embedding <-> '[1,0,0]'::vector LIMIT 2;
'@
  & $psql -X -v ON_ERROR_STOP=1 -c $vectorSql
  $installed = (& $psql -At -c "SELECT extversion FROM pg_extension WHERE extname = 'vector'").Trim()
  if ($installed -ne $vectorVersion) { throw "pgvector reports $installed, expected $vectorVersion" }
  Write-Host "Verified PostgreSQL $reported and pgvector $installed on Windows $([Environment]::OSVersion.Version) after archive relocation"
} finally {
  if ($started) { & $pgCtl -D $data -m immediate -w stop }
}
