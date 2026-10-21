param(
  [Parameter(Mandatory = $true)][string]$CoreArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$ExtensionArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [Parameter(Mandatory = $true)][ValidateSet('15.19','16.15','17.11','18.6')][string]$PostgreSQLVersion,
  [Parameter(Mandatory = $true)][string]$CoreIdentityPath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$identity = Get-Content $CoreIdentityPath -Raw | ConvertFrom-Json
if ($identity.postgresql_version -cne $PostgreSQLVersion) { throw 'Core identity version differs from the requested PostgreSQL version.' }
$coreName = "postgresql-$PostgreSQLVersion-windows-x86_64.tar.gz"
$extensionName = "pg_jsonschema-0.3.4-postgresql-$PostgreSQLVersion-windows-x86_64.tar.gz"
$coreArchive = Join-Path $CoreArchiveDirectory $coreName
$extensionArchive = Join-Path $ExtensionArchiveDirectory $extensionName
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$python = (Get-Command python -ErrorAction Stop).Source
foreach ($entry in @(@($coreArchive, 'postgresql'), @($extensionArchive, 'pg_jsonschema'))) {
  & $python (Join-Path $repo 'tools/license_pointer.py') verify $entry[0] $entry[1]
  if ($LASTEXITCODE -ne 0) { throw "Licence pointer verification failed for $(Split-Path $entry[0] -Leaf)." }
}
foreach ($archive in @($coreArchive, $extensionArchive)) {
  if (-not (Test-Path $archive -PathType Leaf)) { throw "Required archive is missing: $archive" }
  $sidecar = ((Get-Content "$archive.sha256" -Raw) -split '\s+')[0].ToLowerInvariant()
  $actual = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $sidecar) { throw "Archive checksum sidecar mismatch: $archive" }
}
if ((Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $identity.sha256) { throw 'Core archive hash differs from checked identity.' }
$work = Join-Path $env:RUNNER_TEMP ("pg-jsonschema-verify-" + [guid]::NewGuid().ToString('N'))
$coreRoot = Join-Path $work 'core'
$extensionRoot = Join-Path $work 'extension'
$data = Join-Path $work 'data'
New-Item -ItemType Directory -Force $coreRoot,$extensionRoot | Out-Null
& tar.exe -xzf $coreArchive -C $coreRoot
if ($LASTEXITCODE -ne 0) { throw 'Could not extract downloaded PostgreSQL core archive.' }
& tar.exe -xzf $extensionArchive -C $extensionRoot
if ($LASTEXITCODE -ne 0) { throw 'Could not extract downloaded pg_jsonschema archive.' }
$pgRoot = Join-Path $coreRoot 'postgresql'
$manifest = Get-Content (Join-Path $pgRoot 'manifest.json') -Raw | ConvertFrom-Json
if ($manifest.version -cne $PostgreSQLVersion -or $manifest.build_id -cne $identity.build_id -or $manifest.source_revision -cne $identity.source_revision) { throw 'Downloaded core manifest differs from checked identity.' }
$payload = Join-Path $extensionRoot 'pg_jsonschema'
Copy-Item (Join-Path $payload 'lib/pg_jsonschema.dll') (Join-Path $pgRoot 'lib/pg_jsonschema.dll') -Force
$share = Join-Path $pgRoot 'share/extension'
Get-ChildItem (Join-Path $payload 'share/extension') -File | Copy-Item -Destination $share -Force
$python = (Get-Command python -ErrorAction Stop).Source
$originalPath = $env:PATH
$serverStarted = $false
try {
  $env:PATH = "$(Join-Path $pgRoot 'bin');$env:SystemRoot\System32;$env:SystemRoot"
  $initdb = Join-Path $pgRoot 'bin/initdb.exe'
  $pgCtl = Join-Path $pgRoot 'bin/pg_ctl.exe'
  $psql = Join-Path $pgRoot 'bin/psql.exe'
  & $initdb -D $data -U postgres -A trust --encoding=UTF8 --locale=C --no-instructions
  if ($LASTEXITCODE -ne 0) { throw 'First initdb failed on the fresh-runner extracted core.' }
  & $pgCtl -D $data -l (Join-Path $OutputDirectory 'first-run-server.log') -o '-p 55432 -h 127.0.0.1' -w start
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL failed to start for the first fresh-runner probe.' }
  $serverStarted = $true
  & $psql -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -f (Join-Path $PSScriptRoot 'probe.sql') 2>&1 | Tee-Object -FilePath (Join-Path $OutputDirectory 'first-run-probe-output.txt')
  if ($LASTEXITCODE -ne 0) { throw 'First fresh-runner SQL probe failed.' }
  & $pgCtl -D $data -m fast -w stop
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not stop before relocation.' }
  $serverStarted = $false
  Remove-Item $data -Recurse -Force
  $originalPgRoot = $pgRoot
  $relocatedParent = Join-Path $work 'relocated'
  New-Item -ItemType Directory -Force $relocatedParent | Out-Null
  $pgRoot = Join-Path $relocatedParent 'postgresql'
  Move-Item $originalPgRoot $pgRoot
  if (Test-Path $originalPgRoot) { throw 'The original assembled PostgreSQL path remains available after relocation.' }
  if (-not (Test-Path (Join-Path $pgRoot 'bin/pg_config.exe') -PathType Leaf)) { throw 'Relocated PostgreSQL installation is incomplete.' }
  $env:PATH = "$(Join-Path $pgRoot 'bin');$env:SystemRoot\System32;$env:SystemRoot"
  $initdb = Join-Path $pgRoot 'bin/initdb.exe'
  $pgCtl = Join-Path $pgRoot 'bin/pg_ctl.exe'
  $psql = Join-Path $pgRoot 'bin/psql.exe'
  & $initdb -D $data -U postgres -A trust --encoding=UTF8 --locale=C --no-instructions
  if ($LASTEXITCODE -ne 0) { throw 'Second initdb failed after moving the assembled installation.' }
  & $pgCtl -D $data -l (Join-Path $OutputDirectory 'fresh-runner-server.log') -o '-p 55432 -h 127.0.0.1' -w start
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL failed to start after moving the assembled installation.' }
  $serverStarted = $true
  & $psql -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -f (Join-Path $PSScriptRoot 'probe.sql') 2>&1 | Tee-Object -FilePath (Join-Path $OutputDirectory 'fresh-runner-probe-output.txt')
  if ($LASTEXITCODE -ne 0) { throw 'SQL probe failed after moving the assembled installation.' }
  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
  $vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $vsRoot) { throw 'Visual Studio x64 toolchain is missing from the fresh runner.' }
  $dumpbin = Get-ChildItem (Join-Path $vsRoot 'VC/Tools/MSVC') -Directory | Sort-Object Name -Descending | Select-Object -First 1
  if ($dumpbin) { $dumpbin = Join-Path $dumpbin.FullName 'bin/Hostx64/x64/dumpbin.exe' }
  if (-not $dumpbin -or -not (Test-Path $dumpbin -PathType Leaf)) { throw 'x64 dumpbin.exe is missing from the fresh runner.' }
  & $python (Join-Path $PSScriptRoot '../../tools/check_pe_dependencies.py') $pgRoot --dumpbin $dumpbin --archive $coreArchive --archive $extensionArchive --report (Join-Path $OutputDirectory 'fresh-runner-pe-dependency-analysis.json')
  if ($LASTEXITCODE -ne 0) { throw 'Fresh-runner PE dependency closure check failed.' }
  & $pgCtl -D $data -m fast -w stop
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not stop cleanly after the relocated probe.' }
  $serverStarted = $false
  'result=passed' | Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'fresh-runner-result.txt')
} catch {
  $_ | Out-String | Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'fresh-runner-failure.txt')
  throw
} finally {
  if ($serverStarted) { & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m immediate stop 2>$null | Out-Null }
  $env:PATH = $originalPath
}
