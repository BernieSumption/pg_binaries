param([string]$Tools = (Join-Path $env:SystemDrive 'pg-binaries-tools'), [string]$Package = 'postgresql')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$downloadTimeoutSeconds = 300
$env:PG_WINDOWS_TOOLS = $Tools
New-Item -ItemType Directory -Force $Tools | Out-Null
function Write-Stage([string]$Name, [string]$State) {
    $timestamp = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
    Write-Host "[$timestamp] $Name $State"
}
function Run([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -notin @(0, 3010)) { throw "$Program failed: $LASTEXITCODE" }
}
# winget validates official installer hashes against its signed package manifests.
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    Write-Stage 'Install Git' 'started'
    Run winget @('install', '--id', 'Git.Git', '--exact', '--silent', '--accept-package-agreements', '--accept-source-agreements')
    $env:PATH = "$(Join-Path $env:ProgramFiles 'Git/cmd');$env:PATH"
    Write-Stage 'Install Git' 'completed'
}
$python = Join-Path $Tools 'python/python.exe'
if (-not (Test-Path $python)) {
    $installer = Join-Path $Tools 'python-3.13.3.exe'
    if (-not (Test-Path $installer)) {
        Write-Stage 'Download Python installer' 'started'
        Invoke-WebRequest https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe -OutFile $installer -TimeoutSec $downloadTimeoutSeconds
        Write-Stage 'Download Python installer' 'completed'
    }
    Write-Stage 'Verify Python installer signature' 'started'
    $signature = Get-AuthenticodeSignature $installer
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') { throw 'Invalid Python installer signature' }
    Write-Stage 'Verify Python installer signature' 'completed'
    Write-Stage 'Install Python' 'started'
    $process = Start-Process $installer -ArgumentList @('/quiet', 'InstallAllUsers=0', "TargetDir=`"$(Join-Path $Tools 'python')`"", 'Include_test=0', 'PrependPath=0') -Wait -PassThru
    if ($process.ExitCode) { throw 'Python installation failed' }
    Write-Stage 'Install Python' 'completed'
}
Write-Stage 'Install pinned Python build tools' 'started'
Run $python @('-m', 'pip', 'install', '--disable-pip-version-check', 'meson==1.7.2', 'ninja==1.11.1.4', 'cmake==3.31.6', 'pkgconf==2.3.0.post2')
Write-Stage 'Install pinned Python build tools' 'completed'
Write-Stage 'Check Perl availability' 'started'
$perlAvailable = [bool](Get-Command perl.exe -ErrorAction SilentlyContinue)
Write-Stage 'Check Perl availability' 'completed'
if (-not $perlAvailable) {
    Write-Stage 'Install Strawberry Perl' 'started'
    Run winget @('install', '--id', 'StrawberryPerl.StrawberryPerl', '--exact', '--silent', '--accept-package-agreements', '--accept-source-agreements')
    $env:PATH = "C:/Strawberry/perl/bin;C:/Strawberry/c/bin;$env:PATH"
    Write-Stage 'Install Strawberry Perl' 'completed'
}
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$complete = $null
$existing = $null
$hasCpp = $false
Write-Stage 'Check Visual Studio C++ and Clang components' 'started'
if (Test-Path $vswhere) {
    Write-Stage 'Query Visual Studio for the complete C++ and Clang toolchain' 'started'
    $complete = & $vswhere -latest -version '[17.0,18.0)' -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 Microsoft.VisualStudio.Component.VC.Llvm.Clang -property installationPath
    Write-Stage 'Query Visual Studio for the complete C++ and Clang toolchain' 'completed'
    Write-Stage 'Query Visual Studio for the C++ toolchain' 'started'
    $existing = & $vswhere -latest -version '[17.0,18.0)' -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    Write-Stage 'Query Visual Studio for the C++ toolchain' 'completed'
    $hasCpp = [bool]$existing
    if (-not $existing) {
        Write-Stage 'Query Visual Studio Build Tools installation' 'started'
        $existing = & $vswhere -latest -version '[17.0,18.0)' -products Microsoft.VisualStudio.Product.BuildTools -property installationPath
        Write-Stage 'Query Visual Studio Build Tools installation' 'completed'
    }
}
Write-Stage 'Check Visual Studio C++ and Clang components' 'completed'
if (-not $complete) {
    if ($existing) {
        $installer = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/setup.exe'
        $options = @('modify', '--installPath', "`"$existing`"", '--quiet', '--norestart', '--add', 'Microsoft.VisualStudio.Component.VC.Llvm.Clang')
        if (-not $hasCpp) { $options += @('--add', 'Microsoft.VisualStudio.Workload.VCTools', '--includeRecommended') }
        Write-Stage 'Install Visual Studio C++ and Clang components' 'started'
        $process = Start-Process $installer -ArgumentList $options -Wait -PassThru
        if ($process.ExitCode -notin @(0, 3010)) { throw "Visual Studio component installation failed: $($process.ExitCode)" }
        Write-Stage 'Install Visual Studio C++ and Clang components' 'completed'
    } else {
        Write-Stage 'Install Visual Studio Build Tools' 'started'
        Run winget @('install', '--id', 'Microsoft.VisualStudio.2022.BuildTools', '--exact', '--silent', '--accept-package-agreements', '--accept-source-agreements', '--override', '--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Llvm.Clang --includeRecommended')
        Write-Stage 'Install Visual Studio Build Tools' 'completed'
    }
}
$zip = Join-Path $Tools 'winflexbison.zip'
if (-not (Test-Path $zip)) {
    Write-Stage 'Download WinFlexBison archive' 'started'
    Invoke-WebRequest https://github.com/lexxmark/winflexbison/releases/download/v2.5.25/win_flex_bison-2.5.25.zip -OutFile $zip -TimeoutSec $downloadTimeoutSeconds
    Write-Stage 'Download WinFlexBison archive' 'completed'
}
Write-Stage 'Verify WinFlexBison archive checksum' 'started'
if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne '8d324b62be33604b2c45ad1dd34ab93d722534448f55a16ca7292de32b6ac135') { throw 'WinFlexBison checksum mismatch' }
Write-Stage 'Verify WinFlexBison archive checksum' 'completed'
if (-not (Test-Path (Join-Path $Tools 'winflexbison/win_flex.exe'))) {
    Write-Stage 'Extract WinFlexBison archive' 'started'
    Expand-Archive $zip -DestinationPath (Join-Path $Tools 'winflexbison') -Force
    Write-Stage 'Extract WinFlexBison archive' 'completed'
}
Write-Stage 'Validate pinned vcpkg revision' 'started'
$revision = (Get-Content (Join-Path $PSScriptRoot '../../packages/postgresql/internal/vcpkg-commit.txt') -Raw).Trim()
if ($revision -notmatch '^[0-9a-f]{40}$') { throw 'Invalid PostgreSQL vcpkg commit pin' }
Write-Stage 'Validate pinned vcpkg revision' 'completed'
$vcpkg = Join-Path $Tools "vcpkg-$revision"
if (-not (Test-Path (Join-Path $vcpkg '.git'))) {
    Write-Stage 'Initialise vcpkg checkout' 'started'
    Run git @('init', $vcpkg)
    Run git @('-C', $vcpkg, 'remote', 'add', 'origin', 'https://github.com/microsoft/vcpkg.git')
    Write-Stage 'Initialise vcpkg checkout' 'completed'
    Write-Stage 'Fetch pinned vcpkg revision' 'started'
    Run git @('-C', $vcpkg, 'fetch', '--depth=1', 'origin', $revision)
    Write-Stage 'Fetch pinned vcpkg revision' 'completed'
    Write-Stage 'Check out pinned vcpkg revision' 'started'
    Run git @('-C', $vcpkg, 'checkout', '--detach', 'FETCH_HEAD')
    Write-Stage 'Check out pinned vcpkg revision' 'completed'
}
Write-Stage 'Verify vcpkg checkout revision' 'started'
if ((& git -C $vcpkg rev-parse HEAD).Trim() -ne $revision) { throw 'vcpkg revision mismatch' }
Write-Stage 'Verify vcpkg checkout revision' 'completed'
if (-not (Test-Path (Join-Path $vcpkg 'vcpkg.exe'))) {
    Write-Stage 'Bootstrap vcpkg executable' 'started'
    Run (Join-Path $vcpkg 'bootstrap-vcpkg.bat') @('-disableMetrics')
    Write-Stage 'Bootstrap vcpkg executable' 'completed'
}
if ($Package -eq 'postgis') {
    $msys = Join-Path $Tools 'msys64'
    $bash = Join-Path $msys 'usr/bin/bash.exe'
    if (-not (Test-Path $bash)) {
        $archive = Join-Path $Tools 'msys2-base-x86_64-20260927.tar.xz'
        if (-not (Test-Path $archive)) {
            Write-Stage 'Download MSYS2 base archive' 'started'
            Invoke-WebRequest https://github.com/msys2/msys2-installer/releases/download/2026-09-27/msys2-base-x86_64-20260927.tar.xz -OutFile $archive -TimeoutSec $downloadTimeoutSeconds
            Write-Stage 'Download MSYS2 base archive' 'completed'
        }
        Write-Stage 'Verify MSYS2 base archive checksum' 'started'
        if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'ea2f31a0b6ade63914ce441ffb022f0f6aa96982bfefa2326460a26d5fb01322') { throw 'MSYS2 archive checksum mismatch' }
        Write-Stage 'Verify MSYS2 base archive checksum' 'completed'
        Write-Stage 'Extract MSYS2 base archive' 'started'
        Run tar.exe @('-xJf', $archive, '-C', $Tools)
        Write-Stage 'Extract MSYS2 base archive' 'completed'
        Write-Stage 'Initialise MSYS2 login shell' 'started'
        Run $bash @('--login', '-c', 'true')
        Write-Stage 'Initialise MSYS2 login shell' 'completed'
        Write-Stage 'Update MSYS2 packages (first pass)' 'started'
        Run $bash @('--login', '-c', 'pacman -Syu --noconfirm')
        Write-Stage 'Update MSYS2 packages (first pass)' 'completed'
        Write-Stage 'Update MSYS2 packages (second pass)' 'started'
        Run $bash @('--login', '-c', 'pacman -Syu --noconfirm')
        Write-Stage 'Update MSYS2 packages (second pass)' 'completed'
    }
    $env:MSYSTEM = 'MINGW64'
    $env:MSYS2_PATH_TYPE = 'strict'
    $repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
    $packages = @(Get-Content (Join-Path $repo 'packages/postgis/internal/dependencies/windows-packages.txt') | Where-Object { $_ })
    Write-Stage 'Query required MSYS2 packages' 'started'
    & (Join-Path $msys 'usr/bin/pacman.exe') -Q @packages *> $null
    $packagesMissing = $LASTEXITCODE -ne 0
    if ($packagesMissing) {
        Write-Stage 'Query required MSYS2 packages' 'completed; installation required'
        Write-Stage 'Install required MSYS2 packages' 'started'
        Run $bash @('--login', '-c', ('pacman -S --needed --noconfirm ' + ($packages -join ' ')))
        Write-Stage 'Install required MSYS2 packages' 'completed'
    } else {
        Write-Stage 'Query required MSYS2 packages' 'completed; all installed'
    }
}
. (Join-Path $PSScriptRoot 'environment.ps1')
