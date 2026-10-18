param(
  [Parameter(Mandatory = $true)][string]$CoreArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$pgVersion = '18.6'
$extensionVersion = '0.3.4'
$extensionCommit = 'cbe74b570d38aa0c4d42914e7a118bcb3adaee7a'
$cargoLockSha256 = 'ab865dc25d9eea4bf7dbfaf8fae13283e5c0bce4bca460fe10464c6716e67028'
$coreSha256 = '2e48881e4b5c3289bc9526ee846685d62f6cfa4fff2539cb6393f36f605fcceb'
$coreName = "postgresql-$pgVersion-windows-x86_64.tar.gz"
$coreBuildId = 'github-39077749917-1'
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
      $manifest.platform -cne 'windows' -or $manifest.architecture -cne 'x86_64' -or
      $manifest.build_id -cne $coreBuildId) {
    throw 'The downloaded PostgreSQL archive manifest does not match the pinned Windows 18.6 build.'
  }
  $pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
  foreach ($exe in @($pgConfig,(Join-Path $pgRoot 'bin/initdb.exe'),(Join-Path $pgRoot 'bin/pg_ctl.exe'),(Join-Path $pgRoot 'bin/psql.exe'))) {
    if (-not (Test-Path $exe -PathType Leaf)) { throw "PostgreSQL executable is missing: $exe" }
  }
  if ((& $pgConfig --version) -cne "PostgreSQL $pgVersion") { throw 'The core pg_config reports an unexpected PostgreSQL version' }

  & git -C $source init -q
  if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the pg_jsonschema source checkout' }
  & git -C $source remote add origin https://github.com/supabase/pg_jsonschema.git
  if ($LASTEXITCODE -ne 0) { throw 'Could not configure the pg_jsonschema upstream remote' }
  & git -C $source fetch --depth 1 origin $extensionCommit
  if ($LASTEXITCODE -ne 0) { throw 'Could not fetch the pinned pg_jsonschema source commit' }
  & git -C $source checkout --detach FETCH_HEAD
  if ($LASTEXITCODE -ne 0) { throw 'Could not check out the pinned pg_jsonschema source commit' }
  $actualCommit = (& git -C $source rev-parse HEAD).Trim()
  if ($actualCommit -cne $extensionCommit) { throw "Unexpected pg_jsonschema source commit: $actualCommit" }
  $cargoManifest = Get-Content (Join-Path $source 'Cargo.toml') -Raw
  if ($cargoManifest -notmatch '(?m)^version = "0\.3\.4"$') { throw 'Cargo.toml version does not match pg_jsonschema 0.3.4' }
  if ($cargoManifest -notmatch '(?m)^edition = "2024"$') { throw 'Cargo.toml edition differs from the reviewed pinned source' }
  if ($cargoManifest -notmatch '(?m)^pg18 = \["pgrx/pg18", "pgrx-tests/pg18"\]$') { throw 'The source has no expected PostgreSQL 18 feature' }
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
  & cargo pgrx init --pg18 $pgConfig
  if ($LASTEXITCODE -ne 0) { throw 'cargo pgrx init could not register the pinned PostgreSQL core' }
  Push-Location $source
  try {
    & cargo pgrx install --release --no-default-features --features pg18 --pg-config $pgConfig
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
  Copy-Item $dll (Join-Path $OutputDirectory 'pg_jsonschema.dll') -Force
  Copy-Item $control (Join-Path $OutputDirectory 'pg_jsonschema.control') -Force
  Get-ChildItem $extensionDir -Filter 'pg_jsonschema*.sql' -File | Copy-Item -Destination $OutputDirectory -Force

  Move-Item $pgRoot $moved
  $pgRoot = $moved
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
