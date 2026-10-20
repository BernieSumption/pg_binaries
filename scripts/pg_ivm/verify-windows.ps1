param(
  [Parameter(Mandatory = $true)][string]$CoreArchive,
  [Parameter(Mandatory = $true)][string]$ExtensionArchive,
  [ValidateSet('15.19','16.15','17.11','18.6')][string]$PostgreSQLVersion = '18.6',
  [string]$ReportPath
)
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
Set-StrictMode -Version Latest
if ($env:RUNNER_OS -ne 'Windows' -or -not [Environment]::Is64BitOperatingSystem) { throw 'This verifier requires a Windows x86-64 runner.' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = (Get-Command python.exe -ErrorAction Stop).Source
$CoreArchive = (Resolve-Path $CoreArchive).Path
$ExtensionArchive = (Resolve-Path $ExtensionArchive).Path
$pgVersion = $PostgreSQLVersion
$version = '1.16'
$architecture = 'x86_64'
$coreName = "postgresql-$pgVersion-windows-x86_64.tar.gz"
$extensionName = "pg_ivm-$version-postgresql-$pgVersion-windows-x86_64.tar.gz"
foreach ($archive in @($CoreArchive,$ExtensionArchive)) {
  if ((Split-Path $archive -Leaf) -cnotin @($coreName,$extensionName)) { throw 'Archive filename does not match the selected target.' }
  $sidecar = (Get-Content "$archive.sha256" -Raw).Trim() -split '\s+'
  if ($sidecar.Count -lt 2 -or $sidecar[-1] -cne (Split-Path $archive -Leaf) -or $sidecar[0] -notmatch '^[0-9a-fA-F]{64}$' -or (Get-FileHash $archive -Algorithm SHA256).Hash -cne $sidecar[0]) { throw "Invalid archive checksum: $(Split-Path $archive -Leaf)" }
}
$identity = (& $python (Join-Path $repo 'tools/windows_core_pin.py') --postgresql-version $pgVersion | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0 -or (Get-FileHash $CoreArchive -Algorithm SHA256).Hash.ToLowerInvariant() -cne $identity.sha256) { throw 'Core archive does not match the pinned Windows PostgreSQL target.' }
$work = Join-Path $env:RUNNER_TEMP ("pgivm-windows-verify-" + [guid]::NewGuid().ToString('N'))
$first = Join-Path $work 'first'
$package = Join-Path $work 'package'
$data = Join-Path $work 'data'
New-Item -ItemType Directory -Force $first,$package,$data | Out-Null
if (-not $ReportPath) { $ReportPath = Join-Path $work 'static-analysis.json' }
$serverStarted = $false
$oldPath = $env:PATH
try {
  foreach ($archive in @($CoreArchive,$ExtensionArchive)) {
    $members = @(& tar.exe -tzf $archive)
    if ($LASTEXITCODE -ne 0 -or $members.Count -eq 0 -or @($members | Select-Object -Unique).Count -ne $members.Count) { throw 'Archive listing failed or contains duplicate paths.' }
    foreach ($member in $members) {
      if ($member.StartsWith('/') -or $member -match '(^|/)\.\.(/|$)' -or $member.Contains('\')) { throw "Unsafe archive path: $member" }
    }
  }
  & tar.exe -xzf $CoreArchive -C $first
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract PostgreSQL core archive.' }
  & tar.exe -xzf $ExtensionArchive -C $package
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract pg_ivm archive.' }
  $pgRoot = Join-Path $first 'postgresql'
  $extensionRoot = Join-Path $package 'pg_ivm'
  $manifest = Get-Content (Join-Path $pgRoot 'manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.component -cne 'postgresql' -or $manifest.version -cne $pgVersion -or $manifest.platform -cne 'windows' -or $manifest.architecture -cne $architecture) { throw 'Core manifest does not match the selected target.' }
  $metadata = Get-Content (Join-Path $package 'metadata.json') -Raw | ConvertFrom-Json
  $coreHash = (Get-FileHash $CoreArchive -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($metadata.project -cne 'pg_ivm' -or $metadata.version -cne $version -or $metadata.postgresql_version -cne $pgVersion -or $metadata.platform -cne 'windows' -or $metadata.architecture -cne $architecture -or $metadata.core_archive.basename -cne $coreName -or $metadata.core_archive.sha256 -cne $coreHash -or $metadata.source.sha256 -cne '87807d6af1974fce591715d55f75d939dffea33ea6908b413e62d3dd79b9c583') { throw 'Extension metadata does not bind the selected source and core archives.' }
  foreach ($required in @('lib/pg_ivm.dll','share/extension/pg_ivm.control','share/extension/pg_ivm--1.0.sql','LICENSES/pg_ivm.txt','LICENSES/pg_ivm-inventory.json')) { if (-not (Test-Path (Join-Path $extensionRoot $required) -PathType Leaf)) { throw "pg_ivm archive lacks $required" } }
  foreach ($file in Get-ChildItem $extensionRoot -Recurse -File) {
    $relative = $file.FullName.Substring($extensionRoot.Length).TrimStart('\','/')
    if (Test-Path (Join-Path $pgRoot $relative)) { throw "pg_ivm payload collision: $relative" }
  }
  Move-Item $pgRoot (Join-Path $work 'relocated-postgresql')
  $pgRoot = Join-Path $work 'relocated-postgresql'
  foreach ($file in Get-ChildItem $extensionRoot -Recurse -File) {
    $relative = $file.FullName.Substring($extensionRoot.Length).TrimStart('\','/')
    $destination = Join-Path $pgRoot $relative
    New-Item -ItemType Directory -Force (Split-Path $destination -Parent) | Out-Null
    Copy-Item $file.FullName $destination
  }
  $dumpbin = Get-Command dumpbin.exe -ErrorAction Stop
  & $python (Join-Path $repo 'tools/check_pe_dependencies.py') $pgRoot --dumpbin $dumpbin.Source --archive $CoreArchive --archive $ExtensionArchive --report $ReportPath
  if ($LASTEXITCODE -ne 0) { throw 'Windows PE dependency analysis failed.' }
  $bin = Join-Path $pgRoot 'bin'
  $env:PATH = "$bin;$env:SystemRoot\System32;$env:SystemRoot"
  $env:PGHOST = '127.0.0.1'; $env:PGUSER = 'postgres'; $env:PGDATABASE = 'postgres'; $env:PGSSLMODE = 'disable'
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  $listener.Start(); $env:PGPORT = [string]$listener.LocalEndpoint.Port; $listener.Stop()
  & (Join-Path $bin 'initdb.exe') -D $data -U postgres -A trust --encoding=UTF8 --no-instructions
  if ($LASTEXITCODE -ne 0) { throw 'initdb failed for relocated PostgreSQL.' }
  & (Join-Path $bin 'pg_ctl.exe') -D $data -l (Join-Path $work 'postgresql.log') -o "-h 127.0.0.1 -p $env:PGPORT -c shared_preload_libraries=pg_ivm" -w start
  if ($LASTEXITCODE -ne 0) { Get-Content (Join-Path $work 'postgresql.log') -ErrorAction SilentlyContinue | Write-Host; throw 'PostgreSQL failed to start with pg_ivm preloaded.' }
  $serverStarted = $true
  & (Join-Path $bin 'psql.exe') -X -v ON_ERROR_STOP=1 -f (Join-Path $PSScriptRoot 'probe.sql')
  if ($LASTEXITCODE -ne 0) { throw 'pg_ivm SQL probe failed.' }
  & (Join-Path $bin 'pg_ctl.exe') -D $data -m fast -w stop
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not stop cleanly.' }
  $serverStarted = $false
  Write-Output "PASS: relocated pg_ivm $version archive with PostgreSQL $pgVersion on Windows x86-64."
} finally {
  if ($serverStarted -and $pgRoot) { & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m immediate stop 2>$null | Out-Null }
  $env:PATH = $oldPath
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
