param(
    [Parameter(Mandatory = $true)][string]$ExePath,
    [Parameter(Mandatory = $true)][string]$AppDir
)
$ErrorActionPreference = 'Stop'
$taskName = 'Kazuizhi AI Phase1 Supervisor'
$startupName = '卡嘴子 AI 第一阶段后台守护.lnk'
$startupPath = Join-Path ([Environment]::GetFolderPath('Startup')) $startupName
$dataDir = Join-Path $env:LOCALAPPDATA 'Kazuizhi_AI_Enterprise_V2.0.0_Beta\data\r8_25'
$statusPath = Join-Path $dataDir 'service_install.json'
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$result = [ordered]@{
    schema = 'kz.phase1-supervisor-install.v1'
    installed = $false
    mode = 'pending'
    task_name = $taskName
    installed_at = (Get-Date).ToString('o')
    detail = ''
}

try {
    $action = New-ScheduledTaskAction -Execute $ExePath -Argument '--supervisor --no-browser' -WorkingDirectory $AppDir
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
        -Description '卡嘴子 AI 用户级7x24守护：登录后启动，异常退出自动恢复。' -Force | Out-Null
    if (Test-Path -LiteralPath $startupPath) { Remove-Item -LiteralPath $startupPath -Force }
    Start-ScheduledTask -TaskName $taskName
    $result.installed = $true
    $result.mode = 'user_scheduled_task'
    $result.detail = '登录后自动启动；任务计划程序负责异常恢复，应用内部Supervisor负责子进程重启。'
} catch {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($startupPath)
    $shortcut.TargetPath = $ExePath
    $shortcut.Arguments = '--supervisor --no-browser'
    $shortcut.WorkingDirectory = $AppDir
    $shortcut.Save()
    $result.installed = $true
    $result.mode = 'startup_shortcut_fallback'
    $result.detail = '计划任务创建失败，已启用登录启动快捷方式：' + $_.Exception.Message
    Start-Process -FilePath $ExePath -ArgumentList '--supervisor','--no-browser' -WorkingDirectory $AppDir -WindowStyle Hidden
}

$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statusPath -Encoding UTF8
