param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    & $Python '04_Build/v2/verify_v2_autonomous.py' --source
    if ($LASTEXITCODE -ne 0) { throw 'Inherited R8 source verification failed' }
    & $Python '04_Build/v2/verify_r8_operational.py' --source
    if ($LASTEXITCODE -ne 0) { throw 'V2.2 Operational source verification failed' }
    & $Python -m PyInstaller --noconfirm --clean --distpath dist_v2 --workpath build_v2 '04_Build/kazuizhi_v2.0.0.spec'
    if ($LASTEXITCODE -ne 0) { throw 'V2 PyInstaller build failed' }

    $portable = 'dist_v2/Kazuizhi_AI_Enterprise_V2.0.0_Beta'
    $bootstrapPs1 = '04_Build/v2/R8-15_SERVER_BOOTSTRAP.ps1'
    $bootstrapCmd = '04_Build/v2/R8-15_SERVER_BOOTSTRAP.cmd'
    Copy-Item -LiteralPath $bootstrapPs1 -Destination $portable -Force
    Copy-Item -LiteralPath $bootstrapCmd -Destination $portable -Force
    if (-not (Test-Path -LiteralPath (Join-Path $portable 'R8-15_SERVER_BOOTSTRAP.ps1') -PathType Leaf)) { throw 'R8-15 PowerShell bootstrap missing from portable package' }
    if (-not (Test-Path -LiteralPath (Join-Path $portable 'R8-15_SERVER_BOOTSTRAP.cmd') -PathType Leaf)) { throw 'R8-15 CMD bootstrap missing from portable package' }

    & $Python '04_Build/v2/verify_v2_autonomous.py' --exe 'dist_v2/Kazuizhi_AI_Enterprise_V2.0.0_Beta/Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Inherited R8 packaged verification failed' }
    & $Python '04_Build/v2/verify_r8_operational.py' --exe 'dist_v2/Kazuizhi_AI_Enterprise_V2.0.0_Beta/Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe'
    if ($LASTEXITCODE -ne 0) { throw 'V2.2 Operational packaged verification failed' }
    & '04_Build/installer/build_installer_v2.ps1'
} finally { Pop-Location }
