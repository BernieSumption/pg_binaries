param(
  [Parameter(Mandatory = $true)][string]$ArchiveDirectory,
  [string]$PostgreSQLVersion = '18.6',
  [string]$PgvectorVersion = '0.8.7',
  [switch]$CoreOnly,
  [string]$ReportPath
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
$architecture = 'x86_64'
if (-not $ReportPath) { $ReportPath = Join-Path $ArchiveDirectory "windows-diagnostics-$PostgreSQLVersion-$architecture.json" }
$ReportPath = [IO.Path]::GetFullPath($ReportPath)
$archives = (Resolve-Path $ArchiveDirectory).Path
$pgName = "postgresql-$PostgreSQLVersion-windows-$architecture.tar.gz"
$pgArchive = Join-Path $archives $pgName
$archivePaths = @($pgArchive)
$vectorName = $null
$vectorArchive = $null
if (-not $CoreOnly) {
  $vectorName = "pgvector-$PgvectorVersion-postgresql-$PostgreSQLVersion-windows-$architecture.tar.gz"
  $vectorArchive = Join-Path $archives $vectorName
  $archivePaths += $vectorArchive
}
foreach ($archive in $archivePaths) {
  if (-not (Test-Path $archive -PathType Leaf) -or (Get-Item $archive).Length -eq 0) { throw "Missing diagnostic archive: $archive" }
  $sidecar = Get-Content "$archive.sha256" -Raw
  if ($sidecar -notmatch ('(?m)^([0-9a-fA-F]{64})\s+' + [regex]::Escape((Split-Path $archive -Leaf)) + '\s*$')) { throw "Invalid checksum sidecar for $archive" }
  if ($Matches[1].ToLowerInvariant() -ne (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()) { throw "Archive checksum mismatch: $archive" }
}

$work = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString('N'))
$systemTree = Join-Path $work 'system'
$serverTree = Join-Path $work 'server'
$null = New-Item -ItemType Directory -Force $systemTree, $serverTree
$oldPath = $env:PATH
$oldPgPort = $env:PGPORT
$oldPgHost = $env:PGHOST
$oldPgUser = $env:PGUSER
$oldPgDatabase = $env:PGDATABASE
$oldSslMode = $env:PGSSLMODE
$started = $false
try {
  foreach ($tree in @($systemTree, $serverTree)) {
    & tar.exe -xzf $pgArchive -C $tree
    if ($LASTEXITCODE -ne 0) { throw 'Failed to extract PostgreSQL archive' }
    if (-not $CoreOnly) {
      & tar.exe -xzf $vectorArchive -C $tree
      if ($LASTEXITCODE -ne 0) { throw 'Failed to extract pgvector archive' }
    }
  }
  $root = Join-Path $systemTree 'postgresql'
  $pgManifest = Get-Content (Join-Path $root 'manifest.json') -Raw | ConvertFrom-Json
  $vectorMetadata = $null
  if (-not $CoreOnly) {
    $vectorMetadata = Get-Content (Join-Path $systemTree 'metadata.json') -Raw | ConvertFrom-Json
    if ($pgManifest.build_id -cne $vectorMetadata.build_id) { throw 'Archive metadata has inconsistent build identifiers' }
  }
  if (-not $pgManifest.build_id -or $pgManifest.platform -ne 'windows' -or
      $pgManifest.architecture -ne $architecture -or $pgManifest.version -ne $PostgreSQLVersion -or
      (-not $CoreOnly -and $vectorMetadata.version -ne $PgvectorVersion)) { throw 'Archive metadata does not match requested diagnostic target' }

  $runtimeCandidates = @(@('libxml2.dll', 'libcrypto-3-x64.dll') | Where-Object {
    ($_ -in $pgManifest.bundled_runtime_dlls) -and
    (Test-Path (Join-Path (Join-Path $root 'bin') $_) -PathType Leaf) -and
    -not (Test-Path (Join-Path "$env:SystemRoot\System32" $_) -PathType Leaf)
  })
  if ($runtimeCandidates.Count -eq 0) { throw 'No directly imported bundled DLL is absent from System32; cannot isolate a loader failure on this runner' }
  $missingDll = $runtimeCandidates[0]
  $hiddenDll = Join-Path (Join-Path $root 'bin') "$missingDll.diagnostic-hidden"
  Move-Item (Join-Path (Join-Path $root 'bin') $missingDll) $hiddenDll

  $systemPath = "$env:SystemRoot\System32;$env:SystemRoot"
  $env:PATH = $systemPath
  $systemCommand = "& '$root\bin\postgres.exe' --version"
  $systemCwd = $root
  $systemStarted = [DateTime]::UtcNow.ToString('o')
  $systemText = ''
  $systemStatus = 0
  Push-Location $systemCwd
  try {
    try {
      $systemText = (& (Join-Path $root 'bin/postgres.exe') --version 2>&1 | Out-String).Trim()
      $systemStatus = $LASTEXITCODE
    } catch {
      $systemText = $_.Exception.Message
      $systemStatus = 9009
    }
  } finally { Pop-Location }
  $systemFinished = [DateTime]::UtcNow.ToString('o')
  $systemStatusHex = '0x{0:X8}' -f [BitConverter]::ToUInt32([BitConverter]::GetBytes([int32]$systemStatus), 0)
  if ($systemStatus -eq 0 -or ($systemStatusHex -ne '0xC0000135' -and $systemText -notmatch '(?i)(module|DLL|specified|load|0xc0000135|not found)')) {
    throw "Missing-runtime probe did not capture a loader failure (exit $systemStatus): $systemText"
  }

  $serverRoot = Join-Path $serverTree 'postgresql'
  $bin = Join-Path $serverRoot 'bin'
  $data = Join-Path $serverTree 'data'
  $log = Join-Path $serverTree 'server.log'
  $serverPath = "$bin;$env:SystemRoot\System32;$env:SystemRoot"
  $env:PATH = $serverPath
  $env:PGHOST = '127.0.0.1'; $env:PGPORT = '55439'; $env:PGUSER = 'postgres'; $env:PGDATABASE = 'postgres'; $env:PGSSLMODE = 'disable'
  & (Join-Path $bin 'initdb.exe') -D $data -U postgres -A trust --encoding=UTF8 --no-instructions *> (Join-Path $serverTree 'initdb.log')
  if ($LASTEXITCODE -ne 0) { throw 'initdb failed; diagnostic server-error probe cannot continue' }
  $pgCtl = Join-Path $bin 'pg_ctl.exe'
  $psql = Join-Path $bin 'psql.exe'
  & $pgCtl -D $data -l $log -o "-h 127.0.0.1 -p $env:PGPORT" -w start
  if ($LASTEXITCODE -ne 0) { throw 'Could not start PostgreSQL for server-log probe' }
  $started = $true
  $serverCommand = "& '$psql' -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55439 -d postgres -c 'SELECT 1 / 0;'"
  $serverCwd = $serverTree
  $serverStarted = [DateTime]::UtcNow.ToString('o')
  Push-Location $serverCwd
  try {
    $clientText = (& $psql -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55439 -d postgres -c 'SELECT 1 / 0;' 2>&1 | Out-String).Trim()
    $clientStatus = $LASTEXITCODE
  } finally { Pop-Location }
  $serverFinished = [DateTime]::UtcNow.ToString('o')
  & $pgCtl -D $data -m fast -w stop
  if ($LASTEXITCODE -ne 0) { throw 'Could not stop diagnostic PostgreSQL server cleanly' }
  $started = $false
  $serverLog = Get-Content $log -Raw
  if ($clientStatus -eq 0 -or $serverLog -notmatch 'ERROR:\s+division by zero') { throw 'PostgreSQL probe did not produce the expected server log error' }

  $os = Get-CimInstance Win32_OperatingSystem
  $version = (& (Join-Path $bin 'postgres.exe') --version 2>&1 | Out-String).Trim()
  $record = [ordered]@{
    schema_version = 1; platform = 'windows'; architecture = $architecture
    os = [ordered]@{ caption = $os.Caption; version = $os.Version; build_number = $os.BuildNumber; service_pack = $os.ServicePackMajorVersion }
    powershell_version = $PSVersionTable.PSVersion.ToString()
    postgresql_version = $PostgreSQLVersion
    build_id = $pgManifest.build_id; source_revision = $pgManifest.source_revision
    inventory_revision = $null; archive_urls = $null
    archives = [ordered]@{ $pgName = (Get-FileHash $pgArchive -Algorithm SHA256).Hash.ToLowerInvariant() }
    package_metadata = [ordered]@{ postgresql = $pgManifest }
    inspection_tools = [ordered]@{ powershell = $PSVersionTable.PSVersion.ToString(); tar = ((& tar.exe --version 2>&1 | Select-Object -First 1) -join ''); postgres = $version }
    lookup_environment = [ordered]@{
      system_failure = [ordered]@{ PATH = $systemPath; SystemRoot = $env:SystemRoot }
      postgresql_failure = [ordered]@{ PATH = $serverPath; PGHOST = $env:PGHOST; PGPORT = $env:PGPORT; PGUSER = $env:PGUSER; PGDATABASE = $env:PGDATABASE; PGSSLMODE = $env:PGSSLMODE }
    }
    system_failure = [ordered]@{ kind = 'missing-bundled-runtime-dll'; executable = (Join-Path $root 'bin/postgres.exe'); missing_library = $missingDll; hidden_library_path = $hiddenDll; command = $systemCommand; cwd = $systemCwd; started_at_utc = $systemStarted; finished_at_utc = $systemFinished; exit_code = $systemStatus; ntstatus = $systemStatusHex; failure_text = $systemText }
    postgresql_failure = [ordered]@{ kind = 'server-error'; executable = $psql; command = $serverCommand; cwd = $serverCwd; server_start_command = "& '$pgCtl' -D '$data' -l '$log' -o '-h 127.0.0.1 -p 55439' -w start"; started_at_utc = $serverStarted; finished_at_utc = $serverFinished; exit_code = $clientStatus; failure_text = $clientText; server_log = $serverLog }
  }
  if (-not $CoreOnly) {
    $record.pgvector_version = $PgvectorVersion
    $record.archives[$vectorName] = (Get-FileHash $vectorArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    $record.package_metadata.pgvector = $vectorMetadata
  }
  New-Item -ItemType Directory -Force (Split-Path $ReportPath -Parent) | Out-Null
  $record | ConvertTo-Json -Depth 12 | Set-Content -Encoding utf8 $ReportPath
  Write-Host "Windows failure diagnostics written to $ReportPath"
} finally {
  if ($started) { & (Join-Path $serverRoot 'bin/pg_ctl.exe') -D $data -m immediate -w stop *> $null }
  $env:PATH = $oldPath
  $env:PGPORT = $oldPgPort; $env:PGHOST = $oldPgHost; $env:PGUSER = $oldPgUser; $env:PGDATABASE = $oldPgDatabase; $env:PGSSLMODE = $oldSslMode
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
