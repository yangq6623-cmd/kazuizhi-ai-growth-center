param(
    [Parameter(Mandatory = $true)][string]$ExePath,
    [Parameter(Mandatory = $true)][string]$AppDir
)
$ErrorActionPreference = 'Stop'
$taskName = 'Kazuizhi AI Phase1 Supervisor'
$startupName = 'Kazuizhi AI Phase1 Supervisor.lnk'
$startupPath = Join-Path ([Environment]::GetFolderPath('Startup')) $startupName
$dataDir = Join-Path $env:LOCALAPPDATA 'Kazuizhi_AI_Enterprise_V2.0.0_Beta\data\r8_25'
$statusPath = Join-Path $dataDir 'service_install.json'
$runtimePath = Join-Path $dataDir 'runtime_supervisor.json'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

function Write-JsonNoBom([string]$Path, [object]$Value) {
    $json = $Value | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($Path, $json, (New-Object System.Text.UTF8Encoding($false)))
}

$result = [ordered]@{
    schema = 'kz.phase1-supervisor-install.v1'
    installed = $false
    mode = 'pending'
    task_name = $taskName
    installed_at = (Get-Date).ToString('o')
    detail = ''
}

function Save-InstallState {
    Write-JsonNoBom -Path $statusPath -Value $result
    $runtime = [pscustomobject]@{}
    if (Test-Path -LiteralPath $runtimePath) {
        try { $runtime = Get-Content -LiteralPath $runtimePath -Raw -Encoding UTF8 | ConvertFrom-Json } catch {}
    }
    if ($null -eq $runtime) { $runtime = [pscustomobject]@{} }
    $runtime | Add-Member -NotePropertyName schema -NotePropertyValue 'kz.runtime-supervisor.v1' -Force
    $runtime | Add-Member -NotePropertyName mode -NotePropertyValue $result.mode -Force
    $runtime | Add-Member -NotePropertyName installed -NotePropertyValue $true -Force
    $runtime | Add-Member -NotePropertyName install_mode -NotePropertyValue $result.mode -Force
    $runtime | Add-Member -NotePropertyName install_detail -NotePropertyValue $result.detail -Force
    $runtime | Add-Member -NotePropertyName installed_at -NotePropertyValue $result.installed_at -Force
    $runtime | Add-Member -NotePropertyName restart_count -NotePropertyValue ([int]($runtime.restart_count)) -Force
    $runtime | Add-Member -NotePropertyName updated_at -NotePropertyValue (Get-Date).ToString('o') -Force
    Write-JsonNoBom -Path $runtimePath -Value $runtime
}

try {
    $action = New-ScheduledTaskAction -Execute $ExePath -Argument '--supervisor --no-browser' -WorkingDirectory $AppDir
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
        -Description 'Kazuizhi user-scoped 7x24 supervisor with automatic runtime recovery.' -Force | Out-Null
    if (Test-Path -LiteralPath $startupPath) { Remove-Item -LiteralPath $startupPath -Force }
    $result.installed = $true
    $result.mode = 'user_scheduled_task'
    $result.detail = 'Starts after user logon; Task Scheduler and the in-app supervisor provide recovery.'
    Save-InstallState
    Start-ScheduledTask -TaskName $taskName
} catch {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($startupPath)
    $shortcut.TargetPath = $ExePath
    $shortcut.Arguments = '--supervisor --no-browser'
    $shortcut.WorkingDirectory = $AppDir
    $shortcut.Save()
    $result.installed = $true
    $result.mode = 'startup_shortcut_fallback'
    $result.detail = 'Scheduled Task unavailable; installed Startup shortcut fallback: ' + $_.Exception.Message
    Save-InstallState
    Start-Process -FilePath $ExePath -ArgumentList '--supervisor','--no-browser' -WorkingDirectory $AppDir -WindowStyle Hidden
}
