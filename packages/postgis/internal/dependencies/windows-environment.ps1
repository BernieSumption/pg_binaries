function Invoke-PostGISWindowsRecipe([string]$OS, [string]$Arch, [string]$Workspace, [string]$Script) {
    if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'PostGIS expects windows x86_64' }
    $msys = $env:PG_MSYS2_ROOT
    if (-not $msys) {
        if (-not $env:PG_WINDOWS_TOOLS) { throw 'Set PG_WINDOWS_TOOLS or PG_MSYS2_ROOT to the prepared Windows tool environment' }
        $msys = Join-Path $env:PG_WINDOWS_TOOLS 'msys64'
    }
    $bash = Join-Path $msys 'usr/bin/bash.exe'
    if (-not (Test-Path $bash)) { throw "MSYS2 is missing at $msys; install the PostGIS Windows build packages first" }
    $env:MSYSTEM = 'MINGW64'
    $env:MSYS2_PATH_TYPE = 'strict'
    $env:CHERE_INVOKING = '1'
    & $bash --login ($Script.Replace('\', '/')) windows x86_64 ($Workspace.Replace('\', '/'))
    if ($LASTEXITCODE) { throw "PostGIS Windows recipe failed: $Script (exit $LASTEXITCODE)" }
}
