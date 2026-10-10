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
    if (-not $ready) {
        $processDetail = 'runtime process unavailable'
        try {
            $script:runtime.Refresh()
            $processDetail = if ($script:runtime.HasExited) {
                "runtime exited with code $($script:runtime.ExitCode)"
            } else {
                "runtime alive; pid=$($script:runtime.Id); cpu=$([math]::Round($script:runtime.CPU, 2))s"
            }
        } catch { $processDetail = "runtime inspection failed: $($_.Exception.Message)" }
        $listenerDetail = 'no listener'
        try {
            $listenerDetail = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
                ForEach-Object { "listener pid=$($_.OwningProcess) address=$($_.LocalAddress)" }) -join '; '
        } catch {}
        throw "Installed runtime did not become HTTP-ready for GEO field smoke test; $processDetail; $listenerDetail; test_root=$testRoot"
    }

    foreach ($route in @('/api/r8-24/geo-growth/fast','/api/r8-24/geo-growth')) {
        # The new safe owner API does not lie about zero metrics on cold start.
        # It returns an immediate pending_snapshot while the real ledger is
        # reconstructed asynchronously. Verify each GET is fast AND the true
        # snapshot becomes ready within a bounded start-up window.
        $confirmed = $false
        $snapshot = $null
        for ($attempt = 0; $attempt -lt 40; $attempt++) {
            $watch = [System.Diagnostics.Stopwatch]::StartNew()
            $snapshot = Invoke-RestMethod -Uri ($base + $route) -Method Get -TimeoutSec 4
            $watch.Stop()
            if ($watch.Elapsed.TotalSeconds -gt 4.0) { throw "GEO owner snapshot exceeded 4 seconds: $route" }
            if ($snapshot.status_mode -eq 'fast_snapshot' -and $snapshot.status_ready -ne $false) {
                $confirmed = $true
                break
            }
            if ($snapshot.status_mode -ne 'pending_snapshot') {
                throw "Unexpected GEO owner snapshot mode: $($snapshot.status_mode) $route"
            }
            if ($null -ne $snapshot.formal_ab_completed) {
                throw "Pending GEO snapshot fabricated formal A/B results: $route"
            }
            Start-Sleep -Milliseconds 500
        }
        if (-not $confirmed) {
            $diagnostics = 'unavailable'
            try {
                $diagnostics = Invoke-RestMethod -Uri "$base/api/r8-24/geo-growth/fast-health" -TimeoutSec 3 | ConvertTo-Json -Compress -Depth 5
            } catch { $diagnostics = "health request failed: $($_.Exception.Message)" }
            $pending = if ($null -eq $snapshot) { 'no HTTP snapshot' } else { $snapshot | ConvertTo-Json -Compress -Depth 4 }
            throw "GEO true fast snapshot did not warm within 20 seconds: $route; diagnostics=$diagnostics; last_response=$pending"
        }
        if ([string]::IsNullOrWhiteSpace([string]$snapshot.state)) { throw "GEO owner snapshot missing state: $route" }
        if ([string]::IsNullOrWhiteSpace([string]$snapshot.mission)) { throw "GEO owner snapshot missing mission: $route" }
        if ([int]$snapshot.formal_ab_target -ne 50) { throw "GEO owner snapshot lost formal A/B target: $route" }
        if ($null -eq $snapshot.summary -or $null -eq $snapshot.cloud) { throw "GEO owner snapshot missing summary/cloud: $route" }
    }

    $geoHtml = (Invoke-WebRequest -Uri "$base/geo.html?embed=1" -UseBasicParsing -TimeoutSec 4).Content
    foreach ($marker in @('geo-growth-os.js','recoverGeoWorkbench','geo-direct-standalone-health')) {
        if ($geoHtml -notmatch [regex]::Escape($marker)) { throw "Installed GEO HTML missing recovery marker: $marker" }
    }

    $bundle = (Invoke-WebRequest -Uri "$base/operational-search.js" -UseBasicParsing -TimeoutSec 4).Content
    foreach ($marker in @('/api/r8-24/geo-growth/fast','__KZ_GEO_GROWTH_OS_BOOT__','KZ_GEO_TIMEOUT')) {
        if ($bundle -notmatch [regex]::Escape($marker)) { throw "Installed GEO bundle missing fast-owner marker: $marker" }
    }
    # Real browser DOM coverage is executed below through Selenium:
    # test_geo_browser_field.py validates the direct GEO page, while
    # test_owner_sidebar_browser.py validates the integrated owner route.
    # Avoid a second --dump-dom Chrome process here; active GEO timers can keep
    # that process alive despite a correct page and create a false CI timeout.
    Write-Host 'PASS: installed GEO owner HTTP/status/assets smoke passed; real browser DOM checks follow'
}
function Assert-GeoBrowserDom([int]$Port) {
    & $Python (Join-Path $PSScriptRoot 'test_geo_browser_field.py') --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Installed GEO real-browser DOM smoke failed' }
}

