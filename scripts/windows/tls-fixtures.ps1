function New-PilotTlsFixtures([string]$directory) {
  New-Item -ItemType Directory -Force $directory | Out-Null
  $caKey = [System.Security.Cryptography.RSA]::Create(2048)
  $ca = $null
  try {
    $caRequest = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
      'CN=pilot-ca', $caKey, [System.Security.Cryptography.HashAlgorithmName]::SHA256,
      [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)
    $caRequest.CertificateExtensions.Add(
      [System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($true, $false, 0, $true))
    $caRequest.CertificateExtensions.Add(
      [System.Security.Cryptography.X509Certificates.X509KeyUsageExtension]::new(
        [System.Security.Cryptography.X509Certificates.X509KeyUsageFlags]::KeyCertSign, $true))
    $start = [DateTimeOffset]::UtcNow.AddMinutes(-5)
    $end = $start.AddDays(1)
    $ca = $caRequest.CreateSelfSigned($start, $end)
    Set-Content -Encoding ascii -Path (Join-Path $directory 'ca.crt') -Value $ca.ExportCertificatePem()
    foreach ($peer in @('server', 'client')) {
      $key = [System.Security.Cryptography.RSA]::Create(2048)
      $certificate = $null
      try {
        $commonName = if ($peer -eq 'server') { 'localhost' } else { 'postgres' }
        $request = [System.Security.Cryptography.X509Certificates.CertificateRequest]::new(
          "CN=$commonName", $key, [System.Security.Cryptography.HashAlgorithmName]::SHA256,
          [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)
        $request.CertificateExtensions.Add(
          [System.Security.Cryptography.X509Certificates.X509BasicConstraintsExtension]::new($false, $false, 0, $true))
        $serial = [System.Security.Cryptography.RandomNumberGenerator]::GetBytes(16)
        $certificate = $request.Create($ca, $start, $end.AddMinutes(-1), $serial)
        Set-Content -Encoding ascii -Path (Join-Path $directory "$peer.crt") -Value $certificate.ExportCertificatePem()
        Set-Content -Encoding ascii -Path (Join-Path $directory "$peer.key") -Value $key.ExportPkcs8PrivateKeyPem()
      } finally {
        if ($certificate) { $certificate.Dispose() }
        $key.Dispose()
      }
    }
  } finally {
    if ($ca) { $ca.Dispose() }
    $caKey.Dispose()
  }
}
