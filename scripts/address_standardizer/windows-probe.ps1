$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

$runId = '39051931165'
$pgVersion = '18.6'
$pgArtifact = "windows-postgresql-$pgVersion-pilot"
$addressCommit = 'fa11ff53eb49b863d9ffff37f6afd5ff9299c581'
$addressTag = 'v3.7.0'
$pcreVersion = '10.48'
$pcreSha256 = 'b6c68fdf6f3ac31388b50aa89ff0fc49c00c987c16e7b5146491d12003f2c8ed'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$work = Join-Path $env:RUNNER_TEMP 'address-standardizer-windows'
$output = $env:PROBE_OUTPUT
if (-not $output) { $output = Join-Path $env:RUNNER_TEMP 'address-standardizer-results' }
New-Item -ItemType Directory -Force $work, $output | Out-Null
$progressFile = Join-Path $output 'progress.log'
$script:currentStage = 'initialization'

function Write-ProgressMarker([string]$Event, [string]$Detail) {
  $line = "$(Get-Date -AsUTC -Format o) event=$Event stage=$script:currentStage detail=$Detail"
  Write-Host $line
  Add-Content -LiteralPath $progressFile -Value $line -Encoding utf8
}

function Start-Stage([string]$Name) {
  $script:currentStage = $Name
  Write-ProgressMarker 'started' $Name
}

function Complete-Stage {
  Write-ProgressMarker 'completed' $script:currentStage
}

trap {
  Write-ProgressMarker 'failed' $_.Exception.Message
  throw
}

Write-ProgressMarker 'started' 'probe initialized'

function Invoke-Native([string]$File, [string[]]$Arguments) {
  Write-ProgressMarker 'command-started' "$File $($Arguments -join ' ')"
  & $File @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$File failed with exit code $LASTEXITCODE" }
  Write-ProgressMarker 'command-completed' $File
}

function Write-Result([string]$Status, [string]$Detail) {
  @("status=$Status", "detail=$Detail", "postgresql=$pgVersion", "address_standardizer=$addressTag", "address_commit=$addressCommit", "pcre2=$pcreVersion") |
    Set-Content -Encoding utf8 (Join-Path $output 'result.txt')
}

