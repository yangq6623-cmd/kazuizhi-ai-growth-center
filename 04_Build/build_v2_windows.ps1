param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '..')
try {
    & $Python '04_Build/v2/verify_v2_autonomous.py' --source
    if ($LASTEXITCODE -ne 0) { throw 'V2 source verification failed' }
    & $Python -m PyInstaller --noconfirm --clean --distpath dist_v2 --workpath build_v2 '04_Build/kazuizhi_v2.0.0.spec'
    if ($LASTEXITCODE -ne 0) { throw 'V2 PyInstaller build failed' }
    & $Python '04_Build/v2/verify_v2_autonomous.py' --exe 'dist_v2/Kazuizhi_AI_Enterprise_V2.0.0_Beta/Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe'
    if ($LASTEXITCODE -ne 0) { throw 'V2 packaged runtime verification failed' }
    & '04_Build/installer/build_installer_v2.ps1'
} finally { Pop-Location }
