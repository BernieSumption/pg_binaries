param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
$dependencies = Join-Path $Workspace 'build/dependencies'
& (Join-Path $env:VCPKG_INSTALLATION_ROOT 'vcpkg.exe') install --triplet x64-windows --x-install-root=$dependencies icu zlib lz4 zstd openssl libxml2 libxslt
if ($LASTEXITCODE) { throw 'vcpkg dependencies failed' }
$env:PKG_CONFIG_PATH = Join-Path $dependencies 'x64-windows/lib/pkgconfig'
$dep = Join-Path $dependencies 'x64-windows'
$env:PATH = "$(Join-Path $dep 'bin');$env:PATH"
$env:CMAKE_PREFIX_PATH = $dep
$build = Join-Path $Workspace 'build/postgresql'
$args = @('setup', $build, (Join-Path $Workspace 'sources/postgresql'), "--prefix=$(Join-Path $Workspace 'postgresql')", '--buildtype=debugoptimized', '-Dicu=enabled', '-Dlz4=enabled', '-Dzstd=enabled', '-Dzlib=enabled', '-Dssl=openssl', '-Dlibxml=enabled', '-Dlibxslt=enabled', '-Duuid=none', '-Dreadline=disabled', '-Dplperl=disabled', '-Dplpython=disabled', '-Dpltcl=disabled', '-Dgssapi=disabled', '-Dldap=disabled', '-Dpam=disabled', '-Dbonjour=disabled', '-Dlibcurl=disabled', '-Dlibnuma=disabled', '-Dliburing=disabled', '-Dselinux=disabled', '-Dbsd_auth=disabled', '-Dsystemd=disabled', '-Dnls=disabled', '-Dtap_tests=disabled', '-Ddocs=disabled', '-Ddocs_pdf=disabled', "-Dextra_include_dirs=$(Join-Path $dep 'include')", "-Dextra_lib_dirs=$(Join-Path $dep 'lib')")
& meson @args
if ($LASTEXITCODE) { throw 'PostgreSQL Meson configuration failed' }
& meson compile -C $build
if ($LASTEXITCODE) { throw 'PostgreSQL compilation failed' }
& meson install -C $build
if ($LASTEXITCODE) { throw 'PostgreSQL installation failed' }
