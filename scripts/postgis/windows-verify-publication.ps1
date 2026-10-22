param([Parameter(Mandatory=$true)][string]$CoreDirectory,[Parameter(Mandatory=$true)][string]$ExtensionDirectory,[Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$true
$platform='windows-x86_64'; $version='3.6.4'
$coreCandidates=@(Get-ChildItem $CoreDirectory -File | Where-Object { $_.Name -match '^postgresql-(15\.19|16\.15|17\.11|18\.6)-windows-x86_64\.tar\.gz$' })
if($coreCandidates.Count -ne 1){throw 'Core directory must contain exactly one supported PostgreSQL archive'}
$core=$coreCandidates[0].FullName
$pg=[regex]::Match($coreCandidates[0].Name,'^postgresql-(15\.19|16\.15|17\.11|18\.6)-').Groups[1].Value
$extension=Join-Path $ExtensionDirectory "postgis-$version-postgresql-$pg-$platform.tar.gz"
if(-not (Test-Path $extension -PathType Leaf)){throw "PostGIS archive does not match selected PostgreSQL $pg core"}
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
foreach($archive in @($core,$extension)) {
  $line=(Get-Content "$archive.sha256" -Raw).Trim() -split '\s+',2
  $name=''; if($line.Count -eq 2){$name=$line[1];if($name.StartsWith('*')){$name=$name.Substring(1)}}
  if($line.Count -ne 2 -or $line[0] -notmatch '^[0-9a-fA-F]{64}$' -or $name -ne (Split-Path $archive -Leaf) -or (Get-FileHash $archive -Algorithm SHA256).Hash -ne $line[0]) { throw "Invalid archive digest: $archive" }
}
python tools/license_pointer.py verify $extension postgis
if($LASTEXITCODE -ne 0){throw 'PostGIS licence pointer is invalid'}
$coreHash=(Get-FileHash $core -Algorithm SHA256).Hash.ToLowerInvariant()
$extensionHash=(Get-FileHash $extension -Algorithm SHA256).Hash.ToLowerInvariant()
$work=Join-Path $env:RUNNER_TEMP 'postgis-windows-publication'
$coreExtract=Join-Path $work core; $extensionExtract=Join-Path $work extension; $install=Join-Path $work relocated
New-Item -ItemType Directory -Force $coreExtract,$extensionExtract,$install | Out-Null
tar.exe -xzf $core -C $coreExtract; tar.exe -xzf $extension -C $extensionExtract
$metadata=Get-Content (Join-Path $extensionExtract 'metadata.json') -Raw | ConvertFrom-Json
if($metadata.project -ne 'PostGIS' -or $metadata.version -ne $version -or $metadata.postgresql_version -ne $pg -or $metadata.core_archive.sha256 -ne $coreHash -or $metadata.configuration_prerequisites -isnot [array] -or $metadata.configuration_prerequisites.Count -ne 0 -or $metadata.runtime_prerequisites -isnot [array] -or $metadata.runtime_prerequisites.Count -ne 0){throw 'PostGIS metadata does not bind this selected core or its prerequisite fields'}
Copy-Item (Join-Path $coreExtract 'postgresql') $install -Recurse
$pgRoot=Join-Path $install postgresql
Get-ChildItem (Join-Path $extensionExtract postgis) -Recurse -File | Where-Object Name -ne 'metadata.json' | ForEach-Object {
  $relative=$_.FullName.Substring((Join-Path $extensionExtract postgis).Length).TrimStart('\','/')
  $target=Join-Path $pgRoot $relative; New-Item -ItemType Directory -Force (Split-Path $target -Parent) | Out-Null
  if(Test-Path $target -PathType Leaf){if((Get-FileHash $_.FullName).Hash -ne (Get-FileHash $target).Hash){throw "Extension overwrites a different core file: $relative"}}
  Copy-Item $_.FullName $target -Force
}
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
if(-not (Test-Path $vswhere -PathType Leaf)){throw 'Visual Studio vswhere.exe is missing on the verifier'}
$vsRoot=(& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath).Trim()
if($LASTEXITCODE -ne 0 -or -not $vsRoot){throw 'The Windows verifier has no x64 dumpbin tool'}
$dumpbin=Get-ChildItem (Join-Path $vsRoot 'VC/Tools/MSVC') -Filter dumpbin.exe -Recurse -File | Select-Object -First 1 -ExpandProperty FullName
if(-not $dumpbin){throw 'The Windows verifier has no dumpbin.exe'}
python tools/check_pe_dependencies.py $pgRoot --dumpbin $dumpbin --archive $core --archive $extension --report (Join-Path $ExtensionDirectory pe-dependency-analysis.json)
if($LASTEXITCODE -ne 0){throw 'Final archive PE dependency analysis failed'}
$env:PATH="$(Join-Path $pgRoot bin);$env:SystemRoot\System32;$env:SystemRoot"
$env:GDAL_DATA=Join-Path $pgRoot share/gdal; $env:PROJ_DATA=Join-Path $pgRoot share/proj; $env:PROJ_LIB=$env:PROJ_DATA
$env:PGHOST='127.0.0.1'; $env:PGUSER='postgres'; $env:PGDATABASE='postgres'; $env:PGSSLMODE='disable'
$listener=[System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,0); $listener.Start(); $env:PGPORT=[string]$listener.LocalEndpoint.Port; $listener.Stop()
& (Join-Path $pgRoot bin/initdb.exe) -D (Join-Path $work cluster) -U postgres -A trust --encoding=UTF8 --no-instructions 2>&1 | Tee-Object (Join-Path $OutputDirectory initdb.log)
if($LASTEXITCODE -ne 0){throw 'initdb failed'}
& (Join-Path $pgRoot bin/pg_ctl.exe) -D (Join-Path $work cluster) -l (Join-Path $OutputDirectory server.log) -o "-p $env:PGPORT -h 127.0.0.1" -w start
try {
  & (Join-Path $pgRoot bin/psql.exe) -X -v ON_ERROR_STOP=1 -d postgres -f scripts/postgis/probe.sql 2>&1 | Tee-Object (Join-Path $OutputDirectory probe-output.txt)
  if($LASTEXITCODE -ne 0){throw 'PostGIS SQL probe failed'}
  $pe=Join-Path $ExtensionDirectory pe-dependency-analysis.json
  @{passed=$true;architecture='x86_64';inspected_files=(Get-Content $pe -Raw|ConvertFrom-Json).inspected_files;pe_dependency_analysis_sha256=(Get-FileHash $pe -Algorithm SHA256).Hash.ToLowerInvariant();archives=@(@{basename=(Split-Path $core -Leaf);sha256=$coreHash},@{basename=(Split-Path $extension -Leaf);sha256=$extensionHash})}|ConvertTo-Json -Depth 5|Set-Content -Encoding utf8 (Join-Path $ExtensionDirectory static-analysis.json)
} finally { & (Join-Path $pgRoot bin/pg_ctl.exe) -D (Join-Path $work cluster) -m immediate stop 2>$null }
