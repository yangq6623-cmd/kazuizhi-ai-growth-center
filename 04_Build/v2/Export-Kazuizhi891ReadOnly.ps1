[CmdletBinding()]
param(
    [string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'Kazuizhi_AI_Enterprise_V2.0.0_Beta\data'),
    [string]$BaseUrl = 'http://127.0.0.1:8876',
    [string]$OutputDirectory = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) ('Kazuizhi891-ReadOnly-' + (Get-Date -Format 'yyyyMMdd-HHmmss')))
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if (-not (Test-Path -LiteralPath $DataRoot -PathType Container)) { throw "Data directory not found: $DataRoot" }
if ($BaseUrl.TrimEnd('/') -ne 'http://127.0.0.1:8876') { throw 'Only local read-only workbench 127.0.0.1:8876 is permitted' }

function Field($row, [string]$name) {
    if ($null -eq $row) { return $null }
    $property = $row.PSObject.Properties[$name]
    if ($null -ne $property) { return $property.Value }
    return $null
}

function Safe-Text($value) {
    $text = [string]$value
    $text = $text -replace '(?i)(bearer\s+)\S+', '$1[REDACTED]'
    $text = $text -replace '(?i)(token|secret|password|api[_-]?key|authorization)=([^&\s]+)', '$1=[REDACTED]'
    $text = $text -replace '(https?://[^\s?]+)\?\S+', '$1?[QUERY_REDACTED]'
    return $text.Substring(0, [Math]::Min(300, $text.Length))
}

function Safe-Row($row) {
    $fields = @(
        'id', 'task_id', 'job_id', 'asset_id', 'opportunity_id', 'question_id',
        'run_id', 'attempt_id', 'receipt_id', 'evidence_id', 'command_id',
        'decision_pack_id', 'growth_action_id', 'content_revision_id',
        'region', 'service', 'keyword', 'provider', 'expected_platform',
        'platform', 'stage', 'state', 'status', 'kind', 'executor', 'mode',
        'qc_status', 'qc_reasons', 'public_url', 'canonical', 'reason',
        'error', 'last_error', 'last_error_at', 'created_at', 'updated_at',
        'published_at', 'submitted_at', 'due_at', 'last_run_at', 'last_success_at',
        'last_attempt_at', 'last_heartbeat_at', 'last_applied_at',
        'last_processed_command_path', 'last_receipt_id', 'last_command_id',
        'generated_at', 'captured_at', 'configured', 'last_health_at',
        'last_claim_reason', 'last_retest_reason', 'completed', 'total', 'public_pages',
        'submitted_urls', 'formal_evidence_count', 'last_verified_at'
    )
    $out = [ordered]@{}
    foreach ($name in $fields) {
        $value = Field $row $name
        if ($null -eq $value) { continue }
        if ($value -is [string]) { $out[$name] = Safe-Text $value }
        elseif ($value -is [ValueType]) { $out[$name] = $value }
        elseif ($name -eq 'qc_reasons') { $out[$name] = @($value | ForEach-Object { Safe-Text $_ }) }
    }
    return $out
}

$sources = [ordered]@{
    seo = @{ path = 'r8_13\seo_geo_growth.json'; collections = @('assets', 'opportunities') }
    seo_autonomy = @{ path = 'r8_14\seo_geo_autonomy.json'; collections = @('human_items') }
    remote_agent = @{ path = 'r8_17\remote_agent.json'; collections = @() }
    deploy = @{ path = 'r8_15\seo_public_deploy.json'; collections = @() }
    deploy_receipts = @{ path = 'r8_15\seo_public_deploy_receipts.json'; collections = @('items', 'receipts') }
    search = @{ path = 'r8_16\search_submitter.json'; collections = @() }
    search_receipts = @{ path = 'r8_16\search_submission_receipts.json'; collections = @('items') }
    geo_queue = @{ path = 'geo_validation\queue.json'; collections = @('tasks') }
    geo_receipts = @{ path = 'geo_validation\receipts.json'; collections = @('receipts') }
    geo_audit = @{ path = 'geo_validation\audit.json'; collections = @('events') }
    geo_browser = @{ path = 'r8_27\geo_browser_agent.json'; collections = @('sessions') }
    content_center = @{ path = 'r8\ai_content_center.json'; collections = @('tasks', 'items') }
    content_tasks = @{ path = 'r8\content_center.json'; collections = @('tasks', 'items') }
    content_factory = @{ path = 'r8\content_factory.json'; collections = @('tasks') }
    router = @{ path = 'integrations\ai_gateway_state.json'; collections = @() }
    r7_jobs = @{ path = 'r7\jobs.json'; collections = @('items', 'jobs') }
    r7_decision = @{ path = 'r7\decision_center.json'; collections = @() }
    workforce = @{ path = 'r7\workforce_schedule.json'; collections = @() }
    bus = @{ path = 'r8_10\async_control_bus_state.json'; collections = @() }
    bus_receipts = @{ path = 'r8_10\async_control_bus_receipts.json'; collections = @('items') }
    runtime = @{ path = 'r8_20\runtime_health.json'; collections = @() }
    stability = @{ path = 'r8_25\phase1_acceptance.json'; collections = @('samples') }
    stability_history = @{ path = 'r8_25\phase1_acceptance_history.json'; collections = @() }
    supervisor = @{ path = 'r8_25\runtime_supervisor.json'; collections = @() }
}

