param([string]$Tools = (Join-Path $env:SystemDrive 'pg-binaries-tools'), [string]$Package = 'postgresql')
$ErrorActionPreference = 'Stop'
$env:PG_WINDOWS_TOOLS = $Tools
New-Item -ItemType Directory -Force $Tools | Out-Null
function Run([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -notin @(0, 3010)) { throw "$Program failed: $LASTEXITCODE" }
}
# winget validates official installer hashes against its signed package manifests.
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    Run winget @('install', '--id', 'Git.Git', '--exact', '--silent', '--accept-package-agreements', '--accept-source-agreements')
    $env:PATH = "$(Join-Path $env:ProgramFiles 'Git/cmd');$env:PATH"
}
$python = Join-Path $Tools 'python/python.exe'
if (-not (Test-Path $python)) {
    $installer = Join-Path $Tools 'python-3.13.3.exe'
    if (-not (Test-Path $installer)) { Invoke-WebRequest https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe -OutFile $installer }
    $signature = Get-AuthenticodeSignature $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') { throw 'Invalid Python installer signature' }
    $process = Start-Process $installer -ArgumentList @('/quiet', 'InstallAllUsers=0', "TargetDir=`"$(Join-Path $Tools 'python')`"", 'Include_test=0', 'PrependPath=0') -Wait -PassThru
    if ($process.ExitCode) { throw 'Python installation failed' }
}
Run $python @('-m', 'pip', 'install', '--disable-pip-version-check', 'meson==1.7.2', 'ninja==1.11.1.4', 'cmake==3.31.6', 'pkgconf==2.3.0.post2')
if (-not (Get-Command perl.exe -ErrorAction SilentlyContinue)) {
    Run winget @('install', '--id', 'StrawberryPerl.StrawberryPerl', '--exact', '--silent', '--accept-package-agreements', '--accept-source-agreements')
    $env:PATH = "C:/Strawberry/perl/bin;C:/Strawberry/c/bin;$env:PATH"
}
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$complete = $null
$existing = $null
$hasCpp = $false
if (Test-Path $vswhere) {
    $complete = & $vswhere -latest -version '[17.0,18.0)' -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 Microsoft.VisualStudio.Component.VC.Llvm.Clang -property installationPath
    $existing = & $vswhere -latest -version '[17.0,18.0)' -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    $hasCpp = [bool]$existing
    if (-not $existing) { $existing = & $vswhere -latest -version '[17.0,18.0)' -products Microsoft.VisualStudio.Product.BuildTools -property installationPath }
}
if (-not $complete) {
    if ($existing) {
        $installer = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/setup.exe'
        $options = @('modify', '--installPath', "`"$existing`"", '--quiet', '--norestart', '--add', 'Microsoft.VisualStudio.Component.VC.Llvm.Clang')
        if (-not $hasCpp) { $options += @('--add', 'Microsoft.VisualStudio.Workload.VCTools', '--includeRecommended') }
        $process = Start-Process $installer -ArgumentList $options -Wait -PassThru
        if ($process.ExitCode -notin @(0, 3010)) { throw "Visual Studio component installation failed: $($process.ExitCode)" }
    } else {
        Run winget @('install', '--id', 'Microsoft.VisualStudio.2022.BuildTools', '--exact', '--silent', '--accept-package-agreements', '--accept-source-agreements', '--override', '--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Llvm.Clang --includeRecommended')
    }
}
$zip = Join-Path $Tools 'winflexbison.zip'
if (-not (Test-Path $zip)) { Invoke-WebRequest https://github.com/lexxmark/winflexbison/releases/download/v2.5.25/win_flex_bison-2.5.25.zip -OutFile $zip }
if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne '8d324b62be33604b2c45ad1dd34ab93d722534448f55a16ca7292de32b6ac135') { throw 'WinFlexBison checksum mismatch' }
if (-not (Test-Path (Join-Path $Tools 'winflexbison/win_flex.exe'))) { Expand-Archive $zip -DestinationPath (Join-Path $Tools 'winflexbison') -Force }
$revision = (Get-Content (Join-Path $PSScriptRoot '../../packages/postgresql/internal/vcpkg-commit.txt') -Raw).Trim()
if ($revision -notmatch '^[0-9a-f]{40}$') { throw 'Invalid PostgreSQL vcpkg commit pin' }
$vcpkg = Join-Path $Tools "vcpkg-$revision"
if (-not (Test-Path (Join-Path $vcpkg '.git'))) {
    Run git @('init', $vcpkg)
    Run git @('-C', $vcpkg, 'remote', 'add', 'origin', 'https://github.com/microsoft/vcpkg.git')
    Run git @('-C', $vcpkg, 'fetch', '--depth=1', 'origin', $revision)
    Run git @('-C', $vcpkg, 'checkout', '--detach', 'FETCH_HEAD')
}
if ((& git -C $vcpkg rev-parse HEAD).Trim() -ne $revision) { throw 'vcpkg revision mismatch' }
if (-not (Test-Path (Join-Path $vcpkg 'vcpkg.exe'))) { Run (Join-Path $vcpkg 'bootstrap-vcpkg.bat') @('-disableMetrics') }
if ($Package -eq 'postgis') {
    $msys = Join-Path $Tools 'msys64'
    $bash = Join-Path $msys 'usr/bin/bash.exe'
    if (-not (Test-Path $bash)) {
        $archive = Join-Path $Tools 'msys2-base-x86_64-20260927.tar.xz'
        if (-not (Test-Path $archive)) {
            Invoke-WebRequest https://github.com/msys2/msys2-installer/releases/download/2026-09-27/msys2-base-x86_64-20260927.tar.xz -OutFile $archive
        }
        if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ea2f31a0b6ade63914ce441ffb022f0f6aa96982bfefa2326460a26d5fb01322') { throw 'MSYS2 archive checksum mismatch' }
        Run tar.exe @('-xJf', $archive, '-C', $Tools)
        Run $bash @('--login', '-c', 'true')
        Run $bash @('--login', '-c', 'pacman -Syu --noconfirm')
        Run $bash @('--login', '-c', 'pacman -Syu --noconfirm')
    }
    $env:MSYSTEM = 'MINGW64'
    $env:MSYS2_PATH_TYPE = 'strict'
    $repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
    $packages = @(Get-Content (Join-Path $repo 'packages/postgis/internal/dependencies/windows-packages.txt') | Where-Object { $_ })
    & (Join-Path $msys 'usr/bin/pacman.exe') -Q @packages *> $null
    if ($LASTEXITCODE) {
        Run $bash @('--login', '-c', ('pacman -S --needed --noconfirm ' + ($packages -join ' ')))
    }
}
. (Join-Path $PSScriptRoot 'environment.ps1')
