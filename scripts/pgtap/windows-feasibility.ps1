param(
  [Parameter(Mandatory = $true)][string]$CoreArchiveDirectory,
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
$sourceUrl = 'https://github.com/theory/pgtap/archive/refs/tags/v1.3.4.tar.gz'
$sourceSha256 = 'd2c951afb296a001d21785611a8e966e3f8fa3f5bfbd929396a5130c0152f314'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$coreArchiveDirectory = (Resolve-Path $CoreArchiveDirectory).Path
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
$sourceArchive = Join-Path $work 'pgtap-1.3.4.tar.gz'
$pgxsShim = Join-Path $work 'pgxs-empty.mk'
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

  & curl.exe -fL --retry 3 -o $sourceArchive $sourceUrl
  if ($LASTEXITCODE -ne 0) { throw 'Could not download pinned pgTAP source archive' }
  $actualSourceHash = (Get-FileHash $sourceArchive -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualSourceHash -ne $sourceSha256) { throw "Pinned pgTAP source checksum mismatch: $actualSourceHash" }
  tar.exe -xzf $sourceArchive -C $sourceUnpacked
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract pinned pgTAP source archive' }
  $sourceRoot = Join-Path $sourceUnpacked "pgtap-$version"
  if (-not (Test-Path (Join-Path $sourceRoot 'Makefile') -PathType Leaf)) { throw 'Pinned source archive has an unexpected root layout' }
  if ((Get-Content (Join-Path $sourceRoot 'pgtap.control') -Raw) -notmatch "(?m)^default_version\s*=\s*'$version'$" ) { throw 'Upstream pgTAP control version mismatch' }

  $msysBash = 'C:\msys64\usr\bin\bash.exe'
  $msysCygpath = 'C:\msys64\usr\bin\cygpath.exe'
  if (-not (Test-Path $msysBash -PathType Leaf) -or -not (Test-Path $msysCygpath -PathType Leaf)) { throw 'Windows runner MSYS2 tools are unavailable' }
  [IO.File]::WriteAllText($pgxsShim, "`n", [Text.UTF8Encoding]::new($false))
  $sourcePosix = (& $msysCygpath -u $sourceRoot).Trim()
  $shimPosix = (& $msysCygpath -u $pgxsShim).Trim()
  $pgConfigPosix = (& $msysCygpath -u $pgConfig).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $sourcePosix -or -not $shimPosix -or -not $pgConfigPosix) { throw 'Could not map pgTAP generation paths into MSYS2' }
  $env:MSYS2_PATH_TYPE = 'inherit'
  & $msysBash -lc 'pacman -S --needed --noconfirm make patch grep sed gawk'
  if ($LASTEXITCODE -ne 0) { throw 'Could not provide GNU make and SQL-generation tools on the disposable runner' }
  & $msysBash -lc "cd '$sourcePosix' && make all PG_CONFIG='$pgConfigPosix' PGXS='$shimPosix' OSNAME=windows"
  if ($LASTEXITCODE -ne 0) { throw 'Upstream pgTAP SQL generation failed' }

  $payload = Join-Path $stage 'pgtap'
  $extensionDir = Join-Path $payload 'share/extension'
  $documentationDir = Join-Path $payload 'share/doc/extension'
  $licenseDir = Join-Path $payload 'LICENSES'
  New-Item -ItemType Directory -Force $extensionDir,$documentationDir,$licenseDir | Out-Null
  Copy-Item (Join-Path $sourceRoot 'pgtap.control') $extensionDir
  $baseSql = @('pgtap.sql','pgtap-core.sql','pgtap-schema.sql','uninstall_pgtap.sql',
    'pgtap--1.3.4.sql','pgtap-core--1.3.4.sql','pgtap-schema--1.3.4.sql')
  $installSql = @(Get-ChildItem (Join-Path $sourceRoot 'sql') -File -Filter '*.sql' |
    Where-Object { $_.Name -like '*--*.sql' -or $_.Name -in $baseSql })
  if (-not $installSql.Count) { throw 'Upstream pgTAP SQL generation produced no install files' }
  $expectedSqlNames = @(
    'pgtap--0.90.0--0.91.0.sql','pgtap--0.91.0--0.92.0.sql','pgtap--0.92.0--0.93.0.sql',
    'pgtap--0.93.0--0.94.0.sql','pgtap--0.94.0--0.95.0.sql','pgtap--0.95.0--0.96.0.sql',
    'pgtap--0.96.0--0.97.0.sql','pgtap--0.97.0--0.98.0.sql','pgtap--0.98.0--0.99.0.sql',
    'pgtap--0.99.0--1.0.0.sql','pgtap--1.0.0--1.1.0.sql','pgtap--1.1.0--1.2.0.sql',
    'pgtap--1.2.0--1.3.0.sql','pgtap--1.3.0--1.3.1.sql','pgtap--1.3.1--1.3.2.sql',
    'pgtap--1.3.2--1.3.3.sql','pgtap--1.3.3--1.3.4.sql','pgtap--1.3.4.sql',
    'pgtap--unpackaged--0.91.0.sql','pgtap-core--1.3.4.sql','pgtap-core.sql',
    'pgtap-schema--1.3.4.sql','pgtap-schema.sql','pgtap.sql','uninstall_pgtap.sql'
  )
  $actualSqlNames = @($installSql | ForEach-Object { $_.Name } | Sort-Object)
  $expectedSqlNames = @($expectedSqlNames | Sort-Object)
  if (Compare-Object $expectedSqlNames $actualSqlNames) { throw 'Upstream pgTAP SQL install file set differs from the passing payload' }
  Copy-Item $installSql.FullName $extensionDir
  Copy-Item (Join-Path $sourceRoot 'doc/pgtap.mmd') $documentationDir
  $licenseText = Get-Content (Join-Path $sourceRoot 'README.md') -Raw
  $licenseMatch = [regex]::Match($licenseText, '(?m)^Copyright and License\r?\n[^\r\n]*\r?\n')
  if (-not $licenseMatch.Success) { throw 'Could not extract the upstream pgTAP redistribution notice' }
  $licenseText = $licenseText.Substring($licenseMatch.Index + $licenseMatch.Length) -replace "`r`n", "`n"
  [IO.File]::WriteAllText((Join-Path $licenseDir 'pgTAP.txt'), $licenseText, [Text.UTF8Encoding]::new($false))
  if (-not (Select-String -Path (Join-Path $licenseDir 'pgTAP.txt') -SimpleMatch 'Copyright (c) 2008-2025 David E. Wheeler. Some rights reserved.' -Quiet)) { throw 'Upstream pgTAP redistribution notice is unexpected' }
  $inventory = @'
{
  "schema_version": 1,
  "components": [{
    "component": "pgtap", "version": "1.3.4",
    "payload_paths": ["share/extension", "share/doc/extension"],
    "license_file": "pgTAP.txt",
    "license_source": "https://github.com/theory/pgtap/tree/v1.3.4",
    "redistribution_review": {
      "status": "resolved",
      "basis": "The pgTAP v1.3.4 source distribution applies the included permissive copyright notice to the project files and generated SQL and documentation payload. The notice permits redistribution with its attribution and disclaimer retained.",
      "source_obligation": "none"
    }
  }]
}
'@
  $inventory = $inventory -replace "`r`n", "`n"
  [IO.File]::WriteAllText((Join-Path $licenseDir 'pgtap-inventory.json'), $inventory, [Text.UTF8Encoding]::new($false))

  # The two main install scripts embed os_name(); their Windows-specific text is checked below.
  $knownPayloadHashes = @{
    'share/doc/extension/pgtap.mmd' = '5385c92afec570063687bf710a68b6cb8a9afa64fe73552406518fbd49109a9d'
    'share/extension/pgtap.control' = 'b073089908333a1522c925ca9968cebb04d9fa0b1f99e932bda635ffaecdca55'
    'share/extension/pgtap--0.90.0--0.91.0.sql' = 'd7059b8aa56ca0fdc8cb420ab2e8fe4de6bdbafc59267ee75fe2c7ba9017edb1'
    'share/extension/pgtap--0.91.0--0.92.0.sql' = 'f30a22e4713c2c85f3950b7c88ab205707539c82826fa144d5b5537327d2229c'
    'share/extension/pgtap--0.92.0--0.93.0.sql' = '109077aa07701914cc76c1155eafdd6137a2a44cf7df0e2fad7bef5e7c701b0b'
    'share/extension/pgtap--0.93.0--0.94.0.sql' = '47fdaa53f1483d1bb1550051acd85ad1daaf140433a6eb3dfdbfb4cbd090dab6'
    'share/extension/pgtap--0.94.0--0.95.0.sql' = '4db21faaba46babcd90ca61df413dc35030888b188fdd22d2fa7ae32a0c2eee2'
    'share/extension/pgtap--0.95.0--0.96.0.sql' = 'd3ffb0f71447e46d7c0669390115b7919875b54761300a067585a085346c12e1'
  }
  $knownPayloadHashes['share/extension/pgtap--0.96.0--0.97.0.sql'] = '68a1b15159c75615f26d4f3b5cda22a104cd5aeb05d66e158767aad11b436153'
  $knownPayloadHashes['share/extension/pgtap--0.97.0--0.98.0.sql'] = 'b7d0fb5784d8bc866ea2e6abad2d5c9178b353eff42fd98c6687b35cb954ce6'
  $knownPayloadHashes['share/extension/pgtap--0.98.0--0.99.0.sql'] = '14b307769e0d932db20859d23c36148ada3639df3cf03e19fc38e3edcd268100'
  $knownPayloadHashes['share/extension/pgtap--0.99.0--1.0.0.sql'] = '54a2d55f6fe046af7836aa0ce110b46fd818834650c1f788d5fb5f12f2abbf50'
  $knownPayloadHashes['share/extension/pgtap--1.0.0--1.1.0.sql'] = 'bd86f1cda33574fc287ef05114968456f7ef28b5bfe1a874e93bcc118b734fb0'
  $knownPayloadHashes['share/extension/pgtap--1.1.0--1.2.0.sql'] = '847fe2fb52c38947c8c2231c26c793643e9327f518499a9a97b564356dcc915e'
  $knownPayloadHashes['share/extension/pgtap--1.2.0--1.3.0.sql'] = '552ee1cf56f50c7254d71b245d56c5b0c4f388a4ef46ff53a44084dd1116dc2b'
  $knownPayloadHashes['share/extension/pgtap--1.3.0--1.3.1.sql'] = '296ed8441e9b2cece84b3b825450ba8c9aa0683745464963dbc2538f51df078c'
  $knownPayloadHashes['share/extension/pgtap--1.3.1--1.3.2.sql'] = '4a0a8c5641eb1e41319ca44aa59000550ff5d67bab8d8f28db9553553becdc0e'
  $knownPayloadHashes['share/extension/pgtap--1.3.2--1.3.3.sql'] = '21f3ae58ae773b68a1a1d7bd81d183cbcb0308ddd3881dd00b430ce8b14f0316'
  $knownPayloadHashes['share/extension/pgtap--1.3.3--1.3.4.sql'] = 'a4380c7e22ce67eb69aaefeb4afd642cf7e8176afaafb61c678d8a6ae8b32635'
  $knownPayloadHashes['share/extension/pgtap-core.sql'] = 'b28437925b37a1adcebe03a080c39391a76e634302aff7307bebb65c29ce27fd'
  $knownPayloadHashes['share/extension/pgtap-core--1.3.4.sql'] = 'b28437925b37a1adcebe03a080c39391a76e634302aff7307bebb65c29ce27fd'
  $knownPayloadHashes['share/extension/pgtap-schema.sql'] = 'c4fb7daf5b6d69e5a5db261ddfae5c68563cfafac767f9b403cea783d74f6fca'
  $knownPayloadHashes['share/extension/pgtap-schema--1.3.4.sql'] = 'c4fb7daf5b6d69e5a5db261ddfae5c68563cfafac767f9b403cea783d74f6fca'
  $knownPayloadHashes['share/extension/pgtap--unpackaged--0.91.0.sql'] = '5fa57e41b46b37ecff55c17214beb159fe2250a1ececd58f3f54c4746e06e36a'
  $knownPayloadHashes['share/extension/uninstall_pgtap.sql'] = 'c824e2e4e65f7d7021be0f169dc95e45b992c2a46528f927e7734d2b3a806650'
  $knownPayloadHashes['LICENSES/pgTAP.txt'] = '2aa8da4a27c1cf4003064dbc5d3096700f38f84b3193137de4f662bf4b80b0e6'
  $knownPayloadHashes['LICENSES/pgtap-inventory.json'] = 'ae338745180c70d51f209fcc24f2c79c12cff49e66d5074f88180680b554ccb6'
  foreach ($relative in $knownPayloadHashes.Keys) {
    $path = Join-Path $payload ($relative -replace '/', '\')
    if (-not (Test-Path $path -PathType Leaf)) { throw "Generated pgTAP source file missing: $relative" }
    $actual = (Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $knownPayloadHashes[$relative]) { throw "Generated pgTAP source file differs from passing source payload: $relative ($actual)" }
  }
  foreach ($name in @('pgtap.sql','pgtap--1.3.4.sql')) {
    $generatedMain = Get-Content (Join-Path $extensionDir $name) -Raw
    if ($generatedMain -notmatch "RETURNS TEXT AS 'SELECT ''windows''::text;'" -or $generatedMain.Contains('darwin')) {
      throw "Generated $name does not identify the Windows build target"
    }
  }
  if (@(Get-ChildItem $payload -Recurse -File | Where-Object { $_.Extension -in @('.dll','.so','.dylib','.exe') }).Count) { throw 'SQL-only pgTAP payload unexpectedly contains native code' }

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
  $packagePath = Join-Path $OutputDirectory $archiveName
  tar.exe -czf $packagePath -C $stage pgtap metadata.json
  if ($LASTEXITCODE -ne 0) { throw 'Could not create pgTAP archive' }
  $packageHash = (Get-FileHash $packagePath -Algorithm SHA256).Hash.ToLowerInvariant()
  [IO.File]::WriteAllText("$packagePath.sha256", "$packageHash  $archiveName`n", [Text.UTF8Encoding]::new($false))
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
