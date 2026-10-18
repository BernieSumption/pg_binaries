param(
  [Parameter(Mandatory = $true)][string]$CoreArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$ExtensionArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [ValidateSet('15.19','16.15','17.11','18.6')][string]$PostgreSQLVersion = '18.6'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not [Environment]::Is64BitOperatingSystem -or $env:RUNNER_OS -ne 'Windows') {
  throw 'This publication verifier requires Windows x86-64.'
}
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$coreArchiveDirectory = (Resolve-Path $CoreArchiveDirectory).Path
$extensionArchiveDirectory = (Resolve-Path $ExtensionArchiveDirectory).Path
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path

$identityTool = Join-Path $repo 'tools/windows_core_pin.py'
$coreIdentity = (& python $identityTool --postgresql-version $PostgreSQLVersion | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0 -or -not $coreIdentity) { throw 'Cannot load the pinned Windows PostgreSQL core identity' }
$pgVersion = $coreIdentity.postgresql_version
$version = '1.3.4'
$architecture = 'x86_64'
$coreName = $coreIdentity.archive_name
$extensionName = "pgtap-$version-postgresql-$pgVersion-windows-$architecture.tar.gz"
$coreArchive = Join-Path $coreArchiveDirectory $coreName
$extensionArchive = Join-Path $extensionArchiveDirectory $extensionName
foreach ($path in @($coreArchive, $extensionArchive, "$coreArchive.sha256", "$extensionArchive.sha256")) {
  if (-not (Test-Path $path -PathType Leaf)) { throw "Required final archive or checksum sidecar is missing: $path" }
}

