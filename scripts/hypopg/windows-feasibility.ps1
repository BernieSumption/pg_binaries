param(
  [Parameter(Mandatory = $true)][string]$CoreArchiveDirectory,
  [Parameter(Mandatory = $true)][string]$OutputDirectory,
  [ValidateSet("15.19", "16.15", "17.11", "18.6")][string]$PostgreSQLVersion = "18.6",
  [string]$CoreIdentityPath,
  [switch]$BuildOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$pythonExe = (Get-Command 'python.exe' -ErrorAction Stop).Source
$identityArguments = @('--postgresql-version', $PostgreSQLVersion)
if ($CoreIdentityPath) { $identityArguments += @('--path', (Resolve-Path $CoreIdentityPath).Path) }
$coreIdentity = (& $pythonExe (Join-Path $repo 'tools/windows_core_pin.py') @identityArguments | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0 -or -not $coreIdentity) { throw 'Cannot load the pinned Windows PostgreSQL core identity' }
$version = '1.4.3'
$pgVersion = $coreIdentity.postgresql_version
$architecture = 'x86_64'
$sourceUrl = 'https://github.com/HypoPG/hypopg/archive/refs/tags/1.4.3.tar.gz'
$sourceSha256 = '498a961d88cf37057fd9e98027d06fe805c8959d51895c3d9b94c9eb4e14f706'
$coreArchiveName = $coreIdentity.archive_name
$coreSha256 = $coreIdentity.sha256

if ($env:RUNNER_OS -ne 'Windows' -or -not [Environment]::Is64BitOperatingSystem) {
  throw 'This feasibility probe requires Windows x86-64.'
}
$CoreArchiveDirectory = (Resolve-Path $CoreArchiveDirectory).Path
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
$work = Join-Path $env:RUNNER_TEMP ("hypopg-windows-" + [guid]::NewGuid().ToString('N'))
$coreArchive = Join-Path $CoreArchiveDirectory $coreArchiveName
$first = Join-Path $work 'first'
$moved = Join-Path $work 'moved'
$sourceDir = Join-Path $work 'source'
$stage = Join-Path $work 'stage'
$data = Join-Path $work 'data'
$serverStarted = $false
$originalPath = $env:PATH
New-Item -ItemType Directory -Force $work,$first,$sourceDir,$stage | Out-Null
Start-Transcript -Path (Join-Path $OutputDirectory 'windows-build.log') -Force | Out-Null
@("source_url=$sourceUrl","source_sha256=$sourceSha256","postgresql_archive=$coreArchiveName","postgresql_sha256=$coreSha256","hypopg_version=$version","core_profile_id=$($coreIdentity.profile_id)") |
  Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'build-identity.txt')

