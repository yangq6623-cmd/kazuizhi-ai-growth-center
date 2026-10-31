param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$setup = Join-Path $root 'installer_output_v2/Kazuizhi_AI_Enterprise_V2.2.2_R8_Autonomous_Mission_Core.exe'
$baseTemp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$baseTemp = (Resolve-Path $baseTemp).Path.TrimEnd('\')
$testRoot = Join-Path $baseTemp ('KazuizhiV2InstallerTest-' + [guid]::NewGuid().ToString('N'))
$oldLocalAppData = $env:LOCALAPPDATA
$env:LOCALAPPDATA = Join-Path $testRoot 'localappdata'
$name = 'Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe'
function Install-R8 {
    $proc = Start-Process -FilePath $setup -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', ('/DIR="' + $testRoot + '"')) -Wait -PassThru -WindowStyle Hidden
    if ($proc.ExitCode -ne 0) { throw "Install failed: $($proc.ExitCode)" }
}
function Verify-Runtime([string]$Exe) {
    & $Python (Join-Path $PSScriptRoot 'verify_v2_autonomous.py') --exe $Exe
    if ($LASTEXITCODE -ne 0) { throw 'Inherited R8 runtime verification failed' }
    & $Python (Join-Path $PSScriptRoot 'verify_r8_operational.py') --exe $Exe
    if ($LASTEXITCODE -ne 0) { throw 'V2.2 autonomous runtime verification failed' }
}
function Assert-PersistentFiles([hashtable]$Expected, [bool]$Exact) {
    foreach ($relative in $Expected.Keys) {
        $path = Join-Path $dataRoot $relative
        if (-not (Test-Path -LiteralPath $path)) { throw "Persistent user file missing: $relative" }
        $raw = Get-Content -LiteralPath $path -Raw
        try { $null = $raw | ConvertFrom-Json } catch { throw "Persistent user JSON became invalid: $relative" }
        if ($Exact -and $raw.Trim() -ne $Expected[$relative]) { throw "Clean reinstall changed persistent user file: $relative" }
    }
}
try {
    New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA | Out-Null
    Install-R8
    $exe = Join-Path $testRoot $name
    $version = (Get-Item -LiteralPath $exe).VersionInfo
    if ($version.FileVersion -ne '2.2.2.22' -or $version.ProductName -ne 'Kazuizhi AI Enterprise V2.2.2 R8 Autonomous Mission Core') { throw 'Windows EXE version mismatch' }
    Verify-Runtime $exe

    $dataRoot = Join-Path $env:LOCALAPPDATA 'Kazuizhi_AI_Enterprise_V2.0.0_Beta/data'
    New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
    $sentinel = Join-Path $dataRoot 'user-data-preservation-test.txt'
    Set-Content -LiteralPath $sentinel -Value 'preserve-v2-user-data'
    $persistentFiles = @{
        'r7\jobs.json' = '{"schema":1,"items":[{"title":"installer-persistence-job"}]}'
        'operations\tasks.json' = '{"items":[{"title":"installer-persistence-task"}]}'
        'promotion\keywords.json' = '{"items":[{"keyword":"installer-persistence-keyword"}]}'
        'promotion\history.json' = '{"items":[{"kind":"installer-persistence-draft"}]}'
        'summaries\today.json' = '{"completed_items":["installer-persistence-summary"]}'
        'plans\latest_plan.json' = '{"tasks":[{"title":"installer-persistence-plan"}]}'
        'memory\learning_memory.json' = '{"entries":[{"statement":"installer-persistence-memory"}]}'
        'r8\control.json' = '{"devices":[],"accounts":[],"audit":[]}'
    }
    foreach ($relative in $persistentFiles.Keys) {
        $item = Join-Path $dataRoot $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $item) | Out-Null
        Set-Content -LiteralPath $item -Value $persistentFiles[$relative] -NoNewline
    }

    Install-R8
    if ((Get-Content -LiteralPath $sentinel -Raw).Trim() -ne 'preserve-v2-user-data') { throw 'Clean reinstall modified data sentinel' }
    Assert-PersistentFiles $persistentFiles $true

    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start(); $port = $listener.LocalEndpoint.Port; $listener.Stop()
    $runtime = Start-Process -FilePath $exe -ArgumentList @('--no-browser','--port',"$port") -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 2
    $runtime.Refresh()
    if ($runtime.HasExited) { throw 'Active-runtime upgrade setup failed: runtime exited early' }
    Install-R8
    try { $runtime.WaitForExit(5000) | Out-Null } catch {}
    $runtime.Refresh()
    if (-not $runtime.HasExited) { throw 'Installer left active runtime running' }
    if ((Get-Content -LiteralPath $sentinel -Raw).Trim() -ne 'preserve-v2-user-data') { throw 'Active-runtime reinstall modified data sentinel' }
    Assert-PersistentFiles $persistentFiles $false
    Verify-Runtime $exe

    $proc = Start-Process -FilePath (Join-Path $testRoot 'unins000.exe') -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru -WindowStyle Hidden
    if ($proc.ExitCode -ne 0) { throw 'Uninstall failed' }
    if (Test-Path -LiteralPath $exe) { throw 'Uninstall left application executable' }
    if ((Get-Content -LiteralPath $sentinel -Raw).Trim() -ne 'preserve-v2-user-data') { throw 'Uninstall deleted persistent user data' }
    Assert-PersistentFiles $persistentFiles $false
    Write-Host 'PASS: V2.2.2 autonomous install, runtime verification, overwrite upgrade, data preservation and uninstall preservation'
} finally {
    $env:LOCALAPPDATA = $oldLocalAppData
    if (Test-Path -LiteralPath $testRoot) {
        $resolved = (Resolve-Path $testRoot).Path
        if (-not $resolved.StartsWith($baseTemp + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing to clean non-temporary path: $resolved" }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}