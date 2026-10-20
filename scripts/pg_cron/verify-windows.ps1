param(
  [Parameter(Mandatory = $true)][string]$CoreArchive,
  [Parameter(Mandatory = $true)][string]$ExtensionArchive,
  [string]$ReportPath,
  [string]$ProbePath
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Set-StrictMode -Version Latest

if ($env:RUNNER_OS -ne 'Windows' -or -not [Environment]::Is64BitOperatingSystem) {
  throw 'This verifier requires a Windows x86-64 runner.'
}
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = (Get-Command python.exe -ErrorAction Stop).Source
$CoreArchive = (Resolve-Path $CoreArchive).Path
$ExtensionArchive = (Resolve-Path $ExtensionArchive).Path

$pgVersion = '18.6'
$version = '1.6.8'
$architecture = 'x86_64'
$coreIdentity = (& $python (Join-Path $repo 'tools/windows_core_pin.py') --postgresql-version $pgVersion | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0 -or -not $coreIdentity) { throw 'Cannot load the pinned PostgreSQL 18.6 Windows core identity.' }
$coreName = $coreIdentity.archive_name
$extensionName = "pg_cron-$version-postgresql-$pgVersion-windows-$architecture.tar.gz"
$coreArchive = $CoreArchive
$extensionArchive = $ExtensionArchive
if ([IO.Path]::GetFileName($coreArchive) -cne $coreName -or [IO.Path]::GetFileName($extensionArchive) -cne $extensionName) {
  throw 'Archive filenames do not match PostgreSQL 18.6 and pg_cron 1.6.8 Windows identities.'
}
foreach ($archive in @($coreArchive, $extensionArchive)) {
  if (-not (Test-Path $archive -PathType Leaf) -or -not (Test-Path "$archive.sha256" -PathType Leaf)) {
    throw "Required archive or SHA-256 sidecar is missing: $([IO.Path]::GetFileName($archive))"
  }
  $sidecar = (Get-Content "$archive.sha256" -Raw).Trim() -split '\s+'
  if ($sidecar.Count -lt 2 -or $sidecar[-1] -cne [IO.Path]::GetFileName($archive) -or
      $sidecar[0] -notmatch '^[0-9a-fA-F]{64}$') { throw "Invalid SHA-256 sidecar: $([IO.Path]::GetFileName($archive))" }
  $actual = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -cne $sidecar[0].ToLowerInvariant()) { throw "SHA-256 sidecar mismatch: $([IO.Path]::GetFileName($archive))" }
}
$coreHash = (Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($coreHash -cne $coreIdentity.sha256) { throw 'Core archive differs from the pinned PostgreSQL 18.6 artifact.' }

$work = Join-Path $env:RUNNER_TEMP ("pgcron-windows-verify-" + [guid]::NewGuid().ToString('N'))
$first = Join-Path $work 'first'
$moved = Join-Path $work 'moved'
$package = Join-Path $work 'extension-package'
$data = Join-Path $work 'data'
New-Item -ItemType Directory -Force $first,$moved,$package | Out-Null
if (-not $ReportPath) { $ReportPath = Join-Path $env:RUNNER_TEMP ("pgcron-pe-dependencies-$([guid]::NewGuid().ToString('N')).json") }
$reportParent = Split-Path $ReportPath -Parent
if ($reportParent) { New-Item -ItemType Directory -Force $reportParent | Out-Null }
$serverStarted = $false
$originalPath = $env:PATH
$pgRoot = $null
try {
  foreach ($archive in @($coreArchive, $extensionArchive)) {
    $members = @(& tar.exe -tzf $archive)
    if ($LASTEXITCODE -ne 0 -or $members.Count -eq 0) { throw "Could not inspect archive: $([IO.Path]::GetFileName($archive))" }
    if (@($members | Select-Object -Unique).Count -ne $members.Count) { throw 'Archive contains duplicate paths.' }
    foreach ($member in $members) {
      if ($member.StartsWith('/') -or $member -match '(^|/)\.\.(/|$)' -or $member.Contains('\')) {
        throw "Archive contains an unsafe path: $member"
      }
      $root = ($member.TrimEnd('/') -split '/', 2)[0]
      if (($archive -eq $coreArchive -and $root -cne 'postgresql') -or
          ($archive -eq $extensionArchive -and $root -cnotin @('pg_cron','metadata.json'))) {
        throw "Archive contains an unexpected top-level path: $member"
      }
    }
  }
  & tar.exe -xzf $coreArchive -C $first
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the PostgreSQL core archive.' }
  & tar.exe -xzf $extensionArchive -C $package
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the pg_cron archive.' }
  $pgRoot = Join-Path $first 'postgresql'
  $extensionRoot = Join-Path $package 'pg_cron'
  $manifest = Get-Content (Join-Path $pgRoot 'manifest.json') -Raw | ConvertFrom-Json
  foreach ($key in @('component','version','postgresql_version','platform','architecture','build_id','source_revision')) {
    $expected = @{ component='postgresql'; version=$pgVersion; postgresql_version=$pgVersion; platform='windows'; architecture=$architecture; build_id=$coreIdentity.build_id; source_revision=$coreIdentity.source_revision }[$key]
    if ($manifest.$key -cne $expected) { throw "Core manifest $key does not match the checked archive identity." }
  }
  $metadata = Get-Content (Join-Path $package 'metadata.json') -Raw | ConvertFrom-Json
  if ($metadata.project -cne 'pg_cron' -or $metadata.version -cne $version -or
      $metadata.postgresql_version -cne $pgVersion -or $metadata.platform -cne 'windows' -or
      $metadata.architecture -cne $architecture -or $metadata.core_archive.basename -cne $coreName -or
      $metadata.core_archive.sha256 -cne $coreHash -or
      $metadata.source.url -cne 'https://github.com/citusdata/pg_cron/archive/refs/tags/v1.6.8.tar.gz' -or
      $metadata.source.sha256 -cne 'c19ab9bb35406c60fb51ecda993737c083850abe424acb6c1030439d00a1f8e4' -or
      $metadata.configuration_prerequisites.Count -ne 2 -or
      $metadata.configuration_prerequisites[0].name -cne 'shared_preload_libraries' -or
      $metadata.configuration_prerequisites[0].value -cne 'pg_cron' -or
      $metadata.configuration_prerequisites[1].name -cne 'cron.use_background_workers' -or
      $metadata.configuration_prerequisites[1].value -cne 'on') {
    throw 'pg_cron metadata does not bind the checked source, core archive, and prerequisites.'
  }
  foreach ($required in @('lib/pg_cron.dll','share/extension/pg_cron.control','share/extension/pg_cron--1.0.sql',
      'share/extension/pg_cron--1.5--1.6.sql','LICENSES/pg_cron.txt')) {
    if (-not (Test-Path (Join-Path $extensionRoot $required) -PathType Leaf)) { throw "pg_cron archive lacks $required" }
  }
  foreach ($file in Get-ChildItem $extensionRoot -Recurse -File) {
    $relative = $file.FullName.Substring($extensionRoot.Length).TrimStart('\','/')
    if (Test-Path (Join-Path $pgRoot $relative)) { throw "pg_cron payload collision: $relative" }
  }
  Move-Item $pgRoot (Join-Path $moved 'postgresql')
  $pgRoot = Join-Path $moved 'postgresql'
  foreach ($file in Get-ChildItem $extensionRoot -Recurse -File) {
    $relative = $file.FullName.Substring($extensionRoot.Length).TrimStart('\','/')
    $destination = Join-Path $pgRoot $relative
    New-Item -ItemType Directory -Force (Split-Path $destination -Parent) | Out-Null
    Copy-Item $file.FullName $destination
  }

  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
  $dumpbin = Get-Command dumpbin.exe -ErrorAction SilentlyContinue
  if (-not $dumpbin -and (Test-Path $vswhere)) {
    $dumpbinPath = $null
    $vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
    if ($vsRoot) { $dumpbinPath = Get-ChildItem (Join-Path $vsRoot 'VC/Tools/MSVC/*/bin/Hostx64/x64/dumpbin.exe') | Sort-Object FullName -Descending | Select-Object -First 1 }
    if ($dumpbinPath) { $dumpbin = @{ Source = $dumpbinPath.FullName } }
  }
  if (-not $dumpbin) { throw 'dumpbin.exe is unavailable for Windows dependency inspection.' }
  & $python (Join-Path $repo 'tools/check_pe_dependencies.py') $pgRoot --dumpbin $dumpbin.Source --archive $coreArchive --archive $extensionArchive --report $ReportPath
  if ($LASTEXITCODE -ne 0) { throw 'Windows PE dependency analysis failed.' }

  $bin = Join-Path $pgRoot 'bin'
  $env:PATH = "$bin;$env:SystemRoot\System32;$env:SystemRoot"
  $env:PGHOST = '127.0.0.1'; $env:PGUSER = 'postgres'; $env:PGDATABASE = 'postgres'; $env:PGSSLMODE = 'disable'
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  $listener.Start(); $env:PGPORT = [string]$listener.LocalEndpoint.Port; $listener.Stop()
  & (Join-Path $bin 'initdb.exe') -D $data -U postgres -A trust --encoding=UTF8 --no-instructions
  if ($LASTEXITCODE -ne 0) { throw 'initdb failed for relocated PostgreSQL.' }
  $pgCtl = Join-Path $bin 'pg_ctl.exe'
  & $pgCtl -D $data -l (Join-Path $work 'postgresql.log') -o "-h 127.0.0.1 -p $env:PGPORT -c shared_preload_libraries=pg_cron -c cron.use_background_workers=on -c cron.database_name=postgres -c max_worker_processes=20" -w start
  if ($LASTEXITCODE -ne 0) { Get-Content (Join-Path $work 'postgresql.log') -ErrorAction SilentlyContinue | Write-Host; throw 'PostgreSQL failed to start with pg_cron preloaded.' }
  $serverStarted = $true
  $psql = Join-Path $bin 'psql.exe'
  $output = Join-Path $work 'probe-output.txt'
  & $psql -X -A -t -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION pg_cron; CREATE TABLE public.pg_cron_probe (ran_at timestamptz NOT NULL); SELECT cron.schedule(''windows-probe'', ''* * * * *'', ''INSERT INTO public.pg_cron_probe VALUES (clock_timestamp())'');' 2>&1 | Tee-Object -FilePath $output
  if ($LASTEXITCODE -ne 0) { throw 'Could not install pg_cron or schedule the background-worker probe.' }
  'installation_relocated=true' | Add-Content $output
  $jobId = (& $psql -X -A -t -v ON_ERROR_STOP=1 -d postgres -c "SELECT jobid FROM cron.job WHERE jobname = 'windows-probe'" 2>&1 | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { throw "Could not query the pg_cron probe job: $jobId" }
  if ($jobId -notmatch '^\d+$') { throw 'pg_cron did not register the scheduled probe.' }
  $deadline = [DateTime]::UtcNow.AddSeconds(150)
  $status = ''
  while ([DateTime]::UtcNow -lt $deadline) {
    $status = (& $psql -X -A -t -v ON_ERROR_STOP=1 -d postgres -c "SELECT status FROM cron.job_run_details WHERE jobid = $jobId ORDER BY runid DESC LIMIT 1" 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "Could not query the pg_cron run status: $status" }
    if ($status -eq 'succeeded') { break }
    Start-Sleep -Seconds 2
  }
  if ($status -cne 'succeeded') { Get-Content (Join-Path $work 'postgresql.log') | Write-Host; throw 'Scheduled pg_cron background-worker job did not succeed within 150 seconds.' }
  $rows = (& $psql -X -A -t -v ON_ERROR_STOP=1 -d postgres -c 'SELECT count(*) FROM public.pg_cron_probe' 2>&1 | Out-String).Trim()
  if ($LASTEXITCODE -ne 0) { throw "Could not query the pg_cron probe rows: $rows" }
  if ($rows -notmatch '^\d+$' -or [int]$rows -lt 1) { throw 'Scheduled background-worker job did not insert its probe row.' }
  "job_status=$status`njob_rows=$rows" | Add-Content $output
  & $psql -X -v ON_ERROR_STOP=1 -c "SELECT cron.unschedule($jobId)" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Could not remove the pg_cron probe job.' }
  if ($ProbePath) {
    $probeParent = Split-Path $ProbePath -Parent
    if ($probeParent) { New-Item -ItemType Directory -Force $probeParent | Out-Null }
    Copy-Item $output $ProbePath -Force
  }
  & $pgCtl -D $data -m fast -w stop
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not stop cleanly.' }
  $serverStarted = $false
  Write-Output "PASS: pg_cron $version archive installed and executed a background-worker job with relocated PostgreSQL $pgVersion on Windows x86-64."
} finally {
  if ($serverStarted -and $pgRoot) { & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m immediate stop 2>$null | Out-Null }
  $env:PATH = $originalPath
  Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
}