$files = [ordered]@{}
foreach ($name in $sources.Keys) {
    $spec = $sources[$name]
    $path = Join-Path $DataRoot $spec.path
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $files[$name] = @{ present = $false; relative_path = $spec.path }
        continue
    }
    try {
        $original = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
        $entry = [ordered]@{
            present = $true; relative_path = $spec.path
            modified_at = (Get-Item -LiteralPath $path).LastWriteTime.ToString('o')
            source_sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
            status = Safe-Row $original
            collections = [ordered]@{}
        }
        if ($original -is [System.Array]) {
            $entry.collections['root'] = [ordered]@{
                total = $original.Count
                rows = @($original | Select-Object -Last 120 | ForEach-Object { Safe-Row $_ })
            }
        }
        foreach ($collection in $spec.collections) {
            $rows = Field $original $collection
            if ($null -eq $rows) { continue }
            $array = @($rows)
            # Keep full identifiers/status for Asset/Task accounting, but
            # bound potentially large historical Receipt/Audit exports.
            $selected = if ($collection -in @('assets', 'opportunities', 'tasks')) {
                $array
            } else {
                @($array | Select-Object -First 60) + @($array | Select-Object -Last 60)
            }
            $entry.collections[$collection] = [ordered]@{
                total = $array.Count
                rows = @($selected | ForEach-Object { Safe-Row $_ })
            }
        }
        $files[$name] = $entry
    } catch {
        $files[$name] = @{ present = $true; read_error = Safe-Text $_.Exception.Message; relative_path = $spec.path }
    }
}

$endpoints = [ordered]@{
    status = '/api/status'
    r7_snapshot = '/api/r7/ui-snapshot'
    seo = '/api/r8-13/seo-geo'
    seo_autonomy = '/api/r8-14/seo-geo/autonomy'
    geo_fast = '/api/r8-24/geo-growth/fast-ui'
}
$api = [ordered]@{}
foreach ($name in $endpoints.Keys) {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest -Uri ($BaseUrl + $endpoints[$name]) -Method Get -UseBasicParsing -TimeoutSec 15 -Headers @{ 'Cache-Control' = 'no-cache' }
        $clock.Stop()
        $body = $response.Content | ConvertFrom-Json
        $api[$name] = @{
            ok = $true; http_status = [int]$response.StatusCode; elapsed_ms = $clock.ElapsedMilliseconds
            summary = Safe-Row $body; nested_summary = Safe-Row (Field $body 'summary')
        }
    } catch {
        $clock.Stop()
        $api[$name] = @{ ok = $false; elapsed_ms = $clock.ElapsedMilliseconds; error = Safe-Text $_.Exception.Message }
    }
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$report = [ordered]@{
    schema = 'kz.891-readonly-diagnostic.v1'; captured_at = [DateTimeOffset]::Now.ToString('o')
    safety = 'Read-only JSON and local GET; no raw answers, secrets, orders or users; no claim, execution or retry.'
    files = $files; api = $api
}
$target = Join-Path $OutputDirectory 'Kazuizhi891-ReadOnly.json'
$report | ConvertTo-Json -Depth 25 | Set-Content -LiteralPath $target -Encoding UTF8
$hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
"$hash  Kazuizhi891-ReadOnly.json" | Set-Content -LiteralPath (Join-Path $OutputDirectory 'SHA256SUMS.txt') -Encoding ASCII
Write-Output "Read-only export: $target"
Write-Output "SHA256: $hash"