try {
  if (-not (Test-Path $coreArchive -PathType Leaf)) { throw "Pinned core archive is missing: $coreArchiveName" }
  $actualCoreHash = (Get-FileHash $coreArchive -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actualCoreHash -ne $coreSha256) { throw 'Pinned core archive checksum mismatch' }
  $sidecarHash = ((Get-Content "$coreArchive.sha256" -Raw) -split '\s+')[0].ToLowerInvariant()
  if ($sidecarHash -ne $coreSha256) { throw 'Core checksum sidecar does not match the pinned archive identity' }

  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
  if (-not (Test-Path $vswhere -PathType Leaf)) { throw 'Visual Studio vswhere.exe is missing' }
  $vsRoot = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $vsRoot) { throw 'The Windows runner has no x64 MSVC toolchain' }
  $vcvars = Join-Path $vsRoot 'VC/Auxiliary/Build/vcvars64.bat'
  $environmentScript = Join-Path $work 'load-msvc-environment.cmd'
  @('@echo off', "call `"$vcvars`" >nul", 'if errorlevel 1 exit /b %errorlevel%', 'set') |
    Set-Content -Encoding ascii $environmentScript
  $environmentOutput = & $env:ComSpec /d /c $environmentScript
  if ($LASTEXITCODE -ne 0) { throw 'Could not load the x64 MSVC developer environment' }
  foreach ($line in $environmentOutput) {
    if ($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process') }
  }
  foreach ($command in @('cl.exe','link.exe','clang-cl.exe')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "MSVC tool is unavailable: $command" }
  }
  $clExe = (Get-Command 'cl.exe').Source
  $dumpbinExe = Join-Path (Split-Path $clExe -Parent) 'dumpbin.exe'
  if (-not (Test-Path $dumpbinExe -PathType Leaf)) { throw 'Visual Studio dumpbin.exe was not found beside cl.exe' }

  & tar.exe -xzf $coreArchive -C $first
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the pinned PostgreSQL core archive' }
  $pgRoot = Join-Path $first 'postgresql'
  $manifest = Get-Content (Join-Path $pgRoot 'manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.component -cne 'postgresql' -or $manifest.version -cne $pgVersion -or
      $manifest.platform -cne 'windows' -or $manifest.architecture -cne $architecture -or
      $manifest.build_id -cne $coreIdentity.build_id -or $manifest.source_revision -cne $coreIdentity.source_revision) {
    throw 'The core archive manifest does not match the pinned Windows PostgreSQL build.'
  }
  $pgConfig = Join-Path $pgRoot 'bin/pg_config.exe'
  foreach ($exe in @($pgConfig,(Join-Path $pgRoot 'bin/initdb.exe'),(Join-Path $pgRoot 'bin/pg_ctl.exe'),(Join-Path $pgRoot 'bin/psql.exe'))) {
    if (-not (Test-Path $exe -PathType Leaf)) { throw "PostgreSQL executable is missing: $exe" }
  }
  if ((& $pgConfig --version) -cne "PostgreSQL $pgVersion") { throw 'The core pg_config reports an unexpected version' }
  $pgInclude = Join-Path $pgRoot 'include/server'
  $pgImportLibrary = Join-Path $pgRoot 'lib/postgres.lib'
  $moduleDir = (& $pgConfig --pkglibdir).Trim()
  $sharedDir = (& $pgConfig --sharedir).Trim()
  if (-not (Test-Path $pgInclude -PathType Container) -or -not (Test-Path $pgImportLibrary -PathType Leaf)) {
    throw 'Pinned core archive lacks include/server or lib/postgres.lib required for the MSVC extension link.'
  }
  foreach ($directory in @($moduleDir,$sharedDir)) {
    $relative = [IO.Path]::GetRelativePath([IO.Path]::GetFullPath($pgRoot), [IO.Path]::GetFullPath($directory))
    if ($relative -eq '..' -or $relative.StartsWith("..$([IO.Path]::DirectorySeparatorChar)") -or [IO.Path]::IsPathRooted($relative)) {
      throw "PostgreSQL Windows module/share directory is outside the core archive: $directory"
    }
  }

  $sourceArchive = Join-Path $work 'hypopg.tar.gz'
  & curl.exe -fL --retry 3 -o $sourceArchive $sourceUrl
  if ($LASTEXITCODE -ne 0) { throw 'Could not download the pinned HypoPG source archive' }
  if ((Get-FileHash $sourceArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sourceSha256) { throw 'Pinned HypoPG source checksum mismatch' }
  & tar.exe -xzf $sourceArchive -C $sourceDir
  if ($LASTEXITCODE -ne 0) { throw 'Could not extract the pinned HypoPG source archive' }
  $source = Join-Path $sourceDir 'hypopg-1.4.3'
  if ((Get-Content (Join-Path $source 'hypopg.control') -Raw) -notmatch "(?m)^default_version\s*=\s*'$version'$" ) { throw 'Upstream control version mismatch' }
  $makefile = Join-Path $source 'Makefile'
  $makefileText = Get-Content $makefile -Raw
  if ($makefileText -notmatch '(?m)^MODULE_big\s*=\s*hypopg\s*$' -or
      $makefileText -notmatch '(?m)^EXTENSION\s*=\s*hypopg\s*$') {
    throw 'Pinned upstream Makefile no longer identifies the expected HypoPG module and SQL extension.'
  }
  $logicalMakefile = $makefileText -replace "\\\r?\n[ \t]*", ' '
  $objectLines = @([regex]::Matches($logicalMakefile, '(?m)^OBJS\s*=\s*([^\r\n]+)'))
  if ($objectLines.Count -ne 1) { throw 'Could not derive one unambiguous OBJS list from the pinned upstream Makefile.' }
  $objectNames = @($objectLines[0].Groups[1].Value.Trim() -split '\s+' | Where-Object { $_ })
  if (-not $objectNames.Count -or @($objectNames | Where-Object { $_ -notmatch '^[A-Za-z0-9_./]+\.o$' -or $_ -match '(^|/)\.\.?(/|$)' }).Count) {
    throw 'The upstream OBJS list contains an unsupported or empty source entry.'
  }
  if (@($objectNames | Select-Object -Unique).Count -ne $objectNames.Count) { throw 'The upstream OBJS list contains duplicate source entries.' }
  $expectedObjectNames = @('hypopg.o','hypopg_index.o','import/hypopg_import.o','import/hypopg_import_index.o')
  if (@(Compare-Object $expectedObjectNames $objectNames).Count) { throw "Pinned upstream OBJS inventory changed: $($objectNames -join ', ')" }
  $sources = @($objectNames | ForEach-Object {
    $cPath = Join-Path $source ($_.Substring(0, $_.Length - 2) + '.c')
    if (-not (Test-Path $cPath -PathType Leaf)) { throw "The Makefile C source is missing: $($_)" }
    Get-Item $cPath
  })
  $buildDir = Join-Path $work 'build'
  New-Item -ItemType Directory -Force $buildDir | Out-Null
  $compiler = (Get-Command 'clang-cl.exe' -ErrorAction Stop).Source
  $makefileHash = (Get-FileHash $makefile -Algorithm SHA256).Hash
  $objects = @()
  foreach ($sourceFile in $sources) {
    $object = Join-Path $buildDir ($sourceFile.BaseName + '.obj')
    $compileArguments = @(
      '/nologo','/c','/MD','/O2','/DWIN32','/D_WINDOWS','/D_CRT_SECURE_NO_WARNINGS',
      "/I$pgInclude", "/I$(Join-Path $pgInclude 'port/win32')",
      "/I$(Join-Path $pgInclude 'port/win32_msvc')", "/I$(Join-Path $pgRoot 'include')",
      "/I$source", "/Fo$object", $sourceFile.FullName
    )
    & $compiler @compileArguments
    if ($LASTEXITCODE -ne 0) { throw "MSVC-compatible compilation failed for upstream source $($sourceFile.Name)" }
    $objects += $object
  }
  $dll = Join-Path $buildDir 'hypopg.dll'
  $pdb = Join-Path $buildDir 'hypopg.pdb'
  & link.exe '/nologo' '/DLL' '/DEBUG' "/OUT:$dll" "/PDB:$pdb" "/LIBPATH:$(Split-Path $pgImportLibrary)" $objects 'postgres.lib'
  if ($LASTEXITCODE -ne 0) { throw 'MSVC-compatible link failed for the unmodified HypoPG objects' }
  if (-not (Test-Path $dll -PathType Leaf)) { throw 'The MSVC link did not produce hypopg.dll' }
  if (-not (Test-Path $pdb -PathType Leaf)) { throw 'The MSVC link did not produce HypoPG debug symbols' }
  Copy-Item $pdb (Join-Path $OutputDirectory 'hypopg.pdb')
  if ((Get-FileHash $makefile -Algorithm SHA256).Hash -ne $makefileHash) { throw 'Upstream Makefile changed during the build' }

  $payload = Join-Path $stage 'hypopg'
  $moduleRelative = [IO.Path]::GetRelativePath([IO.Path]::GetFullPath($pgRoot), [IO.Path]::GetFullPath($moduleDir)) -replace '\\','/'
  $sharedRelative = [IO.Path]::GetRelativePath([IO.Path]::GetFullPath($pgRoot), [IO.Path]::GetFullPath($sharedDir)) -replace '\\','/'
  if ($sharedRelative -ne 'share') { throw "Unexpected PostgreSQL sharedir archive layout: $sharedRelative" }
  $extensionPayloadDir = Join-Path $payload 'share/extension'
  $modulePayloadDir = Join-Path $payload $moduleRelative
  New-Item -ItemType Directory -Force $modulePayloadDir,$extensionPayloadDir | Out-Null
  Copy-Item $dll (Join-Path $modulePayloadDir 'hypopg.dll')
  Copy-Item (Join-Path $source 'hypopg.control') (Join-Path $payload 'share/extension')
  Copy-Item (Join-Path $source 'hypopg--*.sql') (Join-Path $payload 'share/extension')
  & $pythonExe (Join-Path $repo 'tools/license_pointer.py') write $payload hypopg
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the HypoPG licence pointer.' }
  $metadata = [ordered]@{
    project = 'hypopg'; version = $version; sql_names = @('hypopg'); requires = @()
    postgresql_version = $pgVersion; platform = 'windows'; architecture = $architecture
    source = @{ url = $sourceUrl; sha256 = $sourceSha256 }
    core_archive = @{ basename = $coreArchiveName; sha256 = $coreSha256 }
    release_eligible = $false; core_status = $coreIdentity.status
  }
  $metadata | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 (Join-Path $stage 'metadata.json')
  $archiveName = "hypopg-$version-postgresql-$pgVersion-windows-$architecture.tar.gz"
  $extensionArchive = Join-Path $OutputDirectory $archiveName
  & tar.exe -czf $extensionArchive -C $stage hypopg metadata.json
  if ($LASTEXITCODE -ne 0) { throw 'Could not create the HypoPG extension archive' }
  & $pythonExe (Join-Path $repo 'tools/license_pointer.py') verify $extensionArchive hypopg
  if ($LASTEXITCODE -ne 0) { throw 'HypoPG archive licence pointer verification failed.' }
  $extensionHash = (Get-FileHash $extensionArchive -Algorithm SHA256).Hash.ToLowerInvariant()
  [IO.File]::WriteAllText("$extensionArchive.sha256", "$extensionHash  $archiveName`n", [Text.UTF8Encoding]::new($false))

  if ($BuildOnly) { return }

  Move-Item $pgRoot $moved
  $pgRoot = $moved
  $moduleDir = Join-Path $pgRoot $moduleRelative
  $sharedDir = Join-Path $pgRoot $sharedRelative
  if (-not (Test-Path $moduleDir -PathType Container) -or -not (Test-Path $sharedDir -PathType Container)) {
    throw 'Relocated PostgreSQL module or shared directory is missing.'
  }
  $env:PATH = "$(Join-Path $pgRoot 'bin');$env:SystemRoot\System32;$env:SystemRoot"
  $unpacked = Join-Path $work 'unpacked'
  New-Item -ItemType Directory -Force $unpacked | Out-Null
  & tar.exe -xzf $extensionArchive -C $unpacked
  if ($LASTEXITCODE -ne 0) { throw 'Could not unpack the final HypoPG archive' }
  $extensionRoot = Join-Path $unpacked 'hypopg'
  Copy-Item (Join-Path (Join-Path $extensionRoot $moduleRelative) 'hypopg.dll') (Join-Path $moduleDir 'hypopg.dll')
  Copy-Item (Join-Path $extensionRoot 'share/extension/*') (Join-Path $sharedDir 'extension')
  $env:PATH = "$(Join-Path $pgRoot 'bin');$env:SystemRoot\System32;$env:SystemRoot"
  & (Join-Path $pgRoot 'bin/initdb.exe') -D $data -U postgres -A trust --encoding=UTF8 --locale=C --no-instructions
  if ($LASTEXITCODE -ne 0) { throw 'initdb failed on the relocated PostgreSQL installation' }
  $serverLog = Join-Path $OutputDirectory 'server.log'
  & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -l $serverLog -o '-p 55432 -h 127.0.0.1' -w start
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL failed to start after relocation' }
  $serverStarted = $true
  $probeOutput = Join-Path $OutputDirectory 'probe-output.txt'
  & (Join-Path $pgRoot 'bin/psql.exe') -X -A -t -v ON_ERROR_STOP=1 -h 127.0.0.1 -p 55432 -U postgres -d postgres -f (Join-Path $repo 'scripts/hypopg/probe.sql') 2>&1 | Tee-Object -FilePath $probeOutput
  if ($LASTEXITCODE -ne 0) { throw 'The relocated Windows HypoPG SQL probe failed' }
  if (-not (Select-String -Path $probeOutput -SimpleMatch 'Index Scan using' -Quiet)) { throw 'The probe did not show a plan using its hypothetical index' }
  & $pythonExe (Join-Path $repo 'tools/check_pe_dependencies.py') $pgRoot --dumpbin $dumpbinExe --archive $coreArchive --archive $extensionArchive --report (Join-Path $OutputDirectory 'pe-dependency-analysis.json')
  if ($LASTEXITCODE -ne 0) { throw 'HypoPG Windows PE dependency inspection failed' }
  & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m fast -w stop
  if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not stop cleanly' }
  $serverStarted = $false
  @("source_url=$sourceUrl","source_sha256=$sourceSha256","source_object_list=$($objectNames -join ',')","postgresql_archive=$coreArchiveName","postgresql_sha256=$coreSha256","hypopg_version=$version","hypopg_archive=$archiveName","hypopg_sha256=$extensionHash","windows_version=$([Environment]::OSVersion.Version)","runner_image=$([Environment]::GetEnvironmentVariable('ImageOS'))/$([Environment]::GetEnvironmentVariable('ImageVersion'))") | Set-Content -Encoding utf8 (Join-Path $OutputDirectory 'build-identity.txt')
} finally {
  if ($serverStarted) { & (Join-Path $pgRoot 'bin/pg_ctl.exe') -D $data -m immediate stop 2>$null | Out-Null }
  $env:PATH = $originalPath
  Stop-Transcript | Out-Null
  Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
}
