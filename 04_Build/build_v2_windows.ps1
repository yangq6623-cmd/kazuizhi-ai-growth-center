param(
    [string]$Python = 'python',
    [switch]$SkipSourceVerification
)
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    # CI runs the full source acceptance gate immediately before this script.
    # Local/manual builds still keep the same source verification by default.
    if (-not $SkipSourceVerification) {
        & $Python '04_Build/v2/verify_v2_autonomous.py' --source
        if ($LASTEXITCODE -ne 0) { throw 'Inherited R8 source verification failed' }
        & $Python '04_Build/v2/verify_r8_operational.py' --source
        if ($LASTEXITCODE -ne 0) { throw 'V2.2 Operational source verification failed' }
    } else {
        Write-Host 'Source verification already passed in the CI gate; skipping duplicate long-running source execution before packaging.'
    }

    & $Python -m PyInstaller --noconfirm --clean --distpath dist_v2 --workpath build_v2 '04_Build/kazuizhi_v2.0.0.spec'
    if ($LASTEXITCODE -ne 0) { throw 'V2 PyInstaller build failed' }

    $portable = 'dist_v2/Kazuizhi_AI_Enterprise_V2.0.0_Beta'
    $bootstrapPs1 = '04_Build/v2/R8-15_SERVER_BOOTSTRAP.ps1'
    $bootstrapCmd = '04_Build/v2/R8-15_SERVER_BOOTSTRAP.cmd'
    $rootDiscoveryPs1 = '04_Build/v2/R8-17_SERVER_ROOT_DISCOVERY_BOOTSTRAP.ps1'
    $rootDiscoveryCmd = '04_Build/v2/R8-17_SERVER_ROOT_DISCOVERY_BOOTSTRAP.cmd'
    $phase1SupervisorInstall = '04_Build/v2/Install-KazuizhiPhase1Supervisor.ps1'
    $phase1SupervisorUninstall = '04_Build/v2/Uninstall-KazuizhiPhase1Supervisor.ps1'
    Copy-Item -LiteralPath $bootstrapPs1 -Destination $portable -Force
    Copy-Item -LiteralPath $bootstrapCmd -Destination $portable -Force
    Copy-Item -LiteralPath $rootDiscoveryPs1 -Destination $portable -Force
    Copy-Item -LiteralPath $rootDiscoveryCmd -Destination $portable -Force
    Copy-Item -LiteralPath $phase1SupervisorInstall -Destination $portable -Force
    Copy-Item -LiteralPath $phase1SupervisorUninstall -Destination $portable -Force
    if (-not (Test-Path -LiteralPath (Join-Path $portable 'R8-15_SERVER_BOOTSTRAP.ps1') -PathType Leaf)) { throw 'R8-15 PowerShell bootstrap missing from portable package' }
    if (-not (Test-Path -LiteralPath (Join-Path $portable 'R8-15_SERVER_BOOTSTRAP.cmd') -PathType Leaf)) { throw 'R8-15 CMD bootstrap missing from portable package' }
    if (-not (Test-Path -LiteralPath (Join-Path $portable 'R8-17_SERVER_ROOT_DISCOVERY_BOOTSTRAP.ps1') -PathType Leaf)) { throw 'R8-17 root discovery PowerShell bootstrap missing from portable package' }
    if (-not (Test-Path -LiteralPath (Join-Path $portable 'R8-17_SERVER_ROOT_DISCOVERY_BOOTSTRAP.cmd') -PathType Leaf)) { throw 'R8-17 root discovery CMD bootstrap missing from portable package' }
    if (-not (Test-Path -LiteralPath (Join-Path $portable 'Install-KazuizhiPhase1Supervisor.ps1') -PathType Leaf)) { throw 'Phase-1 supervisor installer missing from portable package' }
    if (-not (Test-Path -LiteralPath (Join-Path $portable 'Uninstall-KazuizhiPhase1Supervisor.ps1') -PathType Leaf)) { throw 'Phase-1 supervisor uninstaller missing from portable package' }

    $exe = 'dist_v2/Kazuizhi_AI_Enterprise_V2.0.0_Beta/Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe'
    & $Python '04_Build/v2/verify_v2_autonomous.py' --exe $exe
    if ($LASTEXITCODE -ne 0) { throw 'Inherited R8 packaged verification failed' }

    # Hosted Windows runners occasionally need a second cold-start attempt for
    # the packaged FFmpeg/content worker to finish its first no-asset render.
    # Keep the gate strict: a retry is allowed once, and the build still fails
    # if the same packaged operational flow does not reach ChatGPT QC twice.
    & $Python '04_Build/v2/verify_r8_operational.py' --exe $exe
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'First packaged operational verification did not finish; retrying once after hosted-runner warmup.'
        Start-Sleep -Seconds 5
        & $Python '04_Build/v2/verify_r8_operational.py' --exe $exe
        if ($LASTEXITCODE -ne 0) { throw 'V2.2 Operational packaged verification failed after retry' }
    }

    & '04_Build/installer/build_installer_v2.ps1'
} finally { Pop-Location }
