param(
  [Parameter(Mandatory = $true)][string]$SourceArchive,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [Parameter(Mandatory = $true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$SourceSha256,
  [Parameter(Mandatory = $true)][string]$MinGWPGConfig,
  [ValidatePattern('^(16|17|18)\.[0-9]+$')][string]$PostgreSQLVersion = '18.6',
  [string]$SourceUrl = 'https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/postgis_tiger_geocoder-2025.2.tar.gz'
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Set-StrictMode -Version Latest

if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
  throw 'This recipe requires Windows x86-64.'
}
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = (Get-Command python.exe -ErrorAction Stop).Source
$tar = (Get-Command tar.exe -ErrorAction Stop).Source
$sourceArchive = (Resolve-Path $SourceArchive).Path
$MinGWPGConfig = (Resolve-Path $MinGWPGConfig).Path
$pgVersion = $PostgreSQLVersion
$version = '2025.2'
$sourceSha = (Get-FileHash $sourceArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($sourceSha -cne $SourceSha256.ToLowerInvariant()) { throw 'Source archive SHA-256 does not match the supplied source identity.' }
$pgConfigVersion = (& $MinGWPGConfig --version).Trim()
if ($LASTEXITCODE -ne 0 -or $pgConfigVersion -cne "PostgreSQL $pgVersion") {
  throw "MinGW pg_config must identify PostgreSQL $pgVersion; got '$pgConfigVersion'."
}
$msysBash = 'C:\msys64\usr\bin\bash.exe'
$msysCygpath = 'C:\msys64\usr\bin\cygpath.exe'
if (-not (Test-Path $msysBash -PathType Leaf) -or -not (Test-Path $msysCygpath -PathType Leaf)) {
  throw 'MSYS2 bash and cygpath are required to generate the upstream SQL scripts.'
}
$sourceMembers = @(& $tar -tzf $sourceArchive)
if ($LASTEXITCODE -ne 0 -or -not ($sourceMembers | Where-Object { $_ -ceq 'postgis_tiger_geocoder/postgis_tiger_geocoder.control' })) {
  throw 'Source archive does not contain the expected TIGER Geocoder 2025.2 root and control file.'
}

$work = Join-Path $env:RUNNER_TEMP ("tiger-windows-build-" + [guid]::NewGuid().ToString('N'))
$sourceRoot = Join-Path $work 'source'
$stage = Join-Path $work 'stage/postgis_tiger_geocoder'
$package = Join-Path $work 'package'
$extensionDirectory = Join-Path $stage 'share/extension'
New-Item -ItemType Directory -Force $sourceRoot,$extensionDirectory,$package | Out-Null
try {
  & $tar -xzf $sourceArchive -C $sourceRoot
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the TIGER Geocoder source archive.' }
  $source = Join-Path $sourceRoot 'postgis_tiger_geocoder'
  $control = Join-Path $source 'postgis_tiger_geocoder.control'
  if ((Get-Content $control -Raw) -notmatch "(?m)^default_version\s*=\s*'$([regex]::Escape($version))'\s*$") {
    throw 'Upstream control file does not identify TIGER Geocoder 2025.2.'
  }
  $sourcePosix = (& $msysCygpath -u $source).Trim()
  $pgConfigPosix = (& $msysCygpath -u $MinGWPGConfig).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $sourcePosix -or -not $pgConfigPosix) {
    throw 'Could not map the source and matching MinGW pg_config paths into MSYS2.'
  }
  $env:MSYS2_PATH_TYPE = 'inherit'
  & $msysBash -lc 'pacman -S --needed --noconfirm make'
  if ($LASTEXITCODE -ne 0) { throw 'Could not provide GNU make in the disposable MSYS2 environment.' }
  & $msysBash -lc "cd '$sourcePosix' && make PG_CONFIG='$pgConfigPosix' all"
  if ($LASTEXITCODE -ne 0) { throw 'Upstream TIGER Geocoder SQL generation failed.' }
  Copy-Item $control $extensionDirectory
  $sqlFiles = @(Get-ChildItem (Join-Path $source 'data') -File -Filter 'postgis_tiger_geocoder*.sql')
  if (-not ($sqlFiles | Where-Object { $_.Name -ceq "postgis_tiger_geocoder--$version.sql" })) {
    throw 'Upstream source does not contain the expected TIGER Geocoder install script.'
  }
  Copy-Item $sqlFiles.FullName $extensionDirectory

  & $python (Join-Path $repo 'tools/license_pointer.py') write $stage postgis_tiger_geocoder
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the TIGER Geocoder licence pointer.' }
  $metadata = [ordered]@{
    project = 'postgis_tiger_geocoder'; version = $version
    sql_names = @('postgis_tiger_geocoder'); requires = @('PostGIS')
    configuration_prerequisites = @(
      [ordered]@{ type='postgresql_setting'; name='search_path'; value='"$user",public,tiger' },
      [ordered]@{ type='sql_extension'; name='fuzzystrmatch'; value='CREATE EXTENSION fuzzystrmatch' }
    )
    runtime_prerequisites = @(); postgresql_version = $pgVersion
    platform = 'windows'; architecture = 'x86_64'
    source = [ordered]@{ url=$SourceUrl; sha256=$sourceSha }
  }
  $metadata | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $package 'metadata.json')
  Move-Item $stage (Join-Path $package 'postgis_tiger_geocoder')
  New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
  $archiveName = "postgis_tiger_geocoder-$version-postgresql-$pgVersion-windows-x86_64.tar.gz"
  $archive = Join-Path (Resolve-Path $OutputDirectory).Path $archiveName
  & $tar -czf $archive -C $package postgis_tiger_geocoder metadata.json
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the Windows TIGER Geocoder archive.' }
  & $python (Join-Path $repo 'tools/license_pointer.py') verify $archive postgis_tiger_geocoder
  if ($LASTEXITCODE -ne 0) { throw 'TIGER Geocoder archive licence pointer verification failed.' }
  $archiveSha = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
  "$archiveSha  $archiveName" | Set-Content -Encoding ascii "$archive.sha256"
} finally {
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