$coreHash = (Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant()
$extensionHash = (Get-FileHash $extensionArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($coreHash -cne $coreIdentity.sha256) { throw 'Core archive differs from the pinned PostgreSQL artifact' }
foreach ($entry in @(@("$coreArchive.sha256", $coreHash), @("$extensionArchive.sha256", $extensionHash))) {
  $sidecarHash = ((Get-Content $entry[0] -Raw) -split '\s+')[0].ToLowerInvariant()
  if ($sidecarHash -cne $entry[1]) { throw "Archive checksum sidecar mismatch: $($entry[0])" }
}

$staticReport = Join-Path $OutputDirectory 'static-analysis.json'
& python (Join-Path $repo 'tools/check_pgtap_windows_archive.py') `
  --postgresql-version $pgVersion --core-archive $coreArchive `
  --extension-archive $extensionArchive --output $staticReport
if ($LASTEXITCODE -ne 0) { throw 'Final core and pgTAP archive inspection failed' }

$work = Join-Path $env:RUNNER_TEMP ("pgtap-windows-verify-" + [guid]::NewGuid().ToString('N'))
$first = Join-Path $work 'first'
$moved = Join-Path $work 'moved'
$package = Join-Path $work 'extension-package'
$data = Join-Path $work 'data'
New-Item -ItemType Directory -Force $first,$moved,$package | Out-Null
$serverStarted = $false
$originalPath = $env:PATH
$pgRoot = $null
try {
  tar.exe -xzf $coreArchive -C $first
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract final PostgreSQL archive' }
  tar.exe -xzf $extensionArchive -C $package
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract final pgTAP archive' }
  $pgRoot = Join-Path $first 'postgresql'
  $extensionPayload = Join-Path $package 'pgtap'
  $manifest = Get-Content (Join-Path $pgRoot 'manifest.json') -Raw | ConvertFrom-Json
  $expectedManifest = @{
    component = 'postgresql'; version = $pgVersion; postgresql_version = $pgVersion
    platform = 'windows'; architecture = $architecture; build_id = $coreIdentity.build_id
    source_revision = $coreIdentity.source_revision
  }
  foreach ($key in @('component','version','postgresql_version','platform','architecture','build_id','source_revision')) {
    if ($manifest.$key -cne $expectedManifest[$key]) { throw "Core manifest $key mismatch: $($manifest.$key)" }
  }
  $pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
  $initdb = Join-Path $pgRoot 'bin/initdb.exe'
  $pgCtl = Join-Path $pgRoot 'bin/pg_ctl.exe'
  $psql = Join-Path $pgRoot 'bin/psql.exe'
  foreach ($path in @($pgConfig,$initdb,$pgCtl,$psql)) { if (-not (Test-Path $path -PathType Leaf)) { throw "Core executable missing: $path" } }
  if ((& $pgConfig --version) -cne "PostgreSQL $pgVersion") { throw 'PostgreSQL version mismatch' }
  $metadata = Get-Content (Join-Path $package 'metadata.json') -Raw | ConvertFrom-Json
  if ($metadata.project -cne 'pgtap' -or $metadata.version -cne $version -or
      $metadata.postgresql_version -cne $pgVersion -or $metadata.platform -cne 'windows' -or
      $metadata.architecture -cne $architecture -or $metadata.core_archive.basename -cne $coreName -or
      $metadata.core_archive.sha256 -cne $coreHash -or
      $metadata.source.sha256 -cne 'd2c951afb296a001d21785611a8e966e3f8fa3f5bfbd929396a5130c0152f314') {
    throw 'Final pgTAP metadata does not bind the expected source and core archives'
  }

  foreach ($file in Get-ChildItem $extensionPayload -Recurse -File) {
    $relative = $file.FullName.Substring($extensionPayload.Length).TrimStart('\','/')
    $destination = Join-Path $pgRoot $relative
    if (Test-Path $destination) { throw "pgTAP payload collision: $relative" }
  }
  Move-Item $pgRoot (Join-Path $moved 'postgresql')
  $pgRoot = Join-Path $moved 'postgresql'
  $initdb = Join-Path $pgRoot 'bin/initdb.exe'
  $pgCtl = Join-Path $pgRoot 'bin/pg_ctl.exe'
  $psql = Join-Path $pgRoot 'bin/psql.exe'
  foreach ($file in Get-ChildItem $extensionPayload -Recurse -File) {
    $relative = $file.FullName.Substring($extensionPayload.Length).TrimStart('\','/')
    $destination = Join-Path $pgRoot $relative
    New-Item -ItemType Directory -Force (Split-Path $destination -Parent) | Out-Null
    Copy-Item $file.FullName $destination
  }

  $env:PATH = "$(Join-Path $pgRoot 'bin');$env:SystemRoot\System32;$env:SystemRoot"
  & $initdb -D $data -U postgres -A trust --encoding=UTF8 --locale=C --no-instructions
  if ($LASTEXITCODE -ne 0) { throw 'initdb failed for relocated PostgreSQL' }
  & $pgCtl -D $data -l (Join-Path $work 'server.log') -o '-p 55432 -h 127.0.0.1' -w start
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL failed to start after relocation' }
  $serverStarted = $true
  $prerequisiteOutput = Join-Path $OutputDirectory 'prerequisite-output.txt'
  & $psql -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres `
    -c 'CREATE EXTENSION IF NOT EXISTS plpgsql' | Tee-Object -FilePath $prerequisiteOutput
  if ($LASTEXITCODE -ne 0) { throw 'Could not create pgTAP configuration prerequisite plpgsql' }
  $probeOutput = Join-Path $OutputDirectory 'probe-output.txt'
  & $psql -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres `
    -f (Join-Path $repo 'scripts/pgtap/probe.sql') 2>&1 | Tee-Object -FilePath $probeOutput
  if ($LASTEXITCODE -ne 0) { throw 'pgTAP SQL assertions failed' }
  if (-not (Select-String -Path $probeOutput -SimpleMatch '1..4' -Quiet)) { throw 'pgTAP plan output missing' }
  $okCount = @(Select-String -Path $probeOutput -Pattern '^ok [1-4]( -|$)').Count
  if ($okCount -ne 4) { throw "Expected four passing pgTAP assertions; found $okCount" }
  $closurePath = Join-Path $OutputDirectory 'extension-closure.txt'
  & $psql -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres `
    -c "SELECT extname FROM pg_extension WHERE extname IN ('pgtap','plpgsql') ORDER BY extname; SELECT count(*) FROM pg_depend d JOIN pg_extension e ON e.oid=d.refobjid WHERE e.extname='pgtap' AND d.deptype='e';" |
    Tee-Object -FilePath $closurePath
  if ($LASTEXITCODE -ne 0) { throw 'Could not inspect installed extension dependency closure' }
  $closure = Get-Content $closurePath
  if (-not ($closure -contains 'pgtap') -or -not ($closure | Where-Object { $_ -match '^[1-9][0-9]*$' })) {
    throw 'Installed pgTAP extension or its owned-object closure is missing'
  }
  & $pgCtl -D $data -m fast -w stop
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not stop cleanly' }
  $serverStarted = $false
  Write-Output "PASS: final pgTAP $version archive installed and exercised with relocated PostgreSQL $pgVersion on Windows x86-64"
} finally {
  if ($serverStarted -and $pgRoot) { & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m immediate stop 2>$null | Out-Null }
  $env:PATH = $originalPath
  Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}
