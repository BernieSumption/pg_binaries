param(
  [Parameter(Mandatory = $true)][string]$CoreArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [ValidateSet('15.19','16.15','17.11','18.6')][string]$PostgreSQLVersion = '18.6',
  [string]$CoreIdentityPath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$pgVersion = $PostgreSQLVersion
if ($CoreIdentityPath) {
  $coreIdentity = Get-Content $CoreIdentityPath -Raw | ConvertFrom-Json
} else {
  $pinPath = Join-Path $PSScriptRoot "../../support/windows-core-pins/$pgVersion-x86_64.json"
  $coreIdentity = (& python (Join-Path $PSScriptRoot '../../tools/windows_core_pin.py') --postgresql-version $pgVersion --path $pinPath | ConvertFrom-Json)
  if ($LASTEXITCODE -ne 0 -or -not $coreIdentity) { throw 'Cannot load the pinned Windows PostgreSQL core identity' }
}
if ($coreIdentity.postgresql_version -cne $pgVersion -or $coreIdentity.platform -cne 'windows-x86_64') { throw 'Core identity does not match the selected Windows PostgreSQL target' }
$pgMajor = $pgVersion.Split('.')[0]
$pgFeature = "pg$pgMajor"
$extensionVersion = '0.3.4'
$extensionCommit = 'cbe74b570d38aa0c4d42914e7a118bcb3adaee7a'
$cargoLockSha256 = 'ab865dc25d9eea4bf7dbfaf8fae13283e5c0bce4bca460fe10464c6716e67028'
$coreSha256 = $coreIdentity.sha256
$coreName = $coreIdentity.archive_name
$coreBuildId = $coreIdentity.build_id
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
$CoreArchiveDirectory = (Resolve-Path $CoreArchiveDirectory).Path
$work = Join-Path $env:RUNNER_TEMP ("pg-jsonschema-windows-" + [guid]::NewGuid().ToString('N'))
$first = Join-Path $work 'first'
$moved = Join-Path $work 'moved'
$source = Join-Path $work 'source'
$data = Join-Path $work 'data'
$serverStarted = $false
$originalPath = $env:PATH
$python = (Get-Command python -ErrorAction Stop).Source
$transcript = Join-Path $OutputDirectory 'windows-build.log'
Start-Transcript -Path $transcript -Force | Out-Null

try {
  if ($env:RUNNER_OS -ne 'Windows' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'This feasibility probe requires Windows x86-64.'
  }
  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
  if (-not (Test-Path $vswhere -PathType Leaf)) { throw 'Visual Studio vswhere.exe is missing from the Windows runner' }
  $vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $vsRoot) { throw 'The Windows runner has no x64 MSVC toolchain installation' }
  $vcvars = Join-Path $vsRoot 'VC/Auxiliary/Build/vcvars64.bat'
  if (-not (Test-Path $vcvars -PathType Leaf)) { throw 'The x64 MSVC vcvars64.bat script is missing' }
  $environmentScript = Join-Path $work 'load-msvc-environment.cmd'
  New-Item -ItemType Directory -Force $work | Out-Null
  @('@echo off', "call `"$vcvars`" >nul", 'if errorlevel 1 exit /b %errorlevel%', 'set') |
    Set-Content -Encoding ascii $environmentScript
  $environmentOutput = & $env:ComSpec /d /c $environmentScript
  if ($LASTEXITCODE -ne 0) { throw 'Could not load the x64 MSVC developer environment' }
  foreach ($line in $environmentOutput) {
    if ($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') }
  }
  foreach ($command in @('cl.exe','link.exe')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "MSVC prerequisite is unavailable after vcvars64: $command" }
  }
  $coreArchive = Join-Path $CoreArchiveDirectory $coreName
  if (-not (Test-Path $coreArchive -PathType Leaf)) { throw "Pinned core archive is missing: $coreName" }
  $actualCoreSha256 = (Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualCoreSha256 -ne $coreSha256) { throw "Pinned core archive checksum mismatch: $actualCoreSha256" }
  $sidecar = Join-Path $CoreArchiveDirectory "$coreName.sha256"
  if (-not (Test-Path $sidecar -PathType Leaf)) { throw 'Pinned core checksum sidecar is missing' }
  $sidecarSha256 = ((Get-Content $sidecar -Raw) -split '\s+')[0].ToLowerInvariant()
  if ($sidecarSha256 -ne $coreSha256) { throw 'Pinned core checksum sidecar does not match the archive' }

  $llvmCandidates = @(
    $env:LIBCLANG_PATH,
    $env:LLVM_PATH,
    'C:\Program Files\LLVM\bin',
    'C:\Program Files (x86)\LLVM\bin',
    'C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Tools\Llvm\x64\bin',
    'C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Tools\Llvm\x64\bin'
  ) | Where-Object { $_ -and (Test-Path (Join-Path $_ 'libclang.dll') -PathType Leaf) }
  if (-not $llvmCandidates) {
    throw 'libclang.dll was not found in the standard Windows runner LLVM locations required by pgrx bindgen.'
  }
  $env:LIBCLANG_PATH = $llvmCandidates[0]
  $env:PGRX_HOME = Join-Path $work 'pgrx'

  New-Item -ItemType Directory -Force $first,$source | Out-Null
  & tar.exe -xzf $coreArchive -C $first
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the pinned PostgreSQL core archive' }
  $pgRoot = Join-Path $first 'postgresql'
  if (-not (Test-Path (Join-Path $pgRoot 'manifest.json') -PathType Leaf)) { throw 'PostgreSQL core manifest is missing' }
  $manifest = Get-Content (Join-Path $pgRoot 'manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.component -cne 'postgresql' -or $manifest.version -cne $pgVersion -or
      $manifest.platform -cne 'windows' -or $manifest.architecture -cne $coreIdentity.architecture -or
      $manifest.build_id -cne $coreBuildId -or $manifest.source_revision -cne $coreIdentity.source_revision) {
    throw "The downloaded PostgreSQL archive manifest does not match the selected Windows $pgVersion core build."
  }
  $pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
  foreach ($exe in @($pgConfig,(Join-Path $pgRoot 'bin/initdb.exe'),(Join-Path $pgRoot 'bin/pg_ctl.exe'),(Join-Path $pgRoot 'bin/psql.exe'))) {
    if (-not (Test-Path $exe -PathType Leaf)) { throw "PostgreSQL executable is missing: $exe" }
  }
  if ((& $pgConfig --version) -cne "PostgreSQL $pgVersion") { throw 'The core pg_config reports an unexpected PostgreSQL version' }

  & git -C $source init -q
  if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the pg_jsonschema source checkout' }
  & git -C $source config core.autocrlf false
  if ($LASTEXITCODE -ne 0) { throw 'Could not preserve upstream source line endings' }
  & git -C $source remote add origin https://github.com/supabase/pg_jsonschema.git
  if ($LASTEXITCODE -ne 0) { throw 'Could not configure the pg_jsonschema upstream remote' }
  & git -C $source fetch --depth 1 origin $extensionCommit
  if ($LASTEXITCODE -ne 0) { throw 'Could not fetch the pinned pg_jsonschema source commit' }
  & git -C $source checkout --detach FETCH_HEAD
  if ($LASTEXITCODE -ne 0) { throw 'Could not check out the pinned pg_jsonschema source commit' }
  $actualCommit = (& git -C $source rev-parse HEAD).Trim()
  if ($actualCommit -cne $extensionCommit) { throw "Unexpected pg_jsonschema source commit: $actualCommit" }
  $cargoManifest = Get-Content (Join-Path $source 'Cargo.toml') -Raw
  if ($cargoManifest -notmatch '(?m)^version = "0\.3\.4"\r?$') { throw 'Cargo.toml version does not match pg_jsonschema 0.3.4' }
  if ($cargoManifest -notmatch '(?m)^edition = "2024"\r?$') { throw 'Cargo.toml edition differs from the reviewed pinned source' }
  $featurePattern = '(?m)^' + [regex]::Escape($pgFeature) + ' = \["pgrx/' + [regex]::Escape($pgFeature) + '", "pgrx-tests/' + [regex]::Escape($pgFeature) + '"\]\r?$'
  if ($cargoManifest -notmatch $featurePattern) { throw "The source has no expected PostgreSQL $pgMajor feature" }
  $cargoLock = Join-Path $source 'Cargo.lock'
  if (-not (Test-Path $cargoLock -PathType Leaf)) { throw 'Cargo.lock is missing from the pinned source' }
  $actualLockSha256 = (Get-FileHash $cargoLock -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualLockSha256 -ne $cargoLockSha256) { throw "Cargo.lock checksum mismatch: $actualLockSha256" }

  $rustcVersion = (& rustc --version).Trim()
  if ($LASTEXITCODE -ne 0) { throw 'rustc is unavailable' }
  $cargoVersion = (& cargo --version).Trim()
  if ($LASTEXITCODE -ne 0) { throw 'cargo is unavailable' }
  $clVersion = (Get-Command cl.exe).Source
  @(
    'pg_jsonschema_source_url=https://github.com/supabase/pg_jsonschema.git'
    "pg_jsonschema_source_commit=$actualCommit"
    "cargo_lock_sha256=$actualLockSha256"
    "postgresql_core_sha256=$actualCoreSha256"
    "postgresql_build_id=$($manifest.build_id)"
    "libclang_path=$env:LIBCLANG_PATH"
    $rustcVersion
    $cargoVersion
    "msvc_compiler_path=$clVersion"
    "windows_version=$([Environment]::OSVersion.Version)"
    "runner_image=$([Environment]::GetEnvironmentVariable('ImageOS'))/$([Environment]::GetEnvironmentVariable('ImageVersion'))"
    (& $pgConfig --version).Trim()
  ) | Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'build-identity.txt')

  & cargo install cargo-pgrx --version 0.16.1 --locked
  if ($LASTEXITCODE -ne 0) { throw 'Could not install cargo-pgrx 0.16.1' }
  & cargo pgrx init "--$pgFeature" $pgConfig
  if ($LASTEXITCODE -ne 0) { throw 'cargo pgrx init could not register the pinned PostgreSQL core' }
  Push-Location $source
  try {
    & cargo pgrx install --release --no-default-features --features $pgFeature --pg-config $pgConfig
    if ($LASTEXITCODE -ne 0) { throw 'cargo pgrx install failed for pg_jsonschema 0.3.4' }
  } finally {
    Pop-Location
  }
  $postBuildLockSha256 = (Get-FileHash $cargoLock -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($postBuildLockSha256 -ne $cargoLockSha256) { throw 'Cargo.lock changed during the build' }
  & git -C $source diff --exit-code --quiet
  if ($LASTEXITCODE -ne 0) { throw 'The build modified tracked upstream source files' }

  $libDir = (& $pgConfig --pkglibdir).Trim()
  $extensionDir = (& $pgConfig --sharedir).Trim() + '\extension'
  $dll = Join-Path $libDir 'pg_jsonschema.dll'
  $control = Join-Path $extensionDir 'pg_jsonschema.control'
  if (-not (Test-Path $dll -PathType Leaf)) { throw 'pgrx did not install pg_jsonschema.dll' }
  if (-not (Test-Path $control -PathType Leaf)) { throw 'pgrx did not install pg_jsonschema.control' }
  $stage = Join-Path $work 'package'
  $payload = Join-Path $stage 'pg_jsonschema'
  $licenseDir = Join-Path $payload 'LICENSES'
  New-Item -ItemType Directory -Force (Join-Path $payload 'lib'),(Join-Path $payload 'share/extension'),
    (Join-Path $licenseDir 'pg_jsonschema'),(Join-Path $licenseDir 'cargo') | Out-Null
  Copy-Item $dll (Join-Path $payload 'lib/pg_jsonschema.dll')
  Copy-Item $control (Join-Path $payload 'share/extension/pg_jsonschema.control')
  Get-ChildItem $extensionDir -Filter 'pg_jsonschema*.sql' -File | Copy-Item -Destination (Join-Path $payload 'share/extension')
  $upstreamLicense = Join-Path $source 'LICENSE'
  if (-not (Test-Path $upstreamLicense -PathType Leaf)) { throw 'Pinned pg_jsonschema source LICENSE is missing' }
  Copy-Item $upstreamLicense (Join-Path $licenseDir 'pg_jsonschema/LICENSE')
  $cargoMetadata = Join-Path $work 'cargo-metadata.json'
  & cargo metadata --manifest-path (Join-Path $source 'Cargo.toml') --locked --format-version 1 --filter-platform x86_64-pc-windows-msvc --no-default-features --features $pgFeature | Set-Content -Encoding utf8 $cargoMetadata
  if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the locked Windows Cargo package inventory' }
  $cargoInventory = Join-Path $licenseDir 'cargo/cargo-license-inventory.json'
  python (Join-Path $repo 'tools/inventory_cargo_licenses.py') $source $cargoMetadata $cargoInventory --package-root $payload --supplements (Join-Path $repo 'support/evidence/pg-jsonschema-crate-licenses-2026-10-18')
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the project-named Cargo licence inventory' }
  python (Join-Path $repo 'tools/create_pg_jsonschema_component_inventory.py') $payload $extensionVersion windows pg_jsonschema.dll
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the resolved pg_jsonschema component inventory' }
  $archiveName = "pg_jsonschema-$extensionVersion-postgresql-$pgVersion-windows-x86_64.tar.gz"
  $extensionArchive = Join-Path $OutputDirectory $archiveName
  $metadata = @{
    project = 'pg_jsonschema'; version = $extensionVersion; sql_names = @('pg_jsonschema'); requires = @()
    postgresql_version = $pgVersion; platform = 'windows'; architecture = 'x86_64'
    source = @{ url = 'https://github.com/supabase/pg_jsonschema.git'; commit = $actualCommit; cargo_lock_sha256 = $cargoLockSha256 }
    core_archive = @{ basename = $coreName; sha256 = $coreSha256 }
    release_eligible = $false; core_status = $coreIdentity.status
  }
  $metadata | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $stage 'metadata.json')
  & tar.exe -czf $extensionArchive -C $stage pg_jsonschema metadata.json
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the pg_jsonschema extension archive' }
  python (Join-Path $repo 'tools/inventory_cargo_licenses.py') --check-archive $extensionArchive --archive-inventory pg_jsonschema/LICENSES/cargo/cargo-license-inventory.json
  if ($LASTEXITCODE -ne 0) { throw 'Final archive Cargo notices failed verification' }
  python (Join-Path $repo 'tools/check_pg_jsonschema_component_inventory.py') $extensionArchive
  if ($LASTEXITCODE -ne 0) { throw 'Final archive component redistribution inventory failed verification' }
  $extensionHash = (Get-FileHash $extensionArchive -Algorithm SHA256).Hash.ToLowerInvariant()
  [IO.File]::WriteAllText("$extensionArchive.sha256", "$extensionHash  $archiveName`n", [Text.UTF8Encoding]::new($false))

  Move-Item $pgRoot $moved
  $pgRoot = $moved
  Remove-Item (Join-Path $pgRoot 'lib/pg_jsonschema.dll') -Force
  Remove-Item (Join-Path $pgRoot 'share/extension/pg_jsonschema*') -Force
  $unpacked = Join-Path $work 'unpacked-extension'
  New-Item -ItemType Directory -Force $unpacked | Out-Null
  & tar.exe -xzf $extensionArchive -C $unpacked
  if ($LASTEXITCODE -ne 0) { throw 'Could not unpack the final extension archive' }
  foreach ($file in Get-ChildItem (Join-Path $unpacked 'pg_jsonschema') -Recurse -File) {
    $relative = $file.FullName.Substring((Join-Path $unpacked 'pg_jsonschema').Length).TrimStart('\','/')
    $destination = Join-Path $pgRoot $relative
    New-Item -ItemType Directory -Force (Split-Path $destination -Parent) | Out-Null
    Copy-Item $file.FullName $destination
  }
  $env:PATH = "$(Join-Path $pgRoot 'bin');$env:SystemRoot\System32;$env:SystemRoot"
  $initdb = Join-Path $pgRoot 'bin/initdb.exe'
  $pgCtl = Join-Path $pgRoot 'bin/pg_ctl.exe'
  $psql = Join-Path $pgRoot 'bin/psql.exe'
  & $initdb -D $data -U postgres -A trust --encoding=UTF8 --locale=C --no-instructions
  if ($LASTEXITCODE -ne 0) { throw 'initdb failed on the relocated PostgreSQL installation' }
  $serverLog = Join-Path $OutputDirectory 'server.log'
  & $pgCtl -D $data -l $serverLog -o '-p 55432 -h 127.0.0.1' -w start
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL failed to start after relocation' }
  $serverStarted = $true
  $probeOutput = Join-Path $OutputDirectory 'probe-output.txt'
  & $psql -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -f (Join-Path $repo 'scripts/pg_jsonschema/probe.sql') 2>&1 | Tee-Object -FilePath $probeOutput
  if ($LASTEXITCODE -ne 0) { throw 'The relocated Windows pg_jsonschema SQL probe failed' }
  if (-not (Select-String -Path $probeOutput -SimpleMatch 'pg_jsonschema' -Quiet)) { throw 'The SQL probe did not report the installed extension' }
  $dumpbin = Join-Path (Split-Path $clVersion -Parent) 'dumpbin.exe'
  if (-not (Test-Path $dumpbin -PathType Leaf)) { throw 'Visual Studio dumpbin.exe was not found beside cl.exe' }
  & $python (Join-Path $repo 'tools/check_pe_dependencies.py') $pgRoot --dumpbin $dumpbin --archive $coreArchive --archive $extensionArchive --report (Join-Path $OutputDirectory 'pe-dependency-analysis.json')
  if ($LASTEXITCODE -ne 0) { throw 'PE dependency closure check failed on the relocated archive installation' }
  & $pgCtl -D $data -m fast -w stop
  if ($LASTEXITCODE -ne 0) { throw 'Relocated PostgreSQL did not stop cleanly' }
  $serverStarted = $false
  'result=passed' | Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'result.txt')
  Write-Output "PASS: pg_jsonschema $extensionVersion source built and exercised with relocated PostgreSQL $pgVersion on Windows x86-64"
} catch {
  $_ | Out-String | Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'failure.txt')
  throw
} finally {
  if ($serverStarted) { & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m immediate stop 2>$null | Out-Null }
  $env:PATH = $originalPath
  Stop-Transcript | Out-Null
}
