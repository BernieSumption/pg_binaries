param(
  [Parameter(Mandatory = $true)]
  [string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$url = 'https://go.microsoft.com/fwlink/?LinkId=619296'
$sdkVersion = '10.0.10240.0'
$targetPrefix = "Lib/$sdkVersion/um/x64/"
$result = [ordered]@{
  schema_version = 1
  status = 'inconclusive'
  url = $url
  file = $null
  length = $null
  sha256 = $null
  signature = $null
  archive_listing = 'not_attempted'
  seven_zip = $null
  import_libraries_directly_extractable = $null
  matching_entries = @()
  error = $null
}

try {
  if (-not $env:RUNNER_TEMP -or -not (Test-Path $env:RUNNER_TEMP -PathType Container)) {
    throw 'RUNNER_TEMP must name an existing directory'
  }
  if (-not [IO.Path]::IsPathRooted($OutputPath)) {
    throw 'OutputPath must be an absolute path'
  }

  $installer = Join-Path $env:RUNNER_TEMP 'windows-sdk-10.0.10240.exe'
  $result.file = $installer
  Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing

  # Authenticode is checked before reading archive contents or recording file metadata.
  $auth = Get-AuthenticodeSignature -FilePath $installer
  $signer = if ($auth.SignerCertificate) { $auth.SignerCertificate.Subject } else { $null }
  $result.signature = [ordered]@{
    status = [string]$auth.Status
    signer_subject = $signer
    microsoft_publisher = [bool]($signer -and $signer -match '(?i)(^|\s)CN=Microsoft Corporation(?:,|$)')
  }
  if ($auth.Status -ne [System.Management.Automation.SignatureStatus]::Valid -or
      -not $result.signature.microsoft_publisher) {
    throw "SDK installer signature is not valid for Microsoft Corporation (status: $($auth.Status))"
  }

  $item = Get-Item -LiteralPath $installer
  $result.length = [long]$item.Length
  $result.sha256 = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()

  $sevenZipCommand = Get-Command 7z.exe -ErrorAction SilentlyContinue
  if (-not $sevenZipCommand) { $sevenZipCommand = Get-Command 7z -ErrorAction SilentlyContinue }
  if (-not $sevenZipCommand) {
    $defaultSevenZip = Join-Path $env:ProgramFiles '7-Zip\7z.exe'
    if (Test-Path -LiteralPath $defaultSevenZip -PathType Leaf) {
      $sevenZipCommand = Get-Item -LiteralPath $defaultSevenZip
    }
  }
  if (-not $sevenZipCommand) {
    $result.archive_listing = 'unavailable'
  } else {
    $sevenZipPath = if ($sevenZipCommand.Source) { $sevenZipCommand.Source } else { $sevenZipCommand.FullName }
    $result.seven_zip = $sevenZipPath
    $listing = @(& $sevenZipPath l -slt $installer 2>&1)
    $sevenZipExit = $LASTEXITCODE
    if ($sevenZipExit -ne 0) {
      $result.archive_listing = 'unsupported_or_failed'
    } else {
      $result.archive_listing = 'available'
      $entries = @($listing | ForEach-Object { [string]$_ } | Where-Object { $_ -match '^Path = ' } |
        ForEach-Object { $_.Substring(7) })
      $matches = @($entries | Where-Object {
        $_ -match ('(?i)(?:^|[\\/])' + [regex]::Escape($targetPrefix).Replace('/', '[\\/]') + '[^\\/]+\.lib$')
      })
      $result.matching_entries = $matches
      $result.import_libraries_directly_extractable = ($matches.Count -gt 0)
    }
  }

  if ($result.archive_listing -eq 'available') {
    $result.status = 'complete'
  }
} catch {
  $result.status = 'failed'
  $result.error = $_.Exception.Message
}

$parent = Split-Path -Parent $OutputPath
if ($parent -and -not (Test-Path $parent -PathType Container)) {
  New-Item -ItemType Directory -Path $parent -Force | Out-Null
}
$json = $result | ConvertTo-Json -Depth 6 -Compress
Set-Content -LiteralPath $OutputPath -Value $json -Encoding utf8
if ($result.status -eq 'failed') { exit 1 }
