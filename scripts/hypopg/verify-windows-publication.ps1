param(
  [Parameter(Mandatory = $true)][string]$CoreArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$ExtensionArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [ValidateSet("15.19", "16.15", "17.11", "18.6")][string]$PostgreSQLVersion = "18.6",
  [string]$CoreIdentityPath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:RUNNER_OS -ne 'Windows' -or -not [Environment]::Is64BitOperatingSystem) {
  throw 'This archive verifier requires Windows x86-64.'
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$pythonExe = (Get-Command 'python.exe' -ErrorAction Stop).Source
$identityArguments = @('--postgresql-version', $PostgreSQLVersion)
if ($CoreIdentityPath) { $identityArguments += @('--path', (Resolve-Path $CoreIdentityPath).Path) }
$coreIdentity = (& $pythonExe (Join-Path $repo 'tools/windows_core_pin.py') @identityArguments | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0 -or -not $coreIdentity) { throw 'Cannot load the pinned Windows PostgreSQL core identity' }
if ($CoreIdentityPath) { $env:HYPOPG_WINDOWS_CORE_IDENTITY_PATH = (Resolve-Path $CoreIdentityPath).Path }
$coreArchive = Join-Path (Resolve-Path $CoreArchiveDirectory).Path $coreIdentity.archive_name
$extensionName = "hypopg-1.4.3-postgresql-$PostgreSQLVersion-windows-x86_64.tar.gz"
$extensionArchive = Join-Path (Resolve-Path $ExtensionArchiveDirectory).Path $extensionName
$pdb = Join-Path (Resolve-Path $ExtensionArchiveDirectory).Path 'hypopg.pdb'
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
$work = Join-Path $env:RUNNER_TEMP ("hypopg-windows-verify-" + [guid]::NewGuid().ToString('N'))
$first = Join-Path $work 'first'
$moved = Join-Path $work 'moved'
$data = Join-Path $work 'data'
$serverStarted = $false
$originalPath = $env:PATH
New-Item -ItemType Directory -Force $work,$first | Out-Null
Start-Transcript -Path (Join-Path $OutputDirectory 'windows-verification.log') -Force | Out-Null
try {
  foreach ($archive in @($coreArchive,$extensionArchive)) {
    if (-not (Test-Path $archive -PathType Leaf)) { throw "Downloaded archive is missing: $([IO.Path]::GetFileName($archive))" }
    $sidecar = Get-Content "$archive.sha256" -Raw
    $expectedHash = ($sidecar -split '\s+')[0].ToLowerInvariant()
    if ($expectedHash -notmatch '^[0-9a-f]{64}$' -or (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
      throw "Downloaded archive checksum mismatch: $([IO.Path]::GetFileName($archive))"
    }
  }
  if (-not (Test-Path $pdb -PathType Leaf)) { throw 'Downloaded HypoPG PDB is missing' }
  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
  if (-not (Test-Path $vswhere -PathType Leaf)) { throw 'Visual Studio vswhere.exe is missing on the verifier' }
  $vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $vsRoot) { throw 'The Windows verifier has no x64 dumpbin tool' }
  $dumpbinExe = Join-Path $vsRoot 'VC/Tools/MSVC'
  $dumpbin = Get-ChildItem $dumpbinExe -Filter dumpbin.exe -Recurse -File | Select-Object -First 1 -ExpandProperty FullName
  if (-not $dumpbin) { throw 'The Windows verifier has no dumpbin.exe' }

  & tar.exe -xzf $coreArchive -C $first
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract downloaded PostgreSQL archive' }
  $pgRoot = Join-Path $first 'postgresql'
  $manifest = Get-Content (Join-Path $pgRoot 'manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.component -cne 'postgresql' -or $manifest.version -cne $PostgreSQLVersion -or $manifest.platform -cne 'windows' -or $manifest.architecture -cne 'x86_64' -or $manifest.build_id -cne $coreIdentity.build_id -or $manifest.source_revision -cne $coreIdentity.source_revision) {
    throw 'Downloaded core manifest does not match the pinned Windows PostgreSQL build.'
  }
  $pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
  if ((& $pgConfig --version) -cne "PostgreSQL $PostgreSQLVersion") { throw 'Downloaded core pg_config reports an unexpected version' }
  $moduleDir = (& $pgConfig --pkglibdir).Trim()
  $sharedDir = (& $pgConfig --sharedir).Trim()
  $moduleRelative = [IO.Path]::GetRelativePath([IO.Path]::GetFullPath($pgRoot), [IO.Path]::GetFullPath($moduleDir)) -replace '\\','/'
  $sharedRelative = [IO.Path]::GetRelativePath([IO.Path]::GetFullPath($pgRoot), [IO.Path]::GetFullPath($sharedDir)) -replace '\\','/'
  if ($sharedRelative -ne 'share') { throw "Unexpected PostgreSQL sharedir archive layout: $sharedRelative" }
  Move-Item $pgRoot $moved
  $pgRoot = $moved
  $moduleDir = Join-Path $pgRoot $moduleRelative
  $sharedDir = Join-Path $pgRoot $sharedRelative
  $unpacked = Join-Path $work 'unpacked'
  New-Item -ItemType Directory -Force $unpacked | Out-Null
  & tar.exe -xzf $extensionArchive -C $unpacked
  if ($LASTEXITCODE -ne 0) { throw 'Could not unpack downloaded HypoPG archive' }
  $extensionRoot = Join-Path $unpacked 'hypopg'
  Copy-Item (Join-Path (Join-Path $extensionRoot $moduleRelative) 'hypopg.dll') (Join-Path $moduleDir 'hypopg.dll')
  Copy-Item (Join-Path $extensionRoot 'share/extension/*') (Join-Path $sharedDir 'extension')
  $peReport = Join-Path $OutputDirectory 'pe-dependency-analysis.json'
  & $pythonExe (Join-Path $repo 'tools/check_pe_dependencies.py') $pgRoot --dumpbin $dumpbin --archive $coreArchive --archive $extensionArchive --report $peReport
  if ($LASTEXITCODE -ne 0) { throw 'HypoPG Windows PE dependency inspection failed' }
  & $pythonExe (Join-Path $repo 'tools/check_hypopg_windows_archive.py') --postgresql-version $PostgreSQLVersion --core-archive $coreArchive --extension-archive $extensionArchive --pdb $pdb --pe-report $peReport --output (Join-Path $OutputDirectory 'static-analysis.json')
  if ($LASTEXITCODE -ne 0) { throw 'Final archive structural analysis failed' }
  $pe = Get-Content $peReport -Raw | ConvertFrom-Json
  if ($pe.outcome -ne 'passed' -or $pe.archives.Count -ne 2) { throw 'PE dependency analysis did not pass for both archives' }
  $env:PATH = "$(Join-Path $pgRoot 'bin');$env:SystemRoot\System32;$env:SystemRoot"
  & (Join-Path $pgRoot 'bin/initdb.exe') -D $data -U postgres -A trust --encoding=UTF8 --locale=C --no-instructions
  if ($LASTEXITCODE -ne 0) { throw 'initdb failed on the relocated downloaded installation' }
  $serverLog = Join-Path $OutputDirectory 'server.log'
  & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -l $serverLog -o '-p 55432 -h 127.0.0.1' -w start
  if ($LASTEXITCODE -ne 0) { throw 'Downloaded PostgreSQL failed to start after relocation' }
  $serverStarted = $true
  $probeOutput = Join-Path $OutputDirectory 'probe-output.txt'
  & (Join-Path $pgRoot 'bin/psql.exe') -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -f (Join-Path $repo 'scripts/hypopg/probe.sql') 2>&1 | Tee-Object -FilePath $probeOutput
  if ($LASTEXITCODE -ne 0) { throw 'Relocated Windows HypoPG SQL probe failed' }
  if (-not (Select-String -Path $probeOutput -SimpleMatch 'Index Scan using' -Quiet)) { throw 'Probe did not show a plan using its hypothetical index' }
  & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m fast -w stop
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not stop cleanly' }
  $serverStarted = $false
} finally {
  if ($serverStarted) { & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m immediate stop 2>$null | Out-Null }
  $env:PATH = $originalPath
  Stop-Transcript | Out-Null
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
