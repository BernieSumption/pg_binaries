param(
    [Parameter(Mandatory = $true)]
    [string]$PostgreSQLVersion
)

$ErrorActionPreference = 'Stop'

python -m pip install --disable-pip-version-check meson ninja
if ($LASTEXITCODE -ne 0) { throw 'Meson and Ninja installation failed' }

$archive = Join-Path $env:RUNNER_TEMP 'win_flex_bison-2.5.25.zip'
$tools = Join-Path $env:RUNNER_TEMP 'win_flex_bison-2.5.25'
Invoke-WebRequest 'https://github.com/lexxmark/winflexbison/releases/download/v2.5.25/win_flex_bison-2.5.25.zip' -OutFile $archive
$actual = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne '8d324b62be33604b2c45ad1dd34ab93d722534448f55a16ca7292de32b6ac135') {
    throw "WinFlexBison checksum mismatch: $actual"
}
Expand-Archive $archive -DestinationPath $tools
$flex = Get-ChildItem $tools -Recurse -Filter win_flex.exe | Select-Object -First 1
if (-not $flex -or -not (Test-Path (Join-Path $flex.DirectoryName 'win_bison.exe'))) {
    throw 'WinFlexBison executables missing from archive'
}
Add-Content -Path $env:GITHUB_PATH -Value $flex.DirectoryName

$vcpkgRevision = '9e593bb18ea69cc5095e012465dcd675a822ed0d'
$vcpkgRoot = Join-Path $env:RUNNER_TEMP "vcpkg-$vcpkgRevision"
git init $vcpkgRoot
if ($LASTEXITCODE -ne 0) { throw 'vcpkg repository initialization failed' }
git -C $vcpkgRoot remote add origin https://github.com/microsoft/vcpkg.git
if ($LASTEXITCODE -ne 0) { throw 'vcpkg remote configuration failed' }
git -C $vcpkgRoot fetch --depth=1 origin $vcpkgRevision
if ($LASTEXITCODE -ne 0) { throw 'vcpkg revision fetch failed' }
git -C $vcpkgRoot checkout --detach FETCH_HEAD
if ($LASTEXITCODE -ne 0) { throw 'vcpkg revision checkout failed' }
$actualRevision = (git -C $vcpkgRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'vcpkg revision verification failed' }
if ($actualRevision -ne $vcpkgRevision) { throw "vcpkg checkout revision mismatch: $actualRevision" }
& (Join-Path $vcpkgRoot 'bootstrap-vcpkg.bat') -disableMetrics
if ($LASTEXITCODE -ne 0) { throw 'vcpkg bootstrap failed' }
$env:VCPKG_INSTALLATION_ROOT = $vcpkgRoot
Add-Content -Path $env:GITHUB_ENV -Value "VCPKG_INSTALLATION_ROOT=$vcpkgRoot"
$opensslPort = if ($PostgreSQLVersion -eq '15.19') { 'openssl[tools]:x64-windows' } else { 'openssl:x64-windows' }
& (Join-Path $vcpkgRoot 'vcpkg.exe') install icu:x64-windows zlib:x64-windows lz4:x64-windows zstd:x64-windows $opensslPort libxml2:x64-windows libxslt:x64-windows
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL library installation failed' }
