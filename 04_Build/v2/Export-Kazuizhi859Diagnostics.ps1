[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:8876',
    [string]$OutputDirectory = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Kazuizhi859Diagnostics')
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Read-only collector: every application request below is GET. The script does
# not send cookies/authorization headers, change configuration, claim/retry a
# task, publish content, or read credential stores.
$taskIds = @(
    'GEO-TASK-95EE62BA113C',
    'GEO-TASK-FEF4F799B1B1',
    'GEO-TASK-6EBC1B10DD82'
)
$encodedTasks = [Uri]::EscapeDataString(($taskIds -join ','))
$requests = [ordered]@{
    status = '/api/status'
    mission = '/api/r8-11/mission-ledger'
    autonomy = '/api/r8-22/autonomy'
    seo = '/api/r8-13/seo-geo'
    seo_autonomy = '/api/r8-14/seo-geo/autonomy'
    geo_fast = '/api/r8-24/geo-growth/fast-ui'
    geo_health = '/api/r8-24/geo-growth/fast-health'
    geo_task_reconciliation = "/api/r8-19/geo/task-reconciliation?task_id=$encodedTasks"
    business_source = '/api/business-source/status'
    build_info = '/build_info.js'
}

function Protect-Value {
    param([object]$Value, [string]$Name = '')
    if ($Name -match '(?i)(password|passwd|token|secret|cookie|authorization|api[_-]?key|credential)') {
        return '[REDACTED]'
    }
    if ($null -eq $Value) { return $null }
    if ($Value -is [string]) {
        if ($Name -match '(?i)(raw_answer|prompt|response_body)') {
            $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
            $stream = [IO.MemoryStream]::new($bytes)
            try { $hash = (Get-FileHash -InputStream $stream -Algorithm SHA256).Hash }
            finally { $stream.Dispose() }
            return [ordered]@{ redacted = $true; length = $Value.Length; sha256 = $hash }
        }
        return $Value
    }
    if ($Value -is [System.Collections.IDictionary]) {
        $copy = [ordered]@{}
        foreach ($key in $Value.Keys) { $copy[[string]$key] = Protect-Value $Value[$key] ([string]$key) }
        return $copy
    }
    if ($Value -is [pscustomobject]) {
        $copy = [ordered]@{}
        foreach ($property in $Value.PSObject.Properties) {
            $copy[$property.Name] = Protect-Value $property.Value $property.Name
        }
        return $copy
    }
    if ($Value -is [System.Collections.IEnumerable] -and $Value -isnot [string]) {
        return @($Value | ForEach-Object { Protect-Value $_ $Name })
    }
    return $Value
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$capturedAt = [DateTimeOffset]::Now.ToString('o')
$results = [ordered]@{}
foreach ($name in $requests.Keys) {
    $uri = $BaseUrl.TrimEnd('/') + $requests[$name]
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest -Uri $uri -Method Get -UseBasicParsing -TimeoutSec 15 -Headers @{
            'Accept' = 'application/json,text/javascript,text/plain'
            'Cache-Control' = 'no-cache'
        }
        $watch.Stop()
        $contentType = [string]$response.Headers['Content-Type']
        $body = if ($contentType -match 'json') { $response.Content | ConvertFrom-Json } else { [string]$response.Content }
        $results[$name] = [ordered]@{
            endpoint = $requests[$name]
            ok = $true
            http_status = [int]$response.StatusCode
            elapsed_ms = [int]$watch.ElapsedMilliseconds
            data = Protect-Value $body
        }
    } catch {
        $watch.Stop()
        $status = $null
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        $results[$name] = [ordered]@{
            endpoint = $requests[$name]
            ok = $false
            http_status = $status
            elapsed_ms = [int]$watch.ElapsedMilliseconds
            error_type = $_.Exception.GetType().Name
            error = ([string]$_.Exception.Message).Substring(0, [Math]::Min(500, ([string]$_.Exception.Message).Length))
        }
    }
}

$payload = [ordered]@{
    schema = 'kazuizhi.859.readonly-diagnostics.v1'
    captured_at = $capturedAt
    computer = $env:COMPUTERNAME
    base_url = $BaseUrl
    safety = [ordered]@{
        http_methods = @('GET')
        task_claims = 0
        retries = 0
        publications = 0
        configuration_writes = 0
        secrets_exported = $false
        raw_answers_exported = $false
    }
    requested_geo_task_ids = $taskIds
    results = $results
}

$stamp = [DateTimeOffset]::Now.ToString('yyyyMMdd-HHmmss')
$jsonPath = Join-Path $OutputDirectory "Kazuizhi859-Diagnostics-$stamp.json"
$payload | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
$hash = (Get-FileHash -LiteralPath $jsonPath -Algorithm SHA256).Hash
$hashPath = "$jsonPath.sha256"
"$hash  $([IO.Path]::GetFileName($jsonPath))" | Set-Content -LiteralPath $hashPath -Encoding ASCII

[ordered]@{
    export = $jsonPath
    sha256_file = $hashPath
    sha256 = $hash
    captured_at = $capturedAt
    read_only = $true
} | ConvertTo-Json -Depth 4
