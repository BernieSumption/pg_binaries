param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
$dependencies = Join-Path $Workspace 'build/dependencies'
& (Join-Path $env:VCPKG_INSTALLATION_ROOT 'vcpkg.exe') install --triplet x64-windows --host-triplet x64-windows --x-install-root=$dependencies icu zlib lz4 zstd openssl libxml2 libxslt
if ($LASTEXITCODE) { throw 'vcpkg dependencies failed' }
$env:PKG_CONFIG_PATH = Join-Path $dependencies 'x64-windows/lib/pkgconfig'
$dep = Join-Path $dependencies 'x64-windows'
$env:PATH = "$(Join-Path $dep 'bin');$env:PATH"
$env:CMAKE_PREFIX_PATH = $dep
$source = Join-Path $Workspace 'sources/postgresql'
$build = Join-Path $Workspace 'build/postgresql'
$perl = (Get-Command perl.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if ($perl) {
    $perlOS = & $perl -e 'print $^O'
    if ($LASTEXITCODE -or $perlOS.Trim() -ne 'MSWin32') { $perl = $null }
}
if (-not $perl) {
    $perl = Join-Path $env:VCPKG_INSTALLATION_ROOT 'downloads/tools/perl/5.42.2.1/perl/bin/perl.exe'
    if (Test-Path -LiteralPath $perl) {
        $perlOS = & $perl -e 'print $^O'
        if ($LASTEXITCODE -or $perlOS.Trim() -ne 'MSWin32') { $perl = $null }
    } else {
        $perl = $null
    }
}
if (-not $perl) { throw 'A native Windows Perl is required; install one or restore vcpkg portable Perl 5.42.2.1' }
$featureArgs = @("--prefix=$(Join-Path $Workspace 'postgresql')", '--buildtype=debugoptimized', "-DPERL=$perl", '-Dicu=enabled', '-Dlz4=enabled', '-Dzstd=enabled', '-Dzlib=enabled', '-Dssl=openssl', '-Dlibxml=enabled', '-Dlibxslt=enabled', '-Duuid=none', '-Dreadline=disabled', '-Dplperl=disabled', '-Dplpython=disabled', '-Dpltcl=disabled', '-Dgssapi=disabled', '-Dldap=disabled', '-Dpam=disabled', '-Dbonjour=disabled', '-Dlibcurl=disabled', '-Dlibnuma=disabled', '-Dliburing=disabled', '-Dselinux=disabled', '-Dbsd_auth=disabled', '-Dsystemd=disabled', '-Dnls=disabled', '-Dtap_tests=disabled', '-Ddocs=disabled', '-Ddocs_pdf=disabled', "-Dextra_include_dirs=$(Join-Path $dep 'include')", "-Dextra_lib_dirs=$(Join-Path $dep 'lib')")
$python = Join-Path $env:PG_WINDOWS_TOOLS 'python/python.exe'
& $python (Join-Path $PSScriptRoot 'internal/patch-windows-zic.py') $source
if ($LASTEXITCODE) { throw 'PostgreSQL runnable zic patch failed' }
$crossFile = Join-Path $PSScriptRoot 'internal/windows-x86_64-cross.ini'
& meson setup $build $source --cross-file $crossFile @featureArgs
if ($LASTEXITCODE) { throw 'PostgreSQL Meson configuration failed' }
& meson compile -C $build
if ($LASTEXITCODE) { throw 'PostgreSQL compilation failed' }
& meson install -C $build
if ($LASTEXITCODE) { throw 'PostgreSQL installation failed' }
