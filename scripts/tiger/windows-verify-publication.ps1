param(
  [Parameter(Mandatory = $true)][string]$CoreArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$PostGISArchive,
  [Parameter(Mandatory = $true)][string]$TigerArchive,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [ValidateSet('16.15','17.11','18.6')][string]$PostgreSQLVersion = '18.6',
  [string]$CoreIdentityPath
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Set-StrictMode -Version Latest

if ($env:RUNNER_OS -ne 'Windows' -or -not [Environment]::Is64BitOperatingSystem) {
  throw 'This publication verifier requires Windows x86-64.'
}
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = (Get-Command python.exe -ErrorAction Stop).Source
$tar = (Get-Command tar.exe -ErrorAction Stop).Source
$coreDirectory = (Resolve-Path $CoreArchiveDirectory).Path
$PostGISArchive = (Resolve-Path $PostGISArchive).Path
$TigerArchive = (Resolve-Path $TigerArchive).Path
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path

$identityArguments = @('--postgresql-version', $PostgreSQLVersion)
if ($CoreIdentityPath) { $identityArguments += @('--path', (Resolve-Path $CoreIdentityPath).Path) }
$coreIdentity = (& $python (Join-Path $repo 'tools/windows_core_pin.py') @identityArguments | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0 -or -not $coreIdentity) { throw 'Cannot load the pinned Windows PostgreSQL core identity.' }
$coreArchive = Join-Path $coreDirectory $coreIdentity.archive_name
$postgisName = "postgis-3.6.4-postgresql-$PostgreSQLVersion-windows-x86_64.tar.gz"
$tigerName = "postgis_tiger_geocoder-2025.2-postgresql-$PostgreSQLVersion-windows-x86_64.tar.gz"
if ([IO.Path]::GetFileName($PostGISArchive) -cne $postgisName -or [IO.Path]::GetFileName($TigerArchive) -cne $tigerName) {
  throw 'PostGIS or TIGER archive name does not match the requested target.'
}
$coreHash = (Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($coreHash -cne $coreIdentity.sha256) { throw 'Core archive differs from the pinned PostgreSQL artifact.' }
foreach ($entry in @(@($coreArchive, 'postgresql'), @($PostGISArchive, 'postgis'), @($TigerArchive, 'postgis_tiger_geocoder'))) {
  if (-not (Test-Path $entry[0] -PathType Leaf) -or -not (Test-Path "$($entry[0]).sha256" -PathType Leaf)) {
    throw "Archive or checksum sidecar is missing: $($entry[0])"
  }
  $actual = (Get-FileHash $entry[0] -Algorithm SHA256).Hash.ToLowerInvariant()
  $sidecar = ((Get-Content "$($entry[0]).sha256" -Raw) -split '\s+')[0].ToLowerInvariant()
  if ($sidecar -notmatch '^[0-9a-f]{64}$' -or $actual -cne $sidecar) { throw "Archive checksum mismatch: $($entry[0])" }
  & $python (Join-Path $repo 'tools/license_pointer.py') verify $entry[0] $entry[1]
  if ($LASTEXITCODE -ne 0) { throw "Licence pointer verification failed: $($entry[0])" }
}

$work = Join-Path $env:RUNNER_TEMP ("tiger-windows-verify-" + [guid]::NewGuid().ToString('N'))
$first = Join-Path $work 'first'
$postgisUnpack = Join-Path $work 'postgis-archive'
$tigerUnpack = Join-Path $work 'tiger-archive'
$moved = Join-Path $work 'relocated'
$data = Join-Path $work 'data'
$serverStarted = $false
$originalPath = $env:PATH
$pgRoot = $null
New-Item -ItemType Directory -Force $first,$postgisUnpack,$tigerUnpack,$moved | Out-Null
try {
  foreach ($entry in @(@($coreArchive,$first), @($PostGISArchive,$postgisUnpack), @($TigerArchive,$tigerUnpack))) {
    & $tar -xzf $entry[0] -C $entry[1]
    if ($LASTEXITCODE -ne 0) { throw "Could not extract archive: $($entry[0])" }
  }
  $pgRoot = Join-Path $first 'postgresql'
  $postgisRoot = Join-Path $postgisUnpack 'postgis'
  $tigerRoot = Join-Path $tigerUnpack 'postgis_tiger_geocoder'
  foreach ($entry in @(@($postgisUnpack,'postgis'), @($tigerUnpack,'postgis_tiger_geocoder'))) {
    $names = @(Get-ChildItem $entry[0] -Force | ForEach-Object Name | Sort-Object)
    if ($names.Count -ne 2 -or $names -cnotcontains $entry[1] -or $names -cnotcontains 'metadata.json') {
      throw "Unexpected top-level content in $($entry[1]) archive."
    }
  }
  $manifest = Get-Content (Join-Path $pgRoot 'manifest.json') -Raw | ConvertFrom-Json
  foreach ($key in @('component','version','postgresql_version','platform','architecture','build_id','source_revision')) {
    $expected = switch ($key) {
      component { 'postgresql' }
      version { $PostgreSQLVersion }
      postgresql_version { $PostgreSQLVersion }
      platform { 'windows' }
      architecture { 'x86_64' }
      build_id { $coreIdentity.build_id }
      source_revision { $coreIdentity.source_revision }
    }
    if ($manifest.$key -cne $expected) { throw "Core manifest $key mismatch." }
  }
  if ((& (Join-Path $pgRoot 'bin/pg_config.exe') --version) -cne "PostgreSQL $PostgreSQLVersion") { throw 'Core pg_config version mismatch.' }

  $postgisMetadata = Get-Content (Join-Path $postgisUnpack 'metadata.json') -Raw | ConvertFrom-Json
  $tigerMetadata = Get-Content (Join-Path $tigerUnpack 'metadata.json') -Raw | ConvertFrom-Json
  foreach ($metadata in @($postgisMetadata,$tigerMetadata)) {
    if ($metadata.postgresql_version -cne $PostgreSQLVersion -or $metadata.platform -cne 'windows' -or $metadata.architecture -cne 'x86_64') {
      throw 'Extension metadata target does not match PostgreSQL Windows x86-64.'
    }
  }
  if ($postgisMetadata.project -cne 'postgis' -or $postgisMetadata.version -cne '3.6.4' -or
      $postgisMetadata.core_archive -and ($postgisMetadata.core_archive.basename -cne $coreIdentity.archive_name -or $postgisMetadata.core_archive.sha256 -cne $coreHash)) {
    throw 'PostGIS metadata does not match the expected project, version, or linked core archive.'
  }
  if ($postgisMetadata.source -and ($postgisMetadata.source.url -cne 'https://download.osgeo.org/postgis/source/postgis-3.6.4.tar.gz' -or
      $postgisMetadata.source.sha256 -cne 'ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6')) {
    throw 'PostGIS metadata does not match the expected source identity.'
  }
  if ($tigerMetadata.project -cne 'postgis_tiger_geocoder' -or $tigerMetadata.version -cne '2025.2' -or
      $tigerMetadata.source.url -cne 'https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/postgis_tiger_geocoder-2025.2.tar.gz' -or
      $tigerMetadata.source.sha256 -cne 'c33cfbfb40785db8754a36be66060e8d023773e7e1be8fb8a622bb3c48db9f54') {
    throw 'TIGER metadata does not match the expected source identity.'
  }
  $extensionSql = Join-Path $tigerRoot 'share/extension'
  foreach ($file in @('postgis_tiger_geocoder.control','postgis_tiger_geocoder--2025.2.sql')) {
    if (-not (Test-Path (Join-Path $extensionSql $file) -PathType Leaf)) { throw "TIGER SQL payload is missing $file." }
  }
  if (Get-ChildItem $tigerRoot -Recurse -File | Where-Object { $_.Extension -in @('.dll','.so','.dylib') }) {
    throw 'SQL-only TIGER archive contains a native library.'
  }

  $occupied = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
  foreach ($entry in @(@($postgisRoot,'postgis'), @($tigerRoot,'postgis_tiger_geocoder'))) {
    foreach ($file in Get-ChildItem $entry[0] -Recurse -File) {
      $relative = $file.FullName.Substring($entry[0].Length).TrimStart('\','/')
      $destination = Join-Path $pgRoot $relative
      if (-not $occupied.Add($relative) -or (Test-Path $destination)) { throw "Archive assembly collision at $relative" }
    }
  }
  foreach ($entry in @(@($postgisRoot,$pgRoot), @($tigerRoot,$pgRoot))) {
    foreach ($file in Get-ChildItem $entry[0] -Recurse -File) {
      $relative = $file.FullName.Substring($entry[0].Length).TrimStart('\','/')
      $destination = Join-Path $entry[1] $relative
      New-Item -ItemType Directory -Force (Split-Path $destination -Parent) | Out-Null
      Copy-Item $file.FullName $destination
    }
  }
  Move-Item $pgRoot (Join-Path $moved 'postgresql')
  $pgRoot = Join-Path $moved 'postgresql'
  $pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
  foreach ($relative in @('share/extension/postgis.control','share/extension/postgis_tiger_geocoder.control')) {
    if (-not (Test-Path (Join-Path $pgRoot $relative) -PathType Leaf)) { throw "Assembled extension file missing: $relative" }
  }

  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
  if (-not (Test-Path $vswhere -PathType Leaf)) { throw 'Visual Studio vswhere.exe is missing.' }
  $vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $vsRoot) { throw 'The verifier has no x64 dumpbin tool.' }
  $dumpbin = Get-ChildItem (Join-Path $vsRoot 'VC/Tools/MSVC') -Filter dumpbin.exe -Recurse -File | Select-Object -First 1 -ExpandProperty FullName
  if (-not $dumpbin) { throw 'dumpbin.exe is missing.' }
  & $python (Join-Path $repo 'tools/check_pe_dependencies.py') $pgRoot --dumpbin $dumpbin --archive $coreArchive --archive $PostGISArchive --archive $TigerArchive --report (Join-Path $OutputDirectory 'static-analysis.json')
  if ($LASTEXITCODE -ne 0) { throw 'Windows PE dependency inspection failed.' }

  $env:PATH = "$(Join-Path $pgRoot 'bin');$env:SystemRoot\System32;$env:SystemRoot"
  & (Join-Path $pgRoot 'bin/initdb.exe') -D $data -U postgres -A trust --encoding=UTF8 --locale=C --no-instructions
  if ($LASTEXITCODE -ne 0) { throw 'initdb failed for the relocated PostgreSQL installation.' }
  & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -l (Join-Path $OutputDirectory 'server.log') -o '-p 55432 -h 127.0.0.1' -w start
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL failed to start after relocation.' }
  $serverStarted = $true
  & (Join-Path $pgRoot 'bin/psql.exe') -X -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -f (Join-Path $repo 'scripts/tiger/probe.sql') 2>&1 | Tee-Object -FilePath (Join-Path $OutputDirectory 'probe-output.txt')
  if ($LASTEXITCODE -ne 0) { throw 'TIGER SQL probe failed.' }
  & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m fast -w stop
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not stop cleanly.' }
  $serverStarted = $false
  Write-Output "PASS: TIGER Geocoder 2025.2 installed with PostGIS 3.6.4 and relocated PostgreSQL $PostgreSQLVersion on Windows x86-64."
} finally {
  if ($serverStarted -and $pgRoot) { & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m immediate stop 2>$null | Out-Null }
  $env:PATH = $originalPath
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
