param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$setup = Join-Path $root 'installer_output_v2/Kazuizhi_AI_Enterprise_V2.2.2_R8-23_Final_Complete_Workbench.exe'
$baseTemp = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { $env:TEMP }
$baseTemp = (Resolve-Path $baseTemp).Path.TrimEnd('\')
$testRoot = Join-Path $baseTemp ('KazuizhiV2InstallerTest-' + [guid]::NewGuid().ToString('N'))
$oldLocalAppData = $env:LOCALAPPDATA
$env:LOCALAPPDATA = Join-Path $testRoot 'localappdata'
$name = 'Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe'
$installerScript = Join-Path $root '04_Build/installer/Kazuizhi_AI_V2.0.0_Beta_Setup.iss'
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
function Assert-GeoOwnerRuntime([int]$Port) {
    $base = "http://127.0.0.1:$Port"
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "$base/api/status" -Method Get -TimeoutSec 2
            if ($health.status -eq 'online') { $ready = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw 'Installed runtime did not become HTTP-ready for GEO field smoke test' }

    foreach ($route in @('/api/r8-24/geo-growth/fast','/api/r8-24/geo-growth')) {
        $watch = [System.Diagnostics.Stopwatch]::StartNew()
        $snapshot = Invoke-RestMethod -Uri ($base + $route) -Method Get -TimeoutSec 4
        $watch.Stop()
        if ($watch.Elapsed.TotalSeconds -gt 4.0) { throw "GEO owner snapshot exceeded 4 seconds: $route" }
        if ($snapshot.status_mode -ne 'fast_snapshot') { throw "GEO owner snapshot did not use fast mode: $route" }
        if ([string]::IsNullOrWhiteSpace([string]$snapshot.state)) { throw "GEO owner snapshot missing state: $route" }
        if ([string]::IsNullOrWhiteSpace([string]$snapshot.mission)) { throw "GEO owner snapshot missing mission: $route" }
        if ([int]$snapshot.formal_ab_target -ne 50) { throw "GEO owner snapshot lost formal A/B target: $route" }
        if ($null -eq $snapshot.summary -or $null -eq $snapshot.cloud) { throw "GEO owner snapshot missing summary/cloud: $route" }
    }

    $geoHtml = (Invoke-WebRequest -Uri "$base/geo.html?embed=1" -UseBasicParsing -TimeoutSec 4).Content
    foreach ($marker in @('geo-growth-os.js','recoverGeoWorkbench','GEO 工作台正在加载')) {
        if ($geoHtml -notmatch [regex]::Escape($marker)) { throw "Installed GEO HTML missing recovery marker: $marker" }
    }

    $bundle = (Invoke-WebRequest -Uri "$base/operational-search.js" -UseBasicParsing -TimeoutSec 4).Content
    foreach ($marker in @('/api/r8-24/geo-growth/fast','__KZ_GEO_GROWTH_OS_BOOT__','GEO 自动增长数据等待超时')) {
        if ($bundle -notmatch [regex]::Escape($marker)) { throw "Installed GEO bundle missing fast-owner marker: $marker" }
    }
    $pf86 = [Environment]::GetFolderPath('ProgramFilesX86')
    $browserCandidates = @(
        (Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'),
        (Join-Path $pf86 'Google\Chrome\Application\chrome.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $pf86 'Microsoft\Edge\Application\msedge.exe')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    if (-not $browserCandidates) { throw 'No installed Chromium browser available for GEO DOM smoke test' }
    $browser = $browserCandidates[0]
    $domFile = Join-Path $testRoot 'geo-dom.html'
    $args = @('--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--virtual-time-budget=12000','--dump-dom',"$base/geo.html?embed=1")
    $proc = Start-Process -FilePath $browser -ArgumentList $args -PassThru -NoNewWindow -RedirectStandardOutput $domFile
    if (-not $proc.WaitForExit(20000)) { try { $proc.Kill() } catch {}; throw 'Headless GEO DOM smoke timed out' }
    if ($proc.ExitCode -ne 0) { throw "Headless GEO DOM smoke failed: $($proc.ExitCode)" }
    $dom = Get-Content -LiteralPath $domFile -Raw
    foreach ($marker in @('id="search-growth-switch"','id="geo-growth-pane"','id="geo-growth-os"','GEO 自动增长工作台')) {
        if ($dom -notmatch [regex]::Escape($marker)) { throw "Installed GEO DOM did not fully mount: $marker" }
    }
    if ($dom -match '页面框架已经打开。#683') { throw 'Installed GEO DOM still contains stale #683 fallback contract' }

    Write-Host 'PASS: installed GEO owner runtime responds quickly and real Chromium DOM mounts the GEO Growth OS'
}
function Assert-GeoBrowserDom([int]$Port) {
    & $Python (Join-Path $PSScriptRoot 'test_geo_browser_field.py') --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Installed GEO real-browser DOM smoke failed' }
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
$runtime = $null
try {
    $installerText = Get-Content -LiteralPath $installerScript -Raw
    if ($installerText -notmatch '\{userstartup\}\\卡嘴子 AI 后台自动运行 R8-23') { throw 'Installer is missing the per-user background autostart shortcut' }
    if ($installerText -notmatch 'Parameters: "--no-browser"') { throw 'Background autostart must not open a browser on sign-in' }
    New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA | Out-Null
    Install-R8
    $exe = Join-Path $testRoot $name
    $version = (Get-Item -LiteralPath $exe).VersionInfo
    if ($version.FileVersion -ne '2.2.2.23' -or $version.ProductName -ne 'Kazuizhi AI Enterprise V2.2.2 R8-23 Final Workbench') { throw 'Windows EXE version mismatch' }
    foreach ($serverTool in @('R8-17_SERVER_ROOT_DISCOVERY_BOOTSTRAP.ps1', 'R8-17_SERVER_ROOT_DISCOVERY_BOOTSTRAP.cmd')) {
        if (-not (Test-Path -LiteralPath (Join-Path $testRoot $serverTool) -PathType Leaf)) { throw "Installed server root-discovery tool missing: $serverTool" }
    }
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
    Assert-GeoOwnerRuntime $port
    Assert-GeoBrowserDom $port
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
    Write-Host 'PASS: R8-23 Final Workbench install, GEO owner HTTP smoke, runtime verification, overwrite upgrade, data preservation and uninstall preservation'
} finally {
    if ($null -ne $runtime) {
        try {
            $runtime.Refresh()
            if (-not $runtime.HasExited) {
                Stop-Process -Id $runtime.Id -Force -ErrorAction SilentlyContinue
                try { $runtime.WaitForExit(5000) | Out-Null } catch {}
            }
        } catch {}
    }
    $env:LOCALAPPDATA = $oldLocalAppData
    if (Test-Path -LiteralPath $testRoot) {
        $resolved = (Resolve-Path $testRoot).Path
        if (-not $resolved.StartsWith($baseTemp + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw "Refusing to clean non-temporary path: $resolved" }
        $removed = $false
        for ($cleanupAttempt = 0; $cleanupAttempt -lt 10; $cleanupAttempt++) {
            try {
                Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction Stop
                $removed = $true
                break
            } catch {
                Start-Sleep -Milliseconds (300 + ($cleanupAttempt * 200))
            }
        }
        if (-not $removed -and (Test-Path -LiteralPath $resolved)) {
            Write-Warning "Deferred cleanup of locked CI test directory: $resolved"
        }
    }
}
