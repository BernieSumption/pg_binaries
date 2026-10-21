param(
  [Parameter(Mandatory = $true)][string]$PostgresRoot,
  [Parameter(Mandatory = $true)][string]$ExtensionRoot
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

if (-not $env:VCToolsRedistDir) { throw 'VCToolsRedistDir is missing; run from the Visual Studio developer environment' }
$redist = Join-Path $env:VCToolsRedistDir 'x64'
if (-not (Test-Path $redist -PathType Container)) { throw "Visual C++ x64 redistributable directory is missing: $redist" }
$bin = Join-Path $PostgresRoot 'bin'
$bundled = @{}
$scanned = @{}
$runtimeName = '^(?:vcruntime|msvcp|concrt|vcomp|mfc|atl)\d[^\\/]*\.dll$'

do {
  $added = $false
  $peFiles = @(Get-ChildItem $PostgresRoot, $ExtensionRoot -Recurse -File | Where-Object { $_.Extension -in @('.exe', '.dll') })
  foreach ($file in $peFiles) {
    if ($scanned.ContainsKey($file.FullName)) { continue }
    $imports = & dumpbin /dependents $file.FullName
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect DLL imports of $($file.FullName)" }
    $scanned[$file.FullName] = $true
    foreach ($line in $imports) {
      $name = $line.Trim()
      if ($name -notmatch $runtimeName) { continue }
      $key = $name.ToLowerInvariant()
      if ($bundled.ContainsKey($key)) { continue }
      $source = @(Get-ChildItem $redist -Recurse -File -Filter $name | Where-Object { $_.Name -ieq $name })
      if ($source.Count -ne 1) { throw "Expected one redistributable x64 copy of $name; found $($source.Count)" }
      Copy-Item $source[0].FullName (Join-Path $bin $source[0].Name)
      $bundled[$key] = $source[0].Name
      $added = $true
    }
  }
} while ($added)

if (-not $bundled.ContainsKey('vcruntime140.dll')) { throw 'Expected PostgreSQL to import VCRUNTIME140.dll' }
$names = @($bundled.Values | Sort-Object)
$names
