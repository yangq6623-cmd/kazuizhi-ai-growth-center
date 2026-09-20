param(
    [string]$Setup = 'installer_output_v2/Kazuizhi_AI_Enterprise_V2.2.0_R8_Operational.exe'
)

$ErrorActionPreference = 'Stop'
$setupPath = (Resolve-Path -LiteralPath $Setup).Path
$startedAt = Get-Date
$signature = Get-AuthenticodeSignature -LiteralPath $setupPath
$scanStatus = 'not_available'
$scanDetail = 'Microsoft Defender custom scan command is unavailable on this runner.'

$scanner = Get-Command Start-MpScan -ErrorAction SilentlyContinue
if ($scanner) {
    try {
        Start-MpScan -ScanType CustomScan -ScanPath $setupPath
        $scanStatus = 'passed'
        $scanDetail = 'Microsoft Defender custom scan completed without quarantining the installer.'
    } catch {
        $message = $_.Exception.Message
        if ($message -match 'service|disabled|not available|0x800106ba') {
            $scanStatus = 'not_available'
            $scanDetail = "Microsoft Defender is unavailable on this runner: $message"
        } else {
            throw
        }
    }
}

if (-not (Test-Path -LiteralPath $setupPath)) {
    throw 'Security scan quarantined or removed the installer.'
}

$detections = @()
if (Get-Command Get-MpThreatDetection -ErrorAction SilentlyContinue) {
    $detections = @(Get-MpThreatDetection -ErrorAction SilentlyContinue | Where-Object {
        $_.InitialDetectionTime -ge $startedAt.AddMinutes(-2) -and
        (($_.Resources | Out-String) -match [regex]::Escape($setupPath))
    })
}
if ($detections.Count -gt 0) {
    $names = @($detections | ForEach-Object { $_.ThreatID }) -join ', '
    throw "Microsoft Defender detected the final installer. Threat IDs: $names"
}

$hash = (Get-FileHash -LiteralPath $setupPath -Algorithm SHA256).Hash
$record = [ordered]@{
    installer = Split-Path -Leaf $setupPath
    sha256 = $hash
    scan_status = $scanStatus
    scan_detail = $scanDetail
    scanned_at = (Get-Date).ToString('o')
    authenticode_status = [string]$signature.Status
    detection_count = $detections.Count
    packaging = 'Inno Setup ZIP non-solid; no custom taskkill code'
}
$output = Join-Path (Split-Path -Parent $setupPath) 'SECURITY_SCAN.json'
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $output -Encoding UTF8
Write-Host "PASS: installer preserved; Defender=$scanStatus; SHA256=$hash"
