$ErrorActionPreference = 'Stop'
if (-not $env:PG_WINDOWS_TOOLS) { $env:PG_WINDOWS_TOOLS = Join-Path $env:SystemDrive 'pg-binaries-tools' }
$env:VCPKG_INSTALLATION_ROOT = Join-Path $env:PG_WINDOWS_TOOLS 'vcpkg-9e593bb18ea69cc5095e012465dcd675a822ed0d'
$env:PATH = "C:/Strawberry/perl/bin;C:/Strawberry/c/bin;$(Join-Path $env:PG_WINDOWS_TOOLS 'python/Scripts');$(Join-Path $env:PG_WINDOWS_TOOLS 'python');$(Join-Path $env:PG_WINDOWS_TOOLS 'winflexbison');$env:PATH"
if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue) -or $env:VSCMD_ARG_TGT_ARCH -ne 'x64') {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    if (-not (Test-Path $vswhere)) { throw 'Visual Studio Installer is missing; run bootstrap.ps1' }
    $vs = & $vswhere -latest -version '[17.0,18.0)' -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $vs) { throw 'Visual Studio C++ Build Tools missing; run bootstrap.ps1' }
    $hostArch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') { 'arm64' } else { 'x64' }
    $devcmd = Join-Path $vs 'Common7/Tools/VsDevCmd.bat'
    & cmd.exe /s /c "`"`"$devcmd`" -no_logo -arch=x64 -host_arch=$hostArch >nul && set`"" | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') }
    }
    if ($LASTEXITCODE) { throw 'Visual Studio developer environment failed' }
}
if (-not $env:VCToolsRedistDir) { throw 'Visual Studio redistributable directory missing' }
$env:PG_WINDOWS_REDIST = Join-Path $env:VCToolsRedistDir 'x64/Microsoft.VC143.CRT'
if (-not (Test-Path $env:PG_WINDOWS_REDIST)) { throw "Visual Studio x64 CRT files are missing: $env:PG_WINDOWS_REDIST" }
if (-not $env:CC) { $env:CC = 'cl.exe' }
if (-not $env:CXX) { $env:CXX = 'cl.exe' }
if (-not $env:AR) { $env:AR = 'lib.exe' }
