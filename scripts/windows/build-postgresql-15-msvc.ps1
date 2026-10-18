param(
  [Parameter(Mandatory = $true)][string]$SourceRoot,
  [Parameter(Mandatory = $true)][string]$InstallRoot,
  [Parameter(Mandatory = $true)][string]$VcpkgRoot,
  [Parameter(Mandatory = $true)][string]$StagingRoot
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$source = (Resolve-Path $SourceRoot).Path
$msvcTools = Join-Path $source 'src/tools/msvc'
$configPath = Join-Path $msvcTools 'config.pl'
foreach ($required in @('config_default.pl', 'build.pl', 'install.pl')) {
  if (-not (Test-Path (Join-Path $msvcTools $required))) { throw "PostgreSQL 15 MSVC tool is missing: $required" }
}
$perlPath = (Get-Command perl -ErrorAction SilentlyContinue).Source
if ($perlPath -and $perlPath -notmatch '(?i)Strawberry') { $perlPath = $null }
if (-not $perlPath -and (Test-Path 'C:/Strawberry/perl/bin/perl.exe')) { $perlPath = 'C:/Strawberry/perl/bin/perl.exe' }
if (-not $perlPath) { throw 'PostgreSQL 15 MSVC builds require Strawberry Perl on PATH' }

$prepareTool = Join-Path $PSScriptRoot 'prepare_postgresql_15_msvc.py'
python $prepareTool --vcpkg-root $VcpkgRoot --staging-root $StagingRoot --config $configPath
if ($LASTEXITCODE -ne 0) { throw 'Cannot stage the vcpkg dependencies for PostgreSQL 15 MSVC' }
try {
  Push-Location $msvcTools
  try {
    & $perlPath (Join-Path $msvcTools 'build.pl')
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL 15 MSVC build failed with exit code $LASTEXITCODE" }
    & $perlPath (Join-Path $msvcTools 'install.pl') $InstallRoot
    if ($LASTEXITCODE -ne 0) { throw "PostgreSQL 15 MSVC install failed with exit code $LASTEXITCODE" }
  } finally {
    Pop-Location
  }
} finally {
  Remove-Item $configPath -Force -ErrorAction SilentlyContinue
}
