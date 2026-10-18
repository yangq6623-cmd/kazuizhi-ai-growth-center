#requires -version 5.1
<#
.SYNOPSIS
  卡嘴子 #817 GEO 原始账本只读取证工具。

.DESCRIPTION
  仅从 %LOCALAPPDATA%\Kazuizhi_AI_Enterprise_V2.0.0_Beta\data 读取 JSON，
  并对 127.0.0.1:8876 的四个只读 GET 接口各访问一次。工具只在指定输出目录
  写入脱敏诊断文件；不会修改生产配置、任务状态、冷却、Evidence 或安装目录。
#>
[CmdletBinding()]
param(
    [string]$OutputRoot = (Join-Path ([Environment]::GetFolderPath('Desktop')) ("KZ817_GEO_READONLY_{0}" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))),
    [string]$BaseUri = 'http://127.0.0.1:8876'
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$dataRoot = Join-Path $env:LOCALAPPDATA 'Kazuizhi_AI_Enterprise_V2.0.0_Beta\data'
if (-not (Test-Path -LiteralPath $dataRoot -PathType Container)) {
    throw "未找到 #817 数据目录：$dataRoot"
}

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
$resolvedOutput = (Resolve-Path -LiteralPath $OutputRoot).Path
$resolvedData = (Resolve-Path -LiteralPath $dataRoot).Path
if ($resolvedOutput.StartsWith($resolvedData, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw '安全停止：输出目录不能位于生产 data 目录内。'
}

function Get-PropValue {
    param([object]$Object, [string]$Name, [object]$Default = $null)
    if ($null -eq $Object) { return $Default }
    $prop = $Object.PSObject.Properties[$Name]
    if ($null -eq $prop) { return $Default }
    return $prop.Value
}

function Read-JsonFile {
    param([string]$RelativePath, [object]$Default)
    $path = Join-Path $dataRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $Default }
    try { return (Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json) }
    catch { throw "无法解析只读账本 $RelativePath：$($_.Exception.Message)" }
}

function Test-SensitiveKey {
    param([string]$Name)
    return $Name -match '(?i)^(password|passwd|pwd|token|cookie|cookies|secret|client_secret|refresh_token|access_token|api_key|apikey|private_key|authorization_header|credential|credentials|headers)$' -or
           $Name -match '(?i)(password|passwd|client_secret|refresh_token|access_token|api[_-]?key|private[_-]?key)'
}

function Protect-Value {
    param([object]$Value, [string]$KeyName = '')
    if (Test-SensitiveKey $KeyName) { return '[REDACTED]' }
    if ($null -eq $Value) { return $null }
    if ($Value -is [string] -or $Value -is [ValueType]) { return $Value }
    if ($Value -is [System.Collections.IDictionary]) {
        $out = [ordered]@{}
        foreach ($key in $Value.Keys) { $out[[string]$key] = Protect-Value $Value[$key] ([string]$key) }
        return $out
    }
    if ($Value -is [System.Collections.IEnumerable]) {
        $items = @()
        foreach ($item in $Value) { $items += ,(Protect-Value $item '') }
        return $items
    }
    $obj = [ordered]@{}
    foreach ($prop in $Value.PSObject.Properties) {
        $obj[$prop.Name] = Protect-Value $prop.Value $prop.Name
    }
    return $obj
}

function Write-JsonUtf8 {
    param([string]$Name, [object]$Value, [int]$Depth = 40)
    $path = Join-Path $OutputRoot $Name
    $json = $Value | ConvertTo-Json -Depth $Depth
    [System.IO.File]::WriteAllText($path, $json, (New-Object System.Text.UTF8Encoding($false)))
}

function Get-TaskClassification {
    param([object]$Task)
    $state = [string](Get-PropValue $Task 'state' '')
    $reason = '{0} {1} {2}' -f (Get-PropValue $Task 'failure_code' ''), (Get-PropValue $Task 'failure_reason' ''), (Get-PropValue $Task 'authorization_reason' '')
    $authLike = $state -eq 'authorization_required' -or $reason -match '(?i)login|auth|authoriz|captcha|risk|风控|登录|授权|验证'
    if ($authLike) { return '登录/授权/风控' }
    if ($state -eq 'failed') { return '历史技术失败' }
    if ($state -eq 'succeeded') { return '已成功并有终态' }
    if ($state -eq 'queued') { return '排队未发送' }
    if ($state -eq 'paused') { return '暂停' }
    if ($state -eq 'running') { return '执行中' }
    return '未分类'
}