if (-not $env:GH_TOKEN) { throw 'GH_TOKEN is required to download the retained pilot artifact' }
Start-Stage 'download PostgreSQL pilot artifact'
$env:GH_REPO = (git -C $root remote get-url origin) -replace '^https://github.com/', '' -replace '^git@github.com:', '' -replace '\.git$', ''
$env:GH_TOKEN = $env:GH_TOKEN
$artifactDir = Join-Path $work 'pilot-artifact'
Invoke-Native 'gh' @('run', 'download', $runId, '--repo', $env:GH_REPO, '--name', $pgArtifact, '--dir', $artifactDir)
Complete-Stage
$script:currentStage = 'verify PostgreSQL pilot artifact'
Write-ProgressMarker 'started' $script:currentStage
$pgArchive = Join-Path $artifactDir "postgresql-$pgVersion-windows-x86_64.tar.gz"
$checksumFile = "$pgArchive.sha256"
if (-not (Test-Path $pgArchive) -or -not (Test-Path $checksumFile)) { throw 'PostgreSQL pilot archive or checksum sidecar is missing' }
$checksumParts = (Get-Content $checksumFile -Raw).Trim() -split '\s+', 2
$actualHash = (Get-FileHash $pgArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($checksumParts.Count -ne 2 -or $checksumParts[1] -ne (Split-Path $pgArchive -Leaf) -or $checksumParts[0] -ne $actualHash) {
  throw 'PostgreSQL pilot archive checksum verification failed'
}
Complete-Stage
$pgExtract = Join-Path $work 'postgresql-archive'
New-Item -ItemType Directory -Force $pgExtract | Out-Null
Start-Stage 'extract PostgreSQL archive'
Invoke-Native 'tar.exe' @('-xzf', $pgArchive, '-C', $pgExtract)
$pgRoot = Join-Path $pgExtract 'postgresql'
$pgInclude = Join-Path $pgRoot 'include/server'
$pgLib = Join-Path $pgRoot 'lib/postgres.lib'
if (-not (Test-Path $pgInclude -PathType Container) -or -not (Test-Path $pgLib -PathType Leaf)) {
  throw 'Pilot archive lacks include/server or lib/postgres.lib'
}
Complete-Stage

$source = Join-Path $work 'address-standardizer'
Start-Stage 'checkout Address Standardizer source'
Invoke-Native 'git' @('clone', '--no-checkout', 'https://github.com/postgis/address_standardizer.git', $source)
Invoke-Native 'git' @('-C', $source, 'checkout', '--detach', $addressCommit)
$head = (git -C $source rev-parse HEAD).Trim()
if ($head -ne $addressCommit) { throw "Address Standardizer checkout is $head, expected $addressCommit" }
$makefile = Get-Content (Join-Path $source 'Makefile') -Raw
if ($makefile -notmatch 'SRCS\s*=\s*\$\(wildcard\s+src/\*\.c\)' -or
    $makefile -notmatch 'PG_CPPFLAGS\s*\+=\s*-DAS_VERSION=' -or
    $makefile -notmatch 'PCRE_VERSION=2' -or
    $makefile -notmatch 'pcre2-8') {
  throw 'Tagged Makefile source inventory or expected compile/link definitions changed'
}
$control = Get-Content (Join-Path $source 'address_standardizer.control') -Raw
if ($control -notmatch "default_version\s*=\s*'3\.7'") { throw 'Tagged control version is not 3.7' }
$sources = @(Get-ChildItem (Join-Path $source 'src') -Filter '*.c' -File | Sort-Object Name)
if ($sources.Count -eq 0) { throw 'Tagged Makefile source inventory resolved to no C files' }
foreach ($header in @('parseaddress-regex.h', 'parseaddress-stcities.h')) {
  if (-not (Test-Path (Join-Path $source "src/$header") -PathType Leaf)) { throw "Committed generated header is missing: $header" }
}
Complete-Stage

$pcreArchive = Join-Path $work "pcre2-$pcreVersion.tar.bz2"
Start-Stage 'download PCRE2 source'
Invoke-Native 'curl.exe' @('-fL', '--retry', '3', '-o', $pcreArchive, "https://github.com/PCRE2Project/pcre2/releases/download/pcre2-$pcreVersion/pcre2-$pcreVersion.tar.bz2")
if ((Get-FileHash $pcreArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pcreSha256) { throw 'PCRE2 source checksum mismatch' }
Complete-Stage
$pcreSourceDir = Join-Path $work 'pcre-source'
New-Item -ItemType Directory -Force $pcreSourceDir | Out-Null
Start-Stage 'extract PCRE2 source'
Invoke-Native 'python' @('-m', 'tarfile', '-e', $pcreArchive, $pcreSourceDir)
Complete-Stage
$pcreSource = Join-Path $pcreSourceDir "pcre2-$pcreVersion"
$pcreBuild = Join-Path $work 'pcre-build'
$pcreInstall = Join-Path $work 'pcre-install'
Start-Stage 'configure PCRE2'
Invoke-Native 'cmake.exe' @('-S', $pcreSource, '-B', $pcreBuild, '-G', 'Visual Studio 17 2022', '-A', 'x64', "-DCMAKE_INSTALL_PREFIX=$pcreInstall", '-DBUILD_SHARED_LIBS=ON', '-DPCRE2_BUILD_PCRE2_8=ON', '-DPCRE2_BUILD_PCRE2_16=OFF', '-DPCRE2_BUILD_PCRE2_32=OFF', '-DPCRE2_BUILD_TESTS=OFF', '-DPCRE2_BUILD_PCRE2GREP=OFF')
Complete-Stage
Start-Stage 'build and install PCRE2'
Invoke-Native 'cmake.exe' @('--build', $pcreBuild, '--config', 'Release', '--target', 'install', '--parallel')
Complete-Stage
$pcreInclude = Join-Path $pcreInstall 'include'
$pcreLib = Get-ChildItem $pcreInstall -Recurse -Filter 'pcre2-8.lib' -File | Select-Object -First 1
$pcreDll = Get-ChildItem $pcreInstall -Recurse -Filter 'pcre2-8.dll' -File | Select-Object -First 1
if (-not $pcreLib -or -not $pcreDll) { throw 'PCRE2 8-bit shared library import library or runtime DLL is missing' }

$buildDir = Join-Path $work 'address-build'
New-Item -ItemType Directory -Force $buildDir | Out-Null
$compiler = (Get-Command 'clang-cl.exe' -ErrorAction Stop).Source
$objects = @()
$sourceIndex = 0
Start-Stage "compile Address Standardizer sources ($($sources.Count) files)"
foreach ($sourceFile in $sources) {
  $sourceIndex++
  Write-ProgressMarker 'source-compile-started' "$sourceIndex/$($sources.Count) $($sourceFile.Name)"
  $object = Join-Path $buildDir ($sourceFile.BaseName + '.obj')
  Invoke-Native $compiler @('/nologo', '/c', '/MD', '/O2', '/DWIN32', '/D_WINDOWS', '/D_CRT_SECURE_NO_WARNINGS', '/DAS_VERSION="3.7"', '/DPCRE_VERSION=2', "/I$pgInclude", "/I$(Join-Path $pgInclude 'port/win32')", "/I$(Join-Path $pgInclude 'port/win32_msvc')", "/I$(Join-Path $pgRoot 'include')", "/I$(Join-Path $source 'src')", "/I$pcreInclude", "/Fo$object", $sourceFile.FullName)
  $objects += $object
  Write-ProgressMarker 'source-compile-completed' "$sourceIndex/$($sources.Count) $($sourceFile.Name)"
}
Complete-Stage
$extensionDll = Join-Path $buildDir 'address_standardizer.dll'
Start-Stage 'link Address Standardizer DLL'
Invoke-Native 'link.exe' (@('/nologo', '/DLL', "/OUT:$extensionDll", "/LIBPATH:$(Split-Path $pgLib)", "/LIBPATH:$($pcreLib.DirectoryName)") + $objects + @('postgres.lib', 'pcre2-8.lib'))
Complete-Stage

Start-Stage 'inspect Address Standardizer DLL imports and exports'
Invoke-Native 'dumpbin.exe' @('/exports', $extensionDll) | Set-Content (Join-Path $output 'exports.txt')
Invoke-Native 'dumpbin.exe' @('/dependents', $extensionDll) | Set-Content (Join-Path $output 'extension-dependencies.txt')
Invoke-Native 'dumpbin.exe' @('/imports', $extensionDll) | Set-Content (Join-Path $output 'imports.txt')
$imports = Get-Content (Join-Path $output 'extension-dependencies.txt') -Raw
if ($imports -notmatch '(?i)pcre2-8\.dll') { throw 'Address Standardizer DLL does not import the expected PCRE2 runtime DLL' }
Complete-Stage

function Join-TaggedSql([string[]]$Inputs, [string]$Destination) {
  $content = foreach ($inputFile in $Inputs) {
    $path = Join-Path $source $inputFile
    if (-not (Test-Path $path -PathType Leaf)) { throw "Tagged SQL input is missing: $inputFile" }
    [IO.File]::ReadAllText($path)
  }
  [IO.File]::WriteAllText($Destination, ($content -join "`n"), [Text.UTF8Encoding]::new($false))
}

$sqlDir = Join-Path $work 'generated-sql'
New-Item -ItemType Directory -Force $sqlDir | Out-Null
Start-Stage 'generate extension SQL files'
$baseSql = @('sql/01_types.sql', 'sql/12_functions.sql')
$usSql = @('sql/13_us_lex.sql', 'sql/14_us_gaz.sql', 'sql/15_us_rules.sql', 'sql/16_data_extension.sql')
Join-TaggedSql $baseSql (Join-Path $sqlDir 'address_standardizer--3.7.sql')
Join-TaggedSql @('sql/12_functions.sql') (Join-Path $sqlDir 'address_standardizer--ANY--3.7.sql')
Join-TaggedSql $usSql (Join-Path $sqlDir 'address_standardizer_data_us--3.7.sql')
Join-TaggedSql $usSql (Join-Path $sqlDir 'address_standardizer_data_us--ANY--3.7.sql')
Complete-Stage

$extensionDir = Join-Path $pgRoot 'share/extension'
$moduleDir = Join-Path $pgRoot 'lib/postgresql'
$binDir = Join-Path $pgRoot 'bin'
Start-Stage 'install extension files'
Copy-Item (Join-Path $source 'address_standardizer.control') $extensionDir
Copy-Item (Join-Path $source 'address_standardizer_data_us.control') $extensionDir
Get-ChildItem $sqlDir -File | Copy-Item -Destination $extensionDir
Copy-Item $extensionDll (Join-Path $moduleDir 'address_standardizer.dll')
Copy-Item $pcreDll.FullName (Join-Path $binDir 'pcre2-8.dll')
Complete-Stage

$dataDir = Join-Path $work 'database'
$socketHost = '127.0.0.1'
Start-Stage 'initialize PostgreSQL database'
Invoke-Native (Join-Path $binDir 'initdb.exe') @('-D', $dataDir, '-U', 'postgres', '--no-instructions', '--encoding=UTF8', '--locale=C')
Complete-Stage
$serverStarted = $false
try {
  Start-Stage 'start PostgreSQL server'
  Invoke-Native (Join-Path $binDir 'pg_ctl.exe') @('-D', $dataDir, '-o', "-p 55432 -h $socketHost", '-w', 'start')
  $serverStarted = $true
  Complete-Stage
  Start-Stage 'run Address Standardizer SQL probe'
  Write-ProgressMarker 'command-started' 'psql Address Standardizer SQL probe'
  & (Join-Path $binDir 'psql.exe') '-X' '-v' 'ON_ERROR_STOP=1' '-h' $socketHost '-p' '55432' '-U' 'postgres' '-d' 'postgres' '-f' (Join-Path $root 'scripts/address_standardizer/probe.sql') 2>&1 |
    Tee-Object -FilePath (Join-Path $output 'probe-output.txt')
  if ($LASTEXITCODE -ne 0) { throw "Address Standardizer SQL probe failed with exit code $LASTEXITCODE" }
  Write-ProgressMarker 'command-completed' 'psql Address Standardizer SQL probe'
  Complete-Stage
} finally {
  if ($serverStarted) {
    Start-Stage 'stop PostgreSQL server'
    Invoke-Native (Join-Path $binDir 'pg_ctl.exe') @('-D', $dataDir, '-m', 'fast', '-w', 'stop')
    Complete-Stage
  }
}

Write-Result 'runtime-probe-passed' 'Tagged sources compiled and linked; both extensions installed and the representative SQL operation passed.'
Start-Stage 'probe completed'
Complete-Stage
Write-Host "Compiled $($sources.Count) tagged C sources and passed the PostgreSQL runtime probe."
