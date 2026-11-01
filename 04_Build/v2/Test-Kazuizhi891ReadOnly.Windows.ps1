Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$export = Join-Path $PSScriptRoot 'Export-Kazuizhi891ReadOnly.ps1'
$root = Join-Path $env:RUNNER_TEMP ('kz891-readonly-test-' + [guid]::NewGuid().ToString('N'))
$data = Join-Path $root 'data'
$output = Join-Path $root 'output'
New-Item -ItemType Directory -Path (Join-Path $data 'r8_13'), (Join-Path $data 'geo_validation'), (Join-Path $data 'r8_10'), (Join-Path $data 'r8_17') -Force | Out-Null

$asset = '{"assets":[{"id":"SEO-TEST","status":"PUBLISHED","public_url":"https://example.invalid/seo/test?token=SENSITIVE_QUERY","error":"Bearer SENSITIVE_BEARER","secret":"SENSITIVE_FIELD"}],"opportunities":[]}'
$queue = '{"tasks":[{"id":"GEO-TASK-TEST","status":"blocked_by_safety_gate","question_id":"GEO-TEST","answer":"SENSITIVE_ANSWER"}]}'
$bus = '{"status":"disconnected","last_error":"password=SENSITIVE_PASSWORD","access_token":"SENSITIVE_TOKEN"}'
$remote = '{"configured":true,"last_health_at":"2026-11-01T00:00:00Z","last_error":"Bearer SENSITIVE_REMOTE","shared_secret":"SENSITIVE_REMOTE_FIELD"}'
$asset | Set-Content -LiteralPath (Join-Path $data 'r8_13\seo_geo_growth.json') -Encoding UTF8
$queue | Set-Content -LiteralPath (Join-Path $data 'geo_validation\queue.json') -Encoding UTF8
$bus | Set-Content -LiteralPath (Join-Path $data 'r8_10\async_control_bus_state.json') -Encoding UTF8
$remote | Set-Content -LiteralPath (Join-Path $data 'r8_17\remote_agent.json') -Encoding UTF8

function Source-Hashes {
    @(Get-ChildItem -LiteralPath $data -Recurse -File | Sort-Object FullName | ForEach-Object {
        "{0}:{1}" -f $_.FullName, (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    })
}
$before = Source-Hashes
$global:KZTestRequests = @()

# The exporter's exact five HTTP calls are intercepted in this process. CI
# cannot contact the production site, a local service, or an external host.
function global:Invoke-WebRequest {
    param([string]$Uri, [string]$Method, [switch]$UseBasicParsing,
          [int]$TimeoutSec, [hashtable]$Headers)
    if ($Method -ne 'Get' -or -not $Uri.StartsWith('http://127.0.0.1:8876/api/')) {
        throw "Unexpected request: $Method $Uri"
    }
    $global:KZTestRequests += $Uri
    [pscustomobject]@{ StatusCode = 200; Content = '{"summary":{"public_pages":35}}' }
}

& $export -DataRoot $data -OutputDirectory $output | Out-Null
$after = Source-Hashes
if (Compare-Object $before $after) { throw 'Source JSON changed during export' }
if ($global:KZTestRequests.Count -ne 5) { throw "Expected five read-only GETs, got $($global:KZTestRequests.Count)" }

$reportPath = Join-Path $output 'Kazuizhi891-ReadOnly.json'
$hashPath = Join-Path $output 'SHA256SUMS.txt'
if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf) -or
    -not (Test-Path -LiteralPath $hashPath -PathType Leaf)) { throw 'Output not in the requested directory' }
$reportText = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8
foreach ($secret in @('SENSITIVE_QUERY','SENSITIVE_BEARER','SENSITIVE_FIELD','SENSITIVE_ANSWER','SENSITIVE_PASSWORD','SENSITIVE_TOKEN','SENSITIVE_REMOTE','SENSITIVE_REMOTE_FIELD')) {
    if ($reportText.Contains($secret)) { throw "Sensitive fixture leaked: $secret" }
}
$report = $reportText | ConvertFrom-Json
if ($report.files.seo.collections.assets.rows[0].id -ne 'SEO-TEST' -or
    $report.files.geo_queue.collections.tasks.rows[0].status -ne 'blocked_by_safety_gate' -or
    $report.files.remote_agent.status.configured -ne $true -or
    $report.api.seo.http_status -ne 200) { throw 'Expected identity/status/HTTP metadata missing' }
$recorded = Get-Content -LiteralPath $hashPath -Raw -Encoding ASCII
if (-not $recorded.Contains((Get-FileHash -LiteralPath $reportPath -Algorithm SHA256).Hash)) {
    throw 'Output SHA256 does not match'
}
try {
    & $export -DataRoot $data -BaseUrl 'https://example.invalid' -OutputDirectory (Join-Path $root 'invalid') | Out-Null
    throw 'Non-local BaseUrl was accepted'
} catch {
    if ($_.Exception.Message -eq 'Non-local BaseUrl was accepted') { throw }
}
if (Test-Path -LiteralPath (Join-Path $root 'invalid')) { throw 'Rejected endpoint created output' }
Write-Output 'PASS: Windows PowerShell read-only export, local GET isolation, redaction, output and SHA256'
