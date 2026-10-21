param(
  [Parameter(Mandatory = $true)][string]$ArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$ArchiveDirectory = (Resolve-Path $ArchiveDirectory).Path
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
$work = Join-Path $env:RUNNER_TEMP 'postgis-windows-relocated-trial'
$coreArchive = Join-Path $ArchiveDirectory 'postgresql-18.6-windows-x86_64.tar.gz'
$extensionArchive = Join-Path $ArchiveDirectory 'postgis-3.6.4-postgresql-18.6-windows-x86_64-trial.tar.gz'

function Assert-ArchiveHash([string]$archive) {
  $line = (Get-Content "$archive.sha256" -Raw).Trim()
  $parts = $line -split '\s+', 2
  if ($parts.Count -ne 2 -or $parts[1] -ne (Split-Path $archive -Leaf)) {
    throw "Invalid checksum companion for $archive"
  }
  if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $parts[0]) {
    throw "Archive checksum mismatch for $archive"
  }
}

Assert-ArchiveHash $coreArchive
Assert-ArchiveHash $extensionArchive
$coreSha = (Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant()
$extensionSha = (Get-FileHash $extensionArchive -Algorithm SHA256).Hash.ToLowerInvariant()
$coreExtract = Join-Path $work 'core-extract'
$extensionExtract = Join-Path $work 'extension-extract'
$relocated = Join-Path $work 'moved/PostgreSQL 18.6'
$data = Join-Path $work 'cluster'
New-Item -ItemType Directory -Force $coreExtract, $extensionExtract, (Split-Path $relocated -Parent) | Out-Null
tar.exe -xzf $coreArchive -C $coreExtract
tar.exe -xzf $extensionArchive -C $extensionExtract
$sourceCore = Join-Path $coreExtract 'postgresql'
$extension = Join-Path $extensionExtract 'postgis'
if (-not (Test-Path (Join-Path $sourceCore 'bin/postgres.exe')) -or
    -not (Test-Path (Join-Path $extension 'metadata.json'))) {
  throw 'Trial archive layout is invalid'
}
$metadata = Get-Content (Join-Path $extension 'metadata.json') -Raw | ConvertFrom-Json
if ($metadata.purpose -ne 'non-publication-relocation-trial' -or
    $metadata.project -ne 'PostGIS' -or $metadata.version -ne '3.6.4' -or
    $metadata.postgresql_version -ne '18.6' -or $metadata.platform -ne 'windows' -or
    $metadata.core_archive_sha256 -ne $coreSha) {
  throw 'Trial metadata does not bind this PostGIS archive to the selected PostgreSQL core'
}
Move-Item $sourceCore $relocated
$pgRoot = $relocated
Get-ChildItem $extension -Force -Recurse | Where-Object FullName -notlike "$(Join-Path $extension 'metadata.json')" | ForEach-Object {
  $relative = $_.FullName.Substring($extension.Length).TrimStart('\', '/')
  $destination = Join-Path $pgRoot $relative
  if ($_.PSIsContainer) {
    New-Item -ItemType Directory -Force $destination | Out-Null
  } else {
    New-Item -ItemType Directory -Force (Split-Path $destination -Parent) | Out-Null
    if (Test-Path $destination -PathType Leaf) {
      $archiveHash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
      $coreHash = (Get-FileHash $destination -Algorithm SHA256).Hash
      if ($archiveHash -ne $coreHash) { throw "Extension payload would replace a different core file: $relative" }
    }
    Copy-Item $_.FullName $destination -Force
  }
}

$pgBin = Join-Path $pgRoot 'bin'
$extensionBin = Join-Path $pgRoot 'bin'
$env:PATH = "$extensionBin;$pgBin;$env:SystemRoot\System32;$env:SystemRoot"
$env:GDAL_DATA = Join-Path $pgRoot 'share/gdal'
$env:PROJ_DATA = Join-Path $pgRoot 'share/proj'
$env:PROJ_LIB = $env:PROJ_DATA
$env:PGHOST = '127.0.0.1'
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$env:PGPORT = [string]$listener.LocalEndpoint.Port
$listener.Stop()
$env:PGUSER = 'postgres'
$env:PGDATABASE = 'postgres'
$env:PGSSLMODE = 'disable'
& (Join-Path $pgBin 'initdb.exe') -D $data -U postgres -A trust --encoding=UTF8 --no-instructions 2>&1 |
  Tee-Object -FilePath (Join-Path $OutputDirectory 'initdb.log')
if ($LASTEXITCODE -ne 0) { throw "initdb.exe failed with exit code $LASTEXITCODE" }
& (Join-Path $pgBin 'pg_ctl.exe') -D $data -l (Join-Path $OutputDirectory 'server.log') `
  -o "-p $env:PGPORT -h 127.0.0.1" start
try {
  & (Join-Path $pgBin 'psql.exe') -X -v ON_ERROR_STOP=1 -d postgres `
    -f (Join-Path $PSScriptRoot '../../scripts/postgis/probe.sql') 2>&1 |
    Tee-Object -FilePath (Join-Path $OutputDirectory 'probe-output.txt')
  if ($LASTEXITCODE -ne 0) { throw "psql.exe failed with exit code $LASTEXITCODE" }
  $record = [ordered]@{
    schema_version = 1
    outcome = 'passed'
    runner_os = [System.Environment]::OSVersion.Version.ToString()
    archives = [ordered]@{
      postgresql = [ordered]@{ basename = (Split-Path $coreArchive -Leaf); sha256 = $coreSha }
      postgis = [ordered]@{ basename = (Split-Path $extensionArchive -Leaf); sha256 = $extensionSha }
    }
    checks = @('archive-sha256', 'core-binding', 'relocation', 'postgis', 'postgis_raster', 'postgis_topology', 'postgis_sfcgal', 'transform')
  }
  $record | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'result.json')
} finally {
  & (Join-Path $pgBin 'pg_ctl.exe') -D $data -m immediate stop 2>$null
}