function Test-UncertainSend {
    param([object]$Task)
    $state = [string](Get-PropValue $Task 'state' '')
    $evidence = [string](Get-PropValue $Task 'evidence_id' '')
    $started = [string](Get-PropValue $Task 'started_at' '')
    $attempt = [string](Get-PropValue $Task 'external_attempted_at' '')
    $reason = '{0} {1}' -f (Get-PropValue $Task 'failure_reason' ''), (Get-PropValue $Task 'authorization_reason' '')
    return [bool]((-not $evidence) -and ($started -or $attempt -or $state -eq 'running' -or $reason -match '(?i)timeout|closed|unknown|ambiguous|超时|未知|中断'))
}

function Invoke-ReadOnlyGetOnce {
    param([string]$Path, [int]$TimeoutSec = 30)
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Method Get -Uri ($BaseUri.TrimEnd('/') + $Path) -TimeoutSec $TimeoutSec -Headers @{'Cache-Control'='no-store'}
        $watch.Stop()
        $parsed = $null
        try { $parsed = $response.Content | ConvertFrom-Json } catch { $parsed = @{ raw_text = $response.Content } }
        return [ordered]@{ path=$Path; ok=$true; status_code=[int]$response.StatusCode; duration_ms=$watch.ElapsedMilliseconds; bytes=$response.RawContentLength; payload=(Protect-Value $parsed) }
    } catch {
        $watch.Stop()
        return [ordered]@{ path=$Path; ok=$false; status_code=$null; duration_ms=$watch.ElapsedMilliseconds; bytes=$null; error=$_.Exception.Message }
    }
}

$queueDoc = Read-JsonFile 'geo_validation\queue.json' ([pscustomobject]@{tasks=@()})
$receiptDoc = Read-JsonFile 'geo_validation\receipts.json' ([pscustomobject]@{receipts=@()})
$growthDoc = Read-JsonFile 'geo_validation\growth_orchestrator.json' ([pscustomobject]@{opportunities=@();history=@()})
$auditDoc = Read-JsonFile 'geo_validation\audit.json' ([pscustomobject]@{events=@()})
$questionDoc = Read-JsonFile 'geo_validation\question_set.json' ([pscustomobject]@{})
$browserDoc = Read-JsonFile 'r8_27\geo_browser_agent.json' ([pscustomobject]@{})
$seoDoc = Read-JsonFile 'r8_14\seo_geo_autonomy.json' ([pscustomobject]@{})

$tasks = @(Get-PropValue $queueDoc 'tasks' @())
$receipts = @(Get-PropValue $receiptDoc 'receipts' @())
$opportunities = @(Get-PropValue $growthDoc 'opportunities' @())

$taskRows = foreach ($task in $tasks) {
    $reason = [string](Get-PropValue $task 'failure_reason' '')
    if (-not $reason) { $reason = [string](Get-PropValue $task 'authorization_reason' '') }
    [pscustomobject][ordered]@{
        task_id = [string](Get-PropValue $task 'task_id' '')
        platform = [string](Get-PropValue $task 'expected_platform' (Get-PropValue $task 'provider' ''))
        provider = [string](Get-PropValue $task 'provider' '')
        test_method = [string](Get-PropValue $task 'test_method' '')
        question_id = [string](Get-PropValue $task 'question_id' '')
        question_text = [string](Get-PropValue $task 'question_text' '')
        original_send_state = [string](Get-PropValue $task 'state' '')
        classification = Get-TaskClassification $task
        uncertain_send_overlap = Test-UncertainSend $task
        failure_code = [string](Get-PropValue $task 'failure_code' '')
        failure_reason = $reason
        created_at = [string](Get-PropValue $task 'created_at' '')
        started_at = [string](Get-PropValue $task 'started_at' '')
        updated_at = [string](Get-PropValue $task 'updated_at' '')
        scheduled_retest_at = [string](Get-PropValue $task 'scheduled_retest_at' '')
        retest_origin = [string](Get-PropValue $task 'retest_origin' '')
        retest_parent_receipt = [string](Get-PropValue $task 'retest_parent_receipt' '')
        retry_count = Get-PropValue $task 'retry_count' 0
        run_id = [string](Get-PropValue $task 'run_id' '')
        evidence_id = [string](Get-PropValue $task 'evidence_id' '')
        mission_id = [string](Get-PropValue $task 'mission_id' '')
    }
}
$taskRows | Export-Csv -LiteralPath (Join-Path $OutputRoot '73_historical_tasks.csv') -NoTypeInformation -Encoding UTF8

$taskById = @{}
foreach ($task in $tasks) { $id = [string](Get-PropValue $task 'task_id' ''); if ($id) { $taskById[$id] = $task } }
$receiptByTask = @{}
foreach ($receipt in $receipts) { $id = [string](Get-PropValue $receipt 'task_id' ''); if ($id) { $receiptByTask[$id] = $receipt } }

$retestRows = @()
foreach ($opp in $opportunities) {
    $schedule = @(Get-PropValue $opp 'retest_schedule' @())
    if ($schedule.Count -eq 0) {
        $legacyTask = [string](Get-PropValue $opp 'retest_task_id' '')
        if ($legacyTask) { $schedule = @([pscustomobject]@{window='24h';task_id=$legacyTask;signal_id=(Get-PropValue $opp 'after_signal_id' '')}) }
    }
    foreach ($slot in $schedule) {
        $taskId = [string](Get-PropValue $slot 'task_id' '')
        $signalId = [string](Get-PropValue $slot 'signal_id' '')
        $task = $null; if ($taskId -and $taskById.ContainsKey($taskId)) { $task = $taskById[$taskId] }
        $receipt = $null; if ($taskId -and $receiptByTask.ContainsKey($taskId)) { $receipt = $receiptByTask[$taskId] }
        $retestRows += [pscustomobject][ordered]@{
            opportunity_id = [string](Get-PropValue $opp 'id' '')
            opportunity_state = [string](Get-PropValue $opp 'state' '')
            job_id = [string](Get-PropValue $opp 'job_id' '')
            question_id = [string](Get-PropValue $opp 'question_id' '')
            question_text = [string](Get-PropValue $opp 'question_text' '')
            window = [string](Get-PropValue $slot 'window' '24h')
            due_at = [string](Get-PropValue $slot 'due_at' '')
            queued_at = [string](Get-PropValue $slot 'queued_at' '')
            task_id = $taskId
            task_state = [string](Get-PropValue $task 'state' '')
            task_started_at = [string](Get-PropValue $task 'started_at' '')
            task_updated_at = [string](Get-PropValue $task 'updated_at' '')
            signal_id = $signalId
            before_score = Get-PropValue $opp 'operating_before_score' (Get-PropValue $opp 'baseline_score' $null)
            after_score = Get-PropValue $opp 'operating_after_score' (Get-PropValue $opp 'after_score' $null)
            delta = Get-PropValue $opp 'operating_delta' (Get-PropValue $opp 'delta' $null)
            baseline_signal_id = [string](Get-PropValue $opp 'signal_id' (Get-PropValue $opp 'baseline_signal_id' ''))
            after_signal_id = [string](Get-PropValue $opp 'after_signal_id' '')
            receipt_id = [string](Get-PropValue $receipt 'evidence_id' (Get-PropValue $receipt 'receipt_id' ''))
            receipt_tested_at = [string](Get-PropValue $receipt 'tested_at' (Get-PropValue $receipt 'finished_at' ''))
            receipt_level = [string](Get-PropValue $receipt 'evidence_level' '')
            receipt_official_truth = [bool](Get-PropValue $receipt 'official_truth' $false)
        }
    }
}
$retestRows | Export-Csv -LiteralPath (Join-Path $OutputRoot 'geo_retest_ledger.csv') -NoTypeInformation -Encoding UTF8

$historyRows = @()
foreach ($event in @(Get-PropValue $growthDoc 'history' @())) {
    $text = $event | ConvertTo-Json -Depth 15 -Compress
    if ($text -match '(?i)retest|24h|11/12|snapshot|coalesc') { $historyRows += $event }
}
Write-JsonUtf8 'geo_retest_history_evidence.json' (Protect-Value $historyRows)

$httpRows = @(
    Invoke-ReadOnlyGetOnce '/api/r8-24/geo-growth/liveness' 10
    Invoke-ReadOnlyGetOnce '/api/r8-24/geo-growth/fast-health' 15
    Invoke-ReadOnlyGetOnce '/api/r8-24/geo-growth/http-health' 15
    Invoke-ReadOnlyGetOnce '/api/r8-24/geo-growth/fast-ui' 30
)
Write-JsonUtf8 'readonly_http_diagnostics.json' $httpRows

Write-JsonUtf8 'queue_sanitized.json' (Protect-Value $queueDoc)
Write-JsonUtf8 'receipts_sanitized.json' (Protect-Value $receiptDoc)
Write-JsonUtf8 'growth_orchestrator_sanitized.json' (Protect-Value $growthDoc)
Write-JsonUtf8 'audit_sanitized.json' (Protect-Value $auditDoc)
Write-JsonUtf8 'question_set_sanitized.json' (Protect-Value $questionDoc)
Write-JsonUtf8 'browser_agent_sanitized.json' (Protect-Value $browserDoc)
Write-JsonUtf8 'seo_autonomy_sanitized.json' (Protect-Value $seoDoc)

$classCounts = @{}
foreach ($row in $taskRows) { if (-not $classCounts.ContainsKey($row.classification)) { $classCounts[$row.classification] = 0 }; $classCounts[$row.classification]++ }
$windowCounts = @{}
foreach ($label in @('24h','72h','7d')) {
    $rows = @($retestRows | Where-Object { $_.window -eq $label })
    $windowCounts[$label] = [ordered]@{scheduled=$rows.Count; queued=@($rows | Where-Object {$_.task_id -and -not $_.signal_id}).Count; completed=@($rows | Where-Object {$_.signal_id}).Count}
}
$fastUi = $httpRows | Where-Object { $_.path -eq '/api/r8-24/geo-growth/fast-ui' } | Select-Object -First 1
$cause = if (-not $fastUi.ok) {
    'fast-ui 本次只读请求失败；0/0 属于前端超时后的概览回退，不能视为账本清零。'
} elseif ($historyRows.Count -eq 0) {
    '当前原始账本和 fast-ui 已导出，但本地未保留可识别的 11/12 历史快照；11→当前值仍缺“当时那一刻”的快照证据。'
} else {
    '已找到含复测/快照关键词的历史事件；请以 geo_retest_history_evidence.json 与 geo_retest_ledger.csv 的 Task ID 对照判定任务替换、合并或真实变化。'
}
$summary = [ordered]@{
    generated_at = (Get-Date).ToString('o')
    read_only = $true
    production_data_root = $resolvedData
    output_root = $resolvedOutput
    task_total = $taskRows.Count
    task_classification = $classCounts
    uncertain_send_overlap = @($taskRows | Where-Object {$_.uncertain_send_overlap}).Count
    opportunity_total = $opportunities.Count
    receipt_total = $receipts.Count
    retest_windows_from_ledger = $windowCounts
    http_diagnostics = @($httpRows | ForEach-Object {[ordered]@{path=$_.path;ok=$_.ok;status_code=$_.status_code;duration_ms=$_.duration_ms;bytes=$_.bytes}})
    seo_autonomy = [ordered]@{enabled=(Get-PropValue $seoDoc 'enabled' $null);mode=(Get-PropValue $seoDoc 'mode' $null);cycle_count=(Get-PropValue $seoDoc 'cycle_count' (Get-PropValue $seoDoc 'cycles' $null));last_run_at=(Get-PropValue $seoDoc 'last_run_at' '')}
    diagnosis = $cause
    safety = '未修改生产数据、配置、任务状态、冷却、Evidence或#817安装文件；未调用任何POST接口。'
}
Write-JsonUtf8 'diagnostic_summary.json' $summary

$readme = @"
# 卡嘴子 #817 GEO 原始账本只读导出结果

- 生成时间：$($summary.generated_at)
- 原始任务数：$($summary.task_total)
- Opportunity：$($summary.opportunity_total)
- Receipt：$($summary.receipt_total)
- 不确定发送（重叠标签）：$($summary.uncertain_send_overlap)
- 结论：$cause

主要文件：
- 73_historical_tasks.csv：全部历史任务、原始发送状态、分类与失败原因
- geo_retest_ledger.csv：Opportunity→Task→Signal/Receipt→Before/After 关联
- readonly_http_diagnostics.json：四个只读接口各一次的耗时与响应
- diagnostic_summary.json：汇总和 SEO 自治只读状态
- *_sanitized.json：脱敏原始账本副本

安全声明：脚本未调用 POST、未重试任务、未清空冷却、未修改生产目录。
"@
[System.IO.File]::WriteAllText((Join-Path $OutputRoot 'README.md'), $readme, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ''
Write-Host '只读导出完成：' -ForegroundColor Green
Write-Host $resolvedOutput -ForegroundColor Cyan
Write-Host ("任务 {0} 条；Opportunity {1} 条；Receipt {2} 条。" -f $taskRows.Count, $opportunities.Count, $receipts.Count)
