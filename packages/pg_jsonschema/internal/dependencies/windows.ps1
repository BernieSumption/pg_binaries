function Get-PgJsonschemaToolchainPins {
    $pins = @{}
    foreach ($line in Get-Content (Join-Path $PSScriptRoot 'toolchain.sh')) {
        if ($line -match '^([a-z_]+)=([0-9.]+)$') { $pins[$Matches[1]] = $Matches[2] }
    }
    if (-not $pins.ContainsKey('rust_version') -or -not $pins.ContainsKey('pgrx_version')) {
        throw 'Could not read pinned Rust and cargo-pgrx versions from internal/dependencies/toolchain.sh'
    }
    return $pins
}

function Test-X64Pe([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $reader = [IO.BinaryReader]::new($stream)
    try {
        if ($stream.Length -lt 64) { return $false }
        $stream.Position = 0x3c
        $peOffset = $reader.ReadInt32()
        if ($peOffset -lt 0 -or $peOffset + 6 -gt $stream.Length) { return $false }
        $stream.Position = $peOffset
        $signature = $reader.ReadBytes(4)
        if ($signature[0] -ne 0x50 -or $signature[1] -ne 0x45 -or $signature[2] -ne 0 -or $signature[3] -ne 0) { return $false }
        return $reader.ReadUInt16() -eq 0x8664
    } finally {
        $reader.Dispose()
        $stream.Dispose()
    }
}

function Set-PgJsonschemaWindowsEnvironment([string]$Workspace, [hashtable]$Pins) {
    $rustRoot = Join-Path $env:PG_WINDOWS_TOOLS 'rust'
    $env:CARGO_HOME = Join-Path $rustRoot 'cargo'
    $env:RUSTUP_HOME = Join-Path $rustRoot 'rustup'
    $env:CARGO_TARGET_DIR = Join-Path $Workspace 'build/target'
    $env:PGRX_HOME = Join-Path $Workspace 'build/pgrx'
    $existingBuildFlags = @($env:PGRX_BUILD_FLAGS -split '\s+' | Where-Object { $_ })
    $env:PGRX_BUILD_FLAGS = (@('--locked') + $existingBuildFlags | Select-Object -Unique) -join ' '
    $pgrxRoot = Join-Path $env:CARGO_HOME "pg-binaries-tools/cargo-pgrx-$($Pins['pgrx_version'])-rust-$($Pins['rust_version'])"
    $rustup = Join-Path $env:CARGO_HOME 'bin/rustup.exe'
    $cargoPgrx = Join-Path $pgrxRoot 'bin/cargo-pgrx.exe'
    foreach ($path in @($rustup, $cargoPgrx)) {
        if (-not (Test-Path $path -PathType Leaf)) { throw "Cached Rust build tool is missing: $path; rerun the package dependency phase" }
    }
    $env:PATH = "$(Join-Path $pgrxRoot 'bin');$(Join-Path $env:CARGO_HOME 'bin');$env:PATH"

    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    if (-not (Test-Path $vswhere -PathType Leaf)) { throw 'Visual Studio vswhere.exe is missing' }
    $vsRoot = (& $vswhere '-latest' '-products' '*' '-requires' 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64' '-property' 'installationPath').Trim()
    if ($LASTEXITCODE -ne 0 -or -not $vsRoot) { throw 'The x64 MSVC toolchain is missing' }
    $clangCandidates = @(
        (Join-Path $vsRoot 'VC/Tools/Llvm/x64/bin'),
        (Join-Path $vsRoot 'VC/Tools/Llvm/bin'),
        (Join-Path $env:ProgramFiles 'LLVM/bin'),
        (Join-Path ${env:ProgramFiles(x86)} 'LLVM/bin')
    )
    $clangDirectories = @($clangCandidates | Where-Object { Test-Path (Join-Path $_ 'libclang.dll') })
    $x64Clang = @($clangDirectories | Where-Object { Test-X64Pe (Join-Path $_ 'libclang.dll') })
    if (-not $x64Clang.Count) {
        $examined = if ($clangDirectories.Count) { $clangDirectories -join ', ' } else { $clangCandidates -join ', ' }
        throw "Bindgen requires an x64 libclang.dll for the x86_64 Rust toolchain; no x64 DLL was found. Checked: $examined. Install the x64 C++ Clang tools or an x64 LLVM package."
    }
    $env:LIBCLANG_PATH = $x64Clang[0]
    return $rustup
}

function Initialize-PgJsonschemaWindowsToolchain([string]$Workspace, [hashtable]$Pins, [string]$PgConfig) {
    $rustRoot = Join-Path $env:PG_WINDOWS_TOOLS 'rust'
    $env:CARGO_HOME = Join-Path $rustRoot 'cargo'
    $env:RUSTUP_HOME = Join-Path $rustRoot 'rustup'
    New-Item -ItemType Directory -Force $env:CARGO_HOME,$env:RUSTUP_HOME | Out-Null
    $env:PATH = "$(Join-Path $env:CARGO_HOME 'bin');$env:PATH"
    $rustup = Join-Path $env:CARGO_HOME 'bin/rustup.exe'
    if (-not (Test-Path $rustup -PathType Leaf)) {
        $installer = Join-Path $rustRoot 'rustup-init-x86_64-pc-windows-msvc.exe'
        $installerUrl = 'https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe'
        $temporaryInstaller = "$installer.download"
        Invoke-WebRequest -Uri $installerUrl -OutFile $temporaryInstaller
        $checksum = (Invoke-WebRequest -Uri "$installerUrl.sha256").Content.Trim() -split '\s+' | Select-Object -First 1
        if ($checksum -notmatch '^[0-9a-fA-F]{64}$' -or
            (Get-FileHash $temporaryInstaller -Algorithm SHA256).Hash -ine $checksum) {
            Remove-Item $temporaryInstaller -Force -ErrorAction SilentlyContinue
            throw 'Official rustup x86_64 installer SHA-256 verification failed'
        }
        Move-Item $temporaryInstaller $installer -Force
        & $installer '-y' '--no-modify-path' '--default-host' 'x86_64-pc-windows-msvc' '--default-toolchain' 'none' '--profile' 'minimal'
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $rustup -PathType Leaf)) { throw 'Could not install rustup into the persistent Rust tool cache' }
    }

    $rustVersion = $Pins['rust_version']
    $pgrxVersion = $Pins['pgrx_version']
    & $rustup 'set' 'default-host' 'x86_64-pc-windows-msvc'
    if ($LASTEXITCODE -ne 0) { throw 'Could not select the x86_64 MSVC Rust host' }
    & $rustup 'toolchain' 'install' $rustVersion '--profile' 'minimal' '--target' 'x86_64-pc-windows-msvc'
    if ($LASTEXITCODE -ne 0) { throw "Could not install pinned x86_64 MSVC Rust toolchain $rustVersion" }

    $env:CARGO_TARGET_DIR = Join-Path $Workspace 'build/target'
    $env:PGRX_HOME = Join-Path $Workspace 'build/pgrx'
    $existingBuildFlags = @($env:PGRX_BUILD_FLAGS -split '\s+' | Where-Object { $_ })
    $env:PGRX_BUILD_FLAGS = (@('--locked') + $existingBuildFlags | Select-Object -Unique) -join ' '
    New-Item -ItemType Directory -Force $env:CARGO_TARGET_DIR,$env:PGRX_HOME | Out-Null
    $pgrxRoot = Join-Path $env:CARGO_HOME "pg-binaries-tools/cargo-pgrx-$pgrxVersion-rust-$rustVersion"
    if (-not (Test-Path (Join-Path $pgrxRoot 'bin/cargo-pgrx.exe') -PathType Leaf)) {
        & $rustup 'run' $rustVersion 'cargo' 'install' 'cargo-pgrx' '--version' $pgrxVersion '--locked' '--root' $pgrxRoot
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $pgrxRoot 'bin/cargo-pgrx.exe') -PathType Leaf)) { throw "Could not install cargo-pgrx $pgrxVersion" }
    }
    $env:PATH = "$(Join-Path $pgrxRoot 'bin');$(Join-Path $env:CARGO_HOME 'bin');$env:PATH"
    Set-PgJsonschemaWindowsEnvironment $Workspace $Pins | Out-Null

    $pgVersion = (& $PgConfig '--version').Trim()
    if ($LASTEXITCODE -ne 0 -or $pgVersion -notmatch '^PostgreSQL\s+(\d+)') { throw "Could not determine PostgreSQL major version from pg_config: $pgVersion" }
    & $rustup 'run' $rustVersion 'cargo' 'pgrx' 'init' "--pg$($Matches[1])" $PgConfig
    if ($LASTEXITCODE -ne 0) { throw 'cargo pgrx init failed for the supplied PostgreSQL SDK' }
}
