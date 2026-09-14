# Kazuizhi AI V1.9.5 Alpha Windows Build Script
# Target: Kazuizhi_AI_V1.9.5_Alpha.exe

$ErrorActionPreference = 'Stop'

Write-Host 'Kazuizhi AI V1.9.5 Alpha Build Start'

python -m pip install -r ../03_V1.9.5_Source/requirements.txt

pyinstaller ../04_Build/kazuizhi_v1.9.5.spec

Write-Host 'Build Finished'
Write-Host 'Check dist output directory.'
