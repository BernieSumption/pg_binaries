param(
  [Parameter(Mandatory = $true)][string]$CoreArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$SourcePackageDirectory,
  [Parameter(Mandatory = $true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$pgVersion = '18.6'
$version = '1.3.4'
$architecture = 'x86_64'
$runId = '39077749917'
$coreName = "postgresql-$pgVersion-windows-$architecture.tar.gz"
$archiveName = "pgtap-$version-postgresql-$pgVersion-windows-$architecture.tar.gz"
$coreSha256 = '2e48881e4b5c3289bc9526ee846685d62f6cfa4fff2539cb6393f36f605fcceb'
$sourcePackageName = 'pgtap-1.3.4-postgresql-18.6-macos-arm64.tar.gz'
$sourcePackageSha256 = '81e422272da2fecc9d74fe1479c6df8d960f797d3eb51111db377f0e0daef0e2'
$sourceUrl = 'https://github.com/theory/pgtap/archive/refs/tags/v1.3.4.tar.gz'
$sourceSha256 = 'd2c951afb296a001d21785611a8e966e3f8fa3f5bfbd929396a5130c0152f314'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$coreArchiveDirectory = (Resolve-Path $CoreArchiveDirectory).Path
$SourcePackageDirectory = (Resolve-Path $SourcePackageDirectory).Path
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path

if (-not [Environment]::Is64BitOperatingSystem -or $env:RUNNER_OS -ne 'Windows') {
  throw 'This feasibility probe requires Windows x86-64.'
}
$coreArchive = Join-Path $coreArchiveDirectory $coreName
if (-not (Test-Path $coreArchive -PathType Leaf)) { throw "Missing core archive: $coreName" }
$actualCoreHash = (Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualCoreHash -ne $coreSha256) { throw "Pinned core archive checksum mismatch: $actualCoreHash" }
$sidecarHash = ((Get-Content "$coreArchive.sha256" -Raw) -split '\s+')[0].ToLowerInvariant()
if ($sidecarHash -ne $coreSha256) { throw 'Core checksum sidecar does not match the pinned archive identity' }

$work = Join-Path $env:RUNNER_TEMP ("pgtap-windows-" + [guid]::NewGuid().ToString('N'))
$first = Join-Path $work 'first'
$stage = Join-Path $work 'stage'
$moved = Join-Path $work 'moved'
$sourceUnpacked = Join-Path $work 'source-package'
$packageUnpacked = Join-Path $work 'final-package'
$data = Join-Path $work 'data'
New-Item -ItemType Directory -Force $first,$stage,$moved,$sourceUnpacked,$packageUnpacked | Out-Null
$serverStarted = $false
$originalPath = $env:PATH
try {
  tar.exe -xzf $coreArchive -C $first
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract PostgreSQL core archive' }
  $pgRoot = Join-Path $first 'postgresql'
  $manifestPath = Join-Path $pgRoot 'manifest.json'
  if (-not (Test-Path $manifestPath -PathType Leaf)) { throw 'Core archive manifest missing' }
  $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
  $expected = @{
    component = 'postgresql'; version = $pgVersion; postgresql_version = $pgVersion
    platform = 'windows'; architecture = $architecture; build_id = "github-$runId-1"
    source_revision = '54f7a3079e7cb6631bf48ab2453822133087aeed'
  }
  foreach ($key in $expected.Keys) {
    if ($manifest.$key -cne $expected[$key]) { throw "Core manifest $key mismatch: $($manifest.$key)" }
  }
  $pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
  $initdb = Join-Path $pgRoot 'bin/initdb.exe'
  $pgCtl = Join-Path $pgRoot 'bin/pg_ctl.exe'
  $psql = Join-Path $pgRoot 'bin/psql.exe'
  foreach ($path in @($pgConfig,$initdb,$pgCtl,$psql)) { if (-not (Test-Path $path)) { throw "Core executable missing: $path" } }
  if ((& $pgConfig --version) -cne "PostgreSQL $pgVersion") { throw 'PostgreSQL version mismatch' }

$sourcePackage = Join-Path $SourcePackageDirectory $sourcePackageName
  if (-not (Test-Path $sourcePackage -PathType Leaf)) { throw "Missing passed pgTAP source package: $sourcePackageName" }
  $actualSourcePackageHash = (Get-FileHash $sourcePackage -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualSourcePackageHash -ne $sourcePackageSha256) { throw "Passed pgTAP archive checksum mismatch: $actualSourcePackageHash" }
  $sourceSidecar = Join-Path $SourcePackageDirectory "$sourcePackageName.sha256"
  if (((Get-Content $sourceSidecar -Raw) -split '\s+')[0].ToLowerInvariant() -ne $sourcePackageSha256) { throw 'pgTAP archive checksum sidecar mismatch' }
  tar.exe -xzf $sourcePackage -C $sourceUnpacked
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract passed pgTAP source package' }
  $sourceMeta = Get-Content (Join-Path $sourceUnpacked 'metadata.json') -Raw | ConvertFrom-Json
  if ($sourceMeta.project -cne 'pgtap' -or $sourceMeta.version -cne $version -or $sourceMeta.sql_names.Count -ne 1 -or $sourceMeta.sql_names[0] -cne 'pgtap') { throw 'Passed pgTAP package identity mismatch' }
  if ($sourceMeta.source.url -cne $sourceUrl -or $sourceMeta.source.sha256 -cne $sourceSha256) { throw 'Passed package does not identify the pinned upstream source archive' }
  if ($sourceMeta.platform -cne 'macos' -or $sourceMeta.architecture -cne 'arm64' -or $sourceMeta.postgresql_version -cne $pgVersion) { throw 'Unexpected source package build platform identity' }
  $payload = Join-Path $sourceUnpacked 'pgtap'
  if (-not (Test-Path (Join-Path $payload 'share/extension/pgtap.control') -PathType Leaf)) { throw 'Passed pgTAP control file missing' }
  $extensionDir = Join-Path $payload 'share/extension'
  foreach ($name in @('pgtap--1.3.4.sql','pgtap-core--1.3.4.sql','pgtap-schema--1.3.4.sql','pgtap--1.3.3--1.3.4.sql')) {
    if (-not (Test-Path (Join-Path $extensionDir $name) -PathType Leaf)) { throw "Passed generated SQL file missing: $name" }
  }
  if (-not (Test-Path (Join-Path $payload 'share/doc/extension/pgtap.mmd') -PathType Leaf)) { throw 'Passed pgTAP documentation missing' }
  if (-not (Test-Path (Join-Path $payload 'LICENSES/pgTAP.txt') -PathType Leaf) -or -not (Test-Path (Join-Path $payload 'LICENSES/pgtap-inventory.json') -PathType Leaf)) { throw 'Passed pgTAP licence payload missing' }
  if (@(Get-ChildItem $payload -Recurse -File | Where-Object { $_.Extension -in @('.dll','.so','.dylib','.exe') }).Count) { throw 'SQL-only pgTAP payload unexpectedly contains native code' }
  $stagedPayload = Join-Path $stage 'pgtap'
  New-Item -ItemType Directory -Force $stagedPayload | Out-Null
  Copy-Item (Join-Path $payload '*') $stagedPayload -Recurse
  $metadata = @{
    project = 'pgtap'; version = $version; sql_names = @('pgtap'); requires = @()
    configuration_prerequisites = @(@{ type = 'sql_extension'; name = 'plpgsql'; value = 'CREATE EXTENSION plpgsql' })
    runtime_prerequisites = @(); postgresql_version = $pgVersion; platform = 'windows'; architecture = $architecture
    source = @{ url = $sourceUrl; sha256 = $sourceSha256 }
    core_archive = @{ basename = $coreName; sha256 = $coreSha256 }
  }
  $metadata | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $stage 'metadata.json')

  $controlFiles = @(Get-ChildItem $extensionDir -Filter '*.control' -File)
  if ($controlFiles.Count -ne 1 -or $controlFiles[0].Name -cne 'pgtap.control') { throw 'Package must expose only the pgtap extension identity' }
  if (@(Get-ChildItem $payload -Recurse -File | Where-Object { $_.Extension -in @('.dll','.so','.dylib','.exe') }).Count) { throw 'SQL-only pgTAP payload unexpectedly contains native code' }
  $packagePath = Join-Path $OutputDirectory $archiveName
  tar.exe -czf $packagePath -C $stage pgtap metadata.json
  if ($LASTEXITCODE -ne 0) { throw 'Could not create pgTAP archive' }
  $packageHash = (Get-FileHash $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
  "$packageHash  $archiveName" | Set-Content -Encoding ascii ("$packagePath.sha256")
  tar.exe -xzf $packagePath -C $packageUnpacked
  if ($LASTEXITCODE -ne 0) { throw 'Could not reopen pgTAP package archive' }
  $packagedMetadata = Get-Content (Join-Path $packageUnpacked 'metadata.json') -Raw | ConvertFrom-Json
  if ($packagedMetadata.project -cne 'pgtap' -or $packagedMetadata.version -cne $version -or $packagedMetadata.source.sha256 -cne $sourceSha256 -or $packagedMetadata.core_archive.sha256 -cne $coreSha256) { throw 'Packaged metadata failed identity checks' }

  $extensionPayload = Join-Path $packageUnpacked 'pgtap'
  foreach ($file in Get-ChildItem $extensionPayload -Recurse -File) {
    $relative = $file.FullName.Substring($extensionPayload.Length).TrimStart('\','/')
    $destination = Join-Path $pgRoot $relative
    if (Test-Path $destination) { throw "pgTAP payload collision: $relative" }
  }
  Move-Item $pgRoot (Join-Path $moved 'postgresql')
  $pgRoot = Join-Path $moved 'postgresql'
  foreach ($file in Get-ChildItem $extensionPayload -Recurse -File) {
    $relative = $file.FullName.Substring($extensionPayload.Length).TrimStart('\','/')
    $destination = Join-Path $pgRoot $relative
    New-Item -ItemType Directory -Force (Split-Path $destination -Parent) | Out-Null
    Copy-Item $file.FullName $destination
  }
  $pgCtl = Join-Path $pgRoot 'bin/pg_ctl.exe'
  $initdb = Join-Path $pgRoot 'bin/initdb.exe'
  $psql = Join-Path $pgRoot 'bin/psql.exe'
  $env:PATH = "$(Join-Path $pgRoot 'bin');$env:SystemRoot\System32;$env:SystemRoot"
  & $initdb -D $data -U postgres -A trust --encoding=UTF8 --locale=C --no-instructions
  if ($LASTEXITCODE -ne 0) { throw 'initdb failed for relocated PostgreSQL' }
  & $pgCtl -D $data -l (Join-Path $work 'server.log') -o '-p 55432 -h 127.0.0.1' -w start
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL failed to start after relocation' }
  $serverStarted = $true
  $probeOutput = Join-Path $OutputDirectory 'probe-output.txt'
  & $psql -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -c 'CREATE EXTENSION IF NOT EXISTS plpgsql' | Tee-Object -FilePath (Join-Path $OutputDirectory 'prerequisite-output.txt')
  if ($LASTEXITCODE -ne 0) { throw 'Could not create pgTAP configuration prerequisite plpgsql' }
  & $psql -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -f (Join-Path $repo 'scripts/pgtap/probe.sql') 2>&1 | Tee-Object -FilePath $probeOutput
  if ($LASTEXITCODE -ne 0) { throw 'pgTAP SQL assertions failed' }
  if (-not (Select-String -Path $probeOutput -SimpleMatch '1..4' -Quiet)) { throw 'pgTAP plan output missing' }
  $okCount = @(Select-String -Path $probeOutput -Pattern '^ok [1-4]( -|$)').Count
  if ($okCount -ne 4) { throw "Expected four passing pgTAP assertions; found $okCount" }
  & $psql -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -c "SELECT extname FROM pg_extension WHERE extname IN ('pgtap','plpgsql') ORDER BY extname; SELECT count(*) FROM pg_depend d JOIN pg_extension e ON e.oid=d.refobjid WHERE e.extname='pgtap' AND d.deptype='e';" | Tee-Object -FilePath (Join-Path $OutputDirectory 'extension-closure.txt')
  if ($LASTEXITCODE -ne 0) { throw 'Could not inspect installed extension dependency closure' }
  $closure = Get-Content (Join-Path $OutputDirectory 'extension-closure.txt')
  if (-not ($closure -contains 'pgtap') -or -not ($closure | Where-Object { $_ -match '^[1-9][0-9]*$' })) { throw 'Installed pgTAP extension or its owned-object closure is missing' }
  & $pgCtl -D $data -m fast -w stop
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not stop cleanly' }
  $serverStarted = $false
  Write-Output "PASS: pgTAP $version source package installed and exercised with relocated PostgreSQL $pgVersion on Windows x86-64"
} finally {
  if ($serverStarted) { & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m immediate stop 2>$null | Out-Null }
  $env:PATH = $originalPath
  Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}
