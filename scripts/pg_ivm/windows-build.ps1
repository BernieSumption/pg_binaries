param(
  [Parameter(Mandatory = $true)][string]$CoreArchive,
  [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$CoreSha256,
  [Parameter(Mandatory = $true)][string]$SourceArchive,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [ValidateSet('15.19','16.15','17.11','18.6')][string]$PostgreSQLVersion = '18.6'
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Set-StrictMode -Version Latest

if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) { throw 'This recipe requires Windows x86-64.' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = (Get-Command python.exe -ErrorAction Stop).Source
$tar = (Get-Command tar.exe -ErrorAction Stop).Source
$coreArchive = (Resolve-Path $CoreArchive).Path
$sourceArchive = (Resolve-Path $SourceArchive).Path
$pgVersion = $PostgreSQLVersion
$version = '1.16'
$sourceUrl = 'https://github.com/sraoss/pg_ivm/archive/refs/tags/v1.16.tar.gz'
$sourceShaExpected = '87807d6af1974fce591715d55f75d939dffea33ea6908b413e62d3dd79b9c583'
$coreName = "postgresql-$pgVersion-windows-x86_64.tar.gz"
if ((Split-Path $coreArchive -Leaf) -cne $coreName) { throw "Core archive must be named $coreName" }
$sidecar = (Get-Content "$coreArchive.sha256" -Raw).Trim() -split '\s+'
$coreSha = (Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($sidecar.Count -lt 2 -or $sidecar[-1] -cne $coreName -or $sidecar[0].ToLowerInvariant() -cne $coreSha) { throw 'Selected PostgreSQL core SHA-256 sidecar is invalid.' }
$pinnedSha = (& $python (Join-Path $repo 'tools/windows_core_pin.py') --postgresql-version $pgVersion --field sha256).Trim()
if ($LASTEXITCODE -ne 0 -or $pinnedSha -cne $CoreSha256.ToLowerInvariant() -or $coreSha -cne $pinnedSha) { throw 'Core archive does not match the checked PostgreSQL Windows identity.' }
if ((Get-FileHash $sourceArchive -Algorithm SHA256).Hash.ToLowerInvariant() -cne $sourceShaExpected) { throw 'Source archive does not match pg_ivm 1.16.' }
$work = Join-Path $env:RUNNER_TEMP ("pgivm-windows-build-" + [guid]::NewGuid().ToString('N'))
$coreRoot = Join-Path $work 'core'
$sourceRoot = Join-Path $work 'source'
$stage = Join-Path $work 'stage/pg_ivm'
$package = Join-Path $work 'package'
New-Item -ItemType Directory -Force $coreRoot,$sourceRoot,(Join-Path $stage 'lib'),(Join-Path $stage 'share/extension'),$package | Out-Null
try {
  & $tar -xzf $coreArchive -C $coreRoot
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the selected PostgreSQL core archive.' }
  $pgRoot = Join-Path $coreRoot 'postgresql'
  $manifest = Get-Content (Join-Path $pgRoot 'manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.component -cne 'postgresql' -or $manifest.version -cne $pgVersion -or $manifest.platform -cne 'windows' -or $manifest.architecture -cne 'x86_64') { throw 'Core manifest does not match the selected Windows target.' }
  $pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
  if ((& $pgConfig --version) -cne "PostgreSQL $pgVersion") { throw 'Core pg_config identity is invalid.' }
  foreach ($required in @('include/server/postgres.h','lib/postgres.lib')) { if (-not (Test-Path (Join-Path $pgRoot $required) -PathType Leaf)) { throw "Core archive lacks $required" } }
  $sourceMembers = @(& $tar -tzf $sourceArchive)
  if ($LASTEXITCODE -ne 0 -or -not ($sourceMembers | Where-Object { $_ -ceq "pg_ivm-$version/meson.build" })) { throw 'Upstream source archive lacks its Meson build definition.' }
  & $tar -xzf $sourceArchive -C $sourceRoot
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the selected pg_ivm source archive.' }
  $source = Join-Path $sourceRoot "pg_ivm-$version"
  if ((Get-Content (Join-Path $source 'pg_ivm.control') -Raw) -notmatch "(?m)^default_version\s*=\s*'1\.16'\s*$") { throw 'Source extension control version mismatch.' }
  if ((Get-Content (Join-Path $source 'pg_ivm.control') -Raw) -notmatch '(?m)^schema\s*=\s*pg_catalog\s*$') { throw 'Source extension schema mismatch.' }
  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
  if (-not (Test-Path $vswhere -PathType Leaf)) { throw 'Visual Studio vswhere.exe is missing from the Windows runner.' }
  $vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $vsRoot) { throw 'The Windows runner has no x64 MSVC toolchain installation.' }
  $vcvars = Join-Path $vsRoot 'VC/Auxiliary/Build/vcvars64.bat'
  if (-not (Test-Path $vcvars -PathType Leaf)) { throw 'The x64 MSVC vcvars64.bat script is missing.' }
  $environmentScript = Join-Path $work 'load-msvc-environment.cmd'
  @('@echo off', "call `"$vcvars`" >nul", 'if errorlevel 1 exit /b %errorlevel%', 'set') | Set-Content -Encoding ascii $environmentScript
  $environmentOutput = & $env:ComSpec /d /c $environmentScript
  if ($LASTEXITCODE -ne 0) { throw 'Could not load the x64 MSVC developer environment.' }
  foreach ($line in $environmentOutput) { if ($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') } }
  foreach ($command in @('cl.exe','link.exe')) { if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "MSVC prerequisite is unavailable after vcvars64: $command" } }
  $env:PATH = "$(Join-Path $pgRoot 'bin');$(Join-Path $pgRoot 'lib/pgxs/src/test/regress');$env:PATH"
  $env:CC = 'cl'
  python -m pip install --disable-pip-version-check meson ninja
  if ($LASTEXITCODE -ne 0) { throw 'Could not install Meson and Ninja on the disposable runner.' }
  $build = Join-Path $work 'build'
  $moduleDefinition = Join-Path $repo 'scripts/pg_ivm/windows-exports.def'
  Push-Location $source
  try {
    meson setup $build --prefix=$pgRoot --libdir=lib -Dbuildtype=release
    if ($LASTEXITCODE -ne 0) { throw 'Upstream Meson configuration failed.' }
    meson configure $build "-Dc_link_args=/DEF:$moduleDefinition"
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure the PostgreSQL module export list.' }
    meson compile -C $build
    if ($LASTEXITCODE -ne 0) { throw 'Upstream pg_ivm compilation failed.' }
    meson install -C $build
    if ($LASTEXITCODE -ne 0) { throw 'Upstream Meson installation failed.' }
  } finally { Pop-Location }
  if (-not (Test-Path (Join-Path $pgRoot 'lib/pg_ivm.dll') -PathType Leaf)) { throw 'Meson did not install pg_ivm.dll.' }
  Copy-Item (Join-Path $pgRoot 'lib/pg_ivm.dll') (Join-Path $stage 'lib/pg_ivm.dll')
  Copy-Item (Join-Path $pgRoot 'share/extension/pg_ivm*') (Join-Path $stage 'share/extension')
  & $python (Join-Path $repo 'tools/license_pointer.py') write $stage pg_ivm
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the pg_ivm licence pointer.' }
  $metadata = [ordered]@{ project='pg_ivm'; version=$version; sql_names=@('pg_ivm'); requires=@(); configuration_prerequisites=@([ordered]@{ type='postgresql_setting'; name='shared_preload_libraries'; value='pg_ivm' }); runtime_prerequisites=@(); postgresql_version=$pgVersion; platform='windows'; architecture='x86_64'; source=[ordered]@{ url=$sourceUrl; sha256=$sourceShaExpected }; core_archive=[ordered]@{ basename=$coreName; sha256=$coreSha } }
  $metadata | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $package 'metadata.json')
  Move-Item $stage (Join-Path $package 'pg_ivm')
  $name = "pg_ivm-$version-postgresql-$pgVersion-windows-x86_64.tar.gz"
  $archive = Join-Path $OutputDirectory $name
  New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
  & $tar -czf $archive -C $package pg_ivm metadata.json
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the pg_ivm Windows archive.' }
  & $python (Join-Path $repo 'tools/license_pointer.py') verify $archive pg_ivm
  if ($LASTEXITCODE -ne 0) { throw 'pg_ivm archive licence pointer verification failed.' }
  $hash = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $name" | Set-Content -Encoding ascii "$archive.sha256"
} finally { Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue }
