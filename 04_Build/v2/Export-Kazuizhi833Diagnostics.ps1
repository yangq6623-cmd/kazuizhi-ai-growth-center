[CmdletBinding()]
param(
    [string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'Kazuizhi_AI_Enterprise_V2.0.0_Beta\data'),
    [string]$OutputDirectory = (Join-Path ([Environment]::GetFolderPath('Desktop')) ("Kazuizhi_833_Diagnostic_" + (Get-Date -Format 'yyyyMMdd_HHmmss'))),
    [string]$OpportunityId = 'GEO-GROWTH-1F0329CF1616',
    [string[]]$JobIds = @(
        'ef3234d4de924969b1ea0372a550ef44',
        '81483dbb4bab42589f0c036af676fbb6',
        'f7ad20a8012241bba26a124247b7a5d1'
    )
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $DataRoot -PathType Container)) {
    throw "卡嘴子数据目录不存在：$DataRoot"
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

function Read-Ledger([string]$RelativePath) {
    $path = Join-Path $DataRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $null }
    return Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-ArrayProperty($Object, [string[]]$Names) {
    if ($null -eq $Object) { return @() }
    foreach ($name in $Names) {
        $property = $Object.PSObject.Properties[$name]
        if ($null -ne $property -and $null -ne $property.Value) {
            return @($property.Value)
        }
    }
    return @()
}

function Get-FirstValue($Object, [string[]]$Names, $Default = $null) {
    if ($null -eq $Object) { return $Default }
    foreach ($name in $Names) {
        $property = $Object.PSObject.Properties[$name]
        if ($null -ne $property -and $null -ne $property.Value -and [string]$property.Value -ne '') {
            return $property.Value
        }
    }
    return $Default
}

function Redact-Value($Value) {
    if ($null -eq $Value) { return $null }
    if ($Value -is [string] -or $Value -is [ValueType]) { return $Value }
    if ($Value -is [System.Collections.IDictionary]) {
        $copy = [ordered]@{}
        foreach ($key in $Value.Keys) {
            if ([string]$key -match '(?i)(password|passwd|secret|token|cookie|authorization|credential|api[_-]?key|access[_-]?key|refresh[_-]?key)') {
                $copy[[string]$key] = '<redacted>'
            } else {
                $copy[[string]$key] = Redact-Value $Value[$key]
            }
        }
        return $copy
    }
    if ($Value -is [System.Collections.IEnumerable]) {
        return @($Value | ForEach-Object { Redact-Value $_ })
    }
    $copy = [ordered]@{}
    foreach ($property in $Value.PSObject.Properties) {
        if ($property.Name -match '(?i)(password|passwd|secret|token|cookie|authorization|credential|api[_-]?key|access[_-]?key|refresh[_-]?key)') {
            $copy[$property.Name] = '<redacted>'
        } else {
            $copy[$property.Name] = Redact-Value $property.Value
        }
    }
    return $copy
}

$growth = Read-Ledger 'geo_validation\growth_orchestrator.json'
$geoQueue = Read-Ledger 'geo_validation\queue.json'
$geoReceipts = Read-Ledger 'geo_validation\receipts.json'
$r7Jobs = Read-Ledger 'r7\jobs.json'
$seo = Read-Ledger 'r8_13\seo_geo_growth.json'
$publishReceipts = Read-Ledger 'r8_15\seo_public_deploy_receipts.json'
$businessStatus = Read-Ledger 'integrations\business_source.json'
$businessSummary = Read-Ledger 'business\remote_summary.json'

$opportunities = Get-ArrayProperty $growth @('opportunities', 'items')
$selectedOpportunities = @($opportunities | Where-Object {
    $_.id -eq $OpportunityId -or $JobIds -contains [string]$_.job_id
})
$questionIds = @($selectedOpportunities | ForEach-Object { [string]$_.question_id } | Where-Object { $_ } | Select-Object -Unique)
$assetIds = @($selectedOpportunities | ForEach-Object { [string]$_.asset_id } | Where-Object { $_ } | Select-Object -Unique)
$revisionIds = @($selectedOpportunities | ForEach-Object { [string]$_.content_revision_id } | Where-Object { $_ } | Select-Object -Unique)
$scheduleTaskIds = @($selectedOpportunities | ForEach-Object {
    @($_.retest_schedule) | ForEach-Object { [string]$_.task_id }
} | Where-Object { $_ } | Select-Object -Unique)

$queueTasks = Get-ArrayProperty $geoQueue @('tasks', 'items')
$selectedTasks = @($queueTasks | Where-Object {
    $correlation = $_.correlation
    $scheduleTaskIds -contains [string]$_.task_id -or
    $questionIds -contains [string]$_.question_id -or
    ($null -ne $correlation -and (
        [string]$correlation.opportunity_id -eq $OpportunityId -or
        $revisionIds -contains [string]$correlation.content_revision_id
    ))
})
$selectedTaskIds = @($selectedTasks | ForEach-Object { [string]$_.task_id } | Where-Object { $_ } | Select-Object -Unique)

$receiptRows = Get-ArrayProperty $geoReceipts @('receipts', 'items')
$selectedReceipts = @($receiptRows | Where-Object {
    $selectedTaskIds -contains [string]$_.task_id -or
    [string]$_.opportunity_id -eq $OpportunityId -or
    $revisionIds -contains [string]$_.content_revision_id
})

$publicationRows = Get-ArrayProperty $publishReceipts @('items', 'receipts')
$selectedPublicationReceipts = @($publicationRows | Where-Object {
    $assetIds -contains [string]$_.asset_id -or
    [string]$_.growth_action_id -eq $OpportunityId -or
    $revisionIds -contains [string]$_.content_revision_id
} | Sort-Object {
    if ($_.created_at) { [datetimeoffset]$_.created_at } else { [datetimeoffset]::MaxValue }
})

$seoAssets = Get-ArrayProperty $seo @('assets')
$selectedAssets = @($seoAssets | Where-Object {
    $assetIds -contains [string]$_.id -or
    [string]$_.growth_action_id -eq $OpportunityId -or
    $revisionIds -contains [string]$_.content_revision_id
})

$r7Rows = Get-ArrayProperty $r7Jobs @('items', 'jobs')
$selectedJobs = @($r7Rows | Where-Object { $JobIds -contains [string]$_.id })

$protectedTasks = @($queueTasks | Where-Object {
    $reason = [string](Get-FirstValue $_ @('error_reason', 'error', 'last_error') '')
    (Get-FirstValue $_ @('uncertain_external_submission') $false) -eq $true -or
    (Get-FirstValue $_ @('result_unknown') $false) -eq $true -or
    $reason -match '(?i)(timeout|timed out|超时)'
} | ForEach-Object {
    $uncertain = ((Get-FirstValue $_ @('uncertain_external_submission') $false) -eq $true) -or
                 ((Get-FirstValue $_ @('result_unknown') $false) -eq $true)
    [ordered]@{
        task_id = [string](Get-FirstValue $_ @('task_id') '')
        state = [string](Get-FirstValue $_ @('state') '')
        provider = [string](Get-FirstValue $_ @('provider') '')
        failure_reason = [string](Get-FirstValue $_ @('error_reason', 'error', 'last_error') '')
        uncertain_external_submission = [bool]$uncertain
    }
})

$sourceFiles = @(
    'geo_validation\growth_orchestrator.json',
    'geo_validation\queue.json',
    'geo_validation\receipts.json',
    'r7\jobs.json',
    'r8_13\seo_geo_growth.json',
    'r8_15\seo_public_deploy_receipts.json',
    'integrations\business_source.json',
    'business\remote_summary.json'
)
$sourceHashes = @($sourceFiles | ForEach-Object {
    $path = Join-Path $DataRoot $_
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        [ordered]@{
            relative_path = $_
            last_write_time = (Get-Item -LiteralPath $path).LastWriteTime.ToString('o')
            sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        }
    }
})