function Assert-PersistentFiles([hashtable]$Expected, [bool]$Exact) {
    foreach ($relative in $Expected.Keys) {
        $path = Join-Path $dataRoot $relative
        if (-not (Test-Path -LiteralPath $path)) { throw "Persistent user file missing: $relative" }
        # The packaged runtime writes UTF-8 JSON without a BOM. Windows
        # PowerShell 5 otherwise decodes it as the active ANSI code page and
        # can consume JSON quote bytes after Chinese multibyte characters.
        $raw = Get-Content -LiteralPath $path -Raw -Encoding UTF8
        try { $null = $raw | ConvertFrom-Json } catch { throw "Persistent user JSON became invalid: $relative" }
        if ($Exact -and $raw.Trim() -ne $Expected[$relative]) { throw "Clean reinstall changed persistent user file: $relative" }
    }
}
$runtime = $null
$testSucceeded = $false
try {
    $installerText = Get-Content -LiteralPath $installerScript -Raw
    if ($installerText -notmatch 'Install-KazuizhiPhase1Supervisor\.ps1') { throw 'Installer is missing the Phase-1 scheduled-task supervisor setup' }
    if ($installerText -notmatch 'Uninstall-KazuizhiPhase1Supervisor\.ps1') { throw 'Installer is missing supervisor cleanup' }
    if ($installerText -notmatch '\[InstallDelete\][\s\S]*\{userstartup\}[\s\S]*R8-23') { throw 'Installer does not retire the legacy startup shortcut' }
    New-Item -ItemType Directory -Force -Path $env:LOCALAPPDATA | Out-Null
    Install-R8
    $exe = Join-Path $testRoot $name
    $dataRoot = Join-Path $env:LOCALAPPDATA 'Kazuizhi_AI_Enterprise_V2.0.0_Beta/data'
    $supervisorInstall = Join-Path $dataRoot 'r8_25/service_install.json'
    if (-not (Test-Path -LiteralPath $supervisorInstall -PathType Leaf)) { throw 'Phase-1 supervisor install record missing' }
    $supervisorBytes = [System.IO.File]::ReadAllBytes($supervisorInstall)
    if ($supervisorBytes.Length -ge 3 -and $supervisorBytes[0] -eq 0xEF -and $supervisorBytes[1] -eq 0xBB -and $supervisorBytes[2] -eq 0xBF) { throw 'Phase-1 supervisor install record must be UTF-8 without BOM for Python JSON compatibility' }
    $supervisorRecord = Get-Content -LiteralPath $supervisorInstall -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $supervisorRecord.installed) { throw "Phase-1 supervisor was not installed: $($supervisorRecord.detail)" }
    if ($supervisorRecord.mode -notin @('user_scheduled_task','startup_shortcut_fallback')) { throw "Unexpected supervisor mode: $($supervisorRecord.mode)" }
    $supervisorRuntime = Get-Content -LiteralPath (Join-Path $dataRoot 'r8_25/runtime_supervisor.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $supervisorRuntime.installed -or $supervisorRuntime.install_mode -ne $supervisorRecord.mode) { throw 'Runtime supervisor ledger did not preserve the installed startup mode' }
    $version = (Get-Item -LiteralPath $exe).VersionInfo
    if ($version.FileVersion -ne '2.2.2.23' -or $version.ProductName -ne 'Kazuizhi AI Enterprise V2.2.2 R8-23 Final Workbench') { throw 'Windows EXE version mismatch' }
    foreach ($serverTool in @('R8-17_SERVER_ROOT_DISCOVERY_BOOTSTRAP.ps1', 'R8-17_SERVER_ROOT_DISCOVERY_BOOTSTRAP.cmd')) {
        if (-not (Test-Path -LiteralPath (Join-Path $testRoot $serverTool) -PathType Leaf)) { throw "Installed server root-discovery tool missing: $serverTool" }
    }
    foreach ($supervisorTool in @('Install-KazuizhiPhase1Supervisor.ps1', 'Uninstall-KazuizhiPhase1Supervisor.ps1')) {
        if (-not (Test-Path -LiteralPath (Join-Path $testRoot $supervisorTool) -PathType Leaf)) { throw "Installed Phase-1 supervisor tool missing: $supervisorTool" }
    }
    Verify-Runtime $exe

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
    & $Python (Join-Path $PSScriptRoot 'test_owner_sidebar_browser.py') --port $port
    if ($LASTEXITCODE -ne 0) { throw 'Owner sidebar real-Chrome interaction smoke failed' }
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
    $testSucceeded = $true
    Write-Host 'PASS: R8-23 Final Workbench install, GEO owner browser smoke, all-sidebar real Chrome click smoke, runtime verification, overwrite upgrade, data preservation and uninstall preservation'
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
    if ((Test-Path -LiteralPath $testRoot) -and -not $testSucceeded) {
        Write-Warning "Preserving failed installer test root for diagnosis: $testRoot"
    } elseif (Test-Path -LiteralPath $testRoot) {
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
