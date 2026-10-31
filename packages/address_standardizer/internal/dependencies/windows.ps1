param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
if ($env:VSCMD_ARG_TGT_ARCH -and $env:VSCMD_ARG_TGT_ARCH -ne 'x64') { throw 'MSVC must target x64 for PCRE2' }
$source = Join-Path $Workspace 'sources/pcre2'
$build = Join-Path $Workspace 'build/pcre2'
$prefix = Join-Path $Workspace 'build/dependencies'
if (-not (Test-Path (Join-Path $source 'CMakeLists.txt') -PathType Leaf)) { throw 'Pinned PCRE2 CMake project is missing' }
$cmake = (Get-Command 'cmake.exe' -ErrorAction Stop).Source
if (-not (Get-Command 'ninja.exe' -ErrorAction SilentlyContinue)) { throw 'Ninja is unavailable in the Windows development environment' }

& $cmake '-S' $source '-B' $build '-G' 'Ninja' "-DCMAKE_INSTALL_PREFIX=$prefix" `
    '-DCMAKE_BUILD_TYPE=Release' '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL' `
    '-DBUILD_SHARED_LIBS=OFF' '-DBUILD_STATIC_LIBS=ON' `
    '-DPCRE2_BUILD_PCRE2_8=ON' '-DPCRE2_BUILD_PCRE2_16=OFF' '-DPCRE2_BUILD_PCRE2_32=OFF' `
    '-DPCRE2_SUPPORT_JIT=ON' '-DPCRE2_BUILD_PCRE2GREP=OFF' '-DPCRE2_BUILD_TESTS=OFF'
if ($LASTEXITCODE -ne 0) { throw 'PCRE2 CMake configuration failed' }
& $cmake '--build' $build '--config' 'Release'
if ($LASTEXITCODE -ne 0) { throw 'PCRE2 static build failed' }
& $cmake '--install' $build '--config' 'Release'
if ($LASTEXITCODE -ne 0) { throw 'PCRE2 install failed' }