$export = [ordered]@{
    schema = 'kz.833-readonly-diagnostic.v1'
    exported_at = (Get-Date).ToString('o')
    read_only = $true
    safety = [ordered]@{
        production_mutations = 0
        retries_triggered = 0
        credentials_exported = $false
        note = '仅读取本机 JSON 账本；不调用运行、重试、暂停、恢复或外发接口。'
    }
    selection = [ordered]@{
        opportunity_id = $OpportunityId
        job_ids = $JobIds
        question_ids = $questionIds
        asset_ids = $assetIds
        revision_ids = $revisionIds
    }
    runtime = [ordered]@{
        enabled = Get-FirstValue $growth @('enabled') $null
        paused = Get-FirstValue $growth @('paused') $null
        last_run_at = Get-FirstValue $growth @('last_run_at') ''
        last_error = Get-FirstValue $growth @('last_error') ''
        active_opportunity_count = @($opportunities | Where-Object { $_.state -ne 'superseded' }).Count
    }
    opportunities = Redact-Value $selectedOpportunities
    r7_jobs = Redact-Value $selectedJobs
    geo_tasks = Redact-Value $selectedTasks
    geo_receipts = Redact-Value $selectedReceipts
    seo_assets = Redact-Value $selectedAssets
    publication_receipts = Redact-Value $selectedPublicationReceipts
    protected_history = [ordered]@{
        total = $protectedTasks.Count
        timeout = @($protectedTasks | Where-Object { $_.failure_reason -match '(?i)(timeout|timed out|超时)' }).Count
        uncertain = @($protectedTasks | Where-Object { $_.uncertain_external_submission }).Count
        tasks = Redact-Value $protectedTasks
    }
    business = [ordered]@{
        status = Redact-Value $businessStatus
        aggregate_snapshot = Redact-Value $businessSummary
    }
    source_files = $sourceHashes
}

$jsonPath = Join-Path $OutputDirectory 'Kazuizhi_833_Diagnostic.json'
$export | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $jsonPath -Encoding UTF8
$jsonHash = (Get-FileHash -LiteralPath $jsonPath -Algorithm SHA256).Hash
"$jsonHash  Kazuizhi_833_Diagnostic.json" | Set-Content -LiteralPath (Join-Path $OutputDirectory 'SHA256SUMS.txt') -Encoding UTF8
@"
卡嘴子 #833 只读诊断导出

输出：Kazuizhi_833_Diagnostic.json
SHA256：$jsonHash
来源：$DataRoot

本工具只读取并脱敏导出账本，不修改配置、任务、Receipt、生产文件或经营数据；不执行重试或外发。
未读取 integrations\business_readonly_key.bin，也不会导出密码、Token、Cookie 或授权头。
"@ | Set-Content -LiteralPath (Join-Path $OutputDirectory 'README.txt') -Encoding UTF8

Write-Host "只读诊断导出完成：$OutputDirectory"
Write-Host "SHA256：$jsonHash"
