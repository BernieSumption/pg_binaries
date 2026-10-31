param([string]$OS, [string]$Arch, [string]$Workspace)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($OS -ne 'windows' -or $Arch -ne 'x86_64') { throw 'Expected windows x86_64' }

$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
. (Join-Path $repo 'platforms/windows/environment.ps1')
$source = Join-Path $Workspace 'sources/pgtap'
$pgConfig = Join-Path $Workspace 'postgresql/bin/pg_config.exe'
foreach ($path in @($source, $pgConfig)) {
    if (-not (Test-Path $path)) { throw "Required pgTAP build input is missing: $path" }
}

function Get-PgConfigValue([string]$Option) {
    $value = (& $pgConfig $Option).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $value) { throw "pg_config $Option failed" }
    return $value
}

function Get-RelativePath([string]$Root, [string]$Path) {
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd([char[]]@('\','/'))
    $fullPath = [IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($rootPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "PostgreSQL installation path is outside the workspace: $Path"
    }
    return $fullPath.Substring($rootPath.Length + 1)
}

$control = Join-Path $source 'pgtap.control'
$versionLine = Select-String -Path $control -Pattern "^default_version\s*=\s*'([^']+)'\s*$"
if (-not $versionLine) { throw 'pgTAP control file has no default_version' }
$version = $versionLine.Matches[0].Groups[1].Value
$versionParts = $version.Split('.')
$numericVersion = "$($versionParts[0]).$($versionParts[1])"
$sharedDir = Get-PgConfigValue '--sharedir'
$shareRelative = Get-RelativePath (Join-Path $Workspace 'postgresql') $sharedDir
$extensionPayload = Join-Path (Join-Path (Join-Path $Workspace 'payload') $shareRelative) 'extension'
New-Item -ItemType Directory -Force $extensionPayload | Out-Null

$sqlSource = Join-Path $source 'sql'
$template = Join-Path $sqlSource 'pgtap.sql.in'
if (-not (Test-Path $template -PathType Leaf)) { throw 'Upstream pgTAP SQL template is missing' }
$mainSql = [IO.File]::ReadAllText($template)
$mainSql = $mainSql.Replace('MODULE_PATHNAME', 'pgtap').Replace('__OS__', 'windows').Replace('__VERSION__', $numericVersion)
$mainPath = Join-Path $sqlSource 'pgtap.sql'
[IO.File]::WriteAllText($mainPath, $mainSql, [Text.UTF8Encoding]::new($false))

# Recreate the upstream static SQL input, then let its Perl generator split Core and Schema.
$staticDir = Join-Path $Workspace 'build/pgtap-static'
New-Item -ItemType Directory -Force (Join-Path $staticDir 'sql') | Out-Null
$staticMainPath = Join-Path $staticDir 'sql/pgtap.sql'
$staticSql = [IO.File]::ReadAllText($template)
$patches = @(Get-ChildItem (Join-Path $source 'compat') -File -Filter 'install-*.patch' | Sort-Object Name -Descending)
if ($patches.Count -eq 0) { throw 'Upstream pgTAP install patches are missing' }
$git = (Get-Command 'git.exe' -ErrorAction Stop).Source
[IO.File]::WriteAllText($staticMainPath, $staticSql, [Text.UTF8Encoding]::new($false))
foreach ($patch in $patches) {
    & $git '-C' $staticDir 'apply' '-p0' $patch.FullName
    if ($LASTEXITCODE -ne 0) { throw "Could not apply upstream pgTAP install patch $($patch.Name)" }
}
$staticSql = [IO.File]::ReadAllText($staticMainPath)
$staticSql = $staticSql.Replace('MODULE_PATHNAME', '$libdir/pgtap').Replace('__OS__', 'windows').Replace('__VERSION__', $numericVersion)
$staticPath = Join-Path $sqlSource 'pgtap-static.sql'
[IO.File]::WriteAllText($staticPath, $staticSql, [Text.UTF8Encoding]::new($false))

$perl = (Get-Command 'perl.exe' -ErrorAction Stop).Source
$generator = Join-Path $source 'compat/gencore'
foreach ($variant in @(@{ Name = 'core'; Invert = '0' }, @{ Name = 'schema'; Invert = '1' })) {
    $generatedPath = Join-Path $sqlSource "pgtap-$($variant.Name).sql"
    $perlCode = 'open STDOUT, q(>:raw), shift or die $!; exec $^X, shift, @ARGV or die $!;'
    & $perl '-e' $perlCode $generatedPath $generator $variant.Invert $staticPath
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $generatedPath -PathType Leaf)) { throw "Upstream pgTAP $($variant.Name) SQL generation failed" }
}

$uninstallPath = Join-Path $sqlSource 'uninstall_pgtap.sql'
$uninstallPerl = 'for (grep { /^CREATE /} reverse <>) { chomp; s/CREATE (OR REPLACE )?/DROP /; s/DROP (FUNCTION|VIEW|TYPE) /DROP $1 IF EXISTS /; s/ (DEFAULT|=)[ ]+[a-zA-Z0-9]+//g; print "$_;\n" }'
$uninstallCode = 'open STDOUT, q(>:raw), shift or die $!; exec $^X, q(-e), shift, @ARGV or die $!;'
& $perl '-e' $uninstallCode $uninstallPath $uninstallPerl $mainPath
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $uninstallPath -PathType Leaf)) { throw 'Upstream pgTAP uninstall SQL generation failed' }

Copy-Item $mainPath (Join-Path $sqlSource "pgtap--$version.sql") -Force
Copy-Item (Join-Path $sqlSource 'pgtap-core.sql') (Join-Path $sqlSource "pgtap-core--$version.sql") -Force
Copy-Item (Join-Path $sqlSource 'pgtap-schema.sql') (Join-Path $sqlSource "pgtap-schema--$version.sql") -Force
foreach ($input in Get-ChildItem $sqlSource -File -Filter '*.sql.in') {
    if ($input.Name -eq 'pgtap.sql.in') { continue }
    $output = $input.FullName.Substring(0, $input.FullName.Length - 3)
    Copy-Item $input.FullName $output -Force
}

Copy-Item $control $extensionPayload -Force
foreach ($file in Get-ChildItem $sqlSource -File -Filter '*.sql' | Where-Object { $_.Name -ne 'pgtap-static.sql' }) {
    Copy-Item $file.FullName $extensionPayload -Force
}
