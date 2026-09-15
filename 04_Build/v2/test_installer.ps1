param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$setup = Join-Path $root 'installer_output_v2/Kazuizhi_AI_Enterprise_V2.0.0_Beta_Setup.exe'
$testRoot = Join-Path $env:RUNNER_TEMP 'KazuizhiV2InstallerTest'
$name = 'Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe'
function Install-Beta {
    $proc = Start-Process -FilePath $setup -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', ('/DIR="' + $testRoot + '"')) -Wait -PassThru -WindowStyle Hidden
    if ($proc.ExitCode -ne 0) { throw "Install failed: $($proc.ExitCode)" }
}
Install-Beta
$exe = Join-Path $testRoot $name
$version = (Get-Item -LiteralPath $exe).VersionInfo
if ($version.FileVersion -ne '2.0.0.0' -or $version.ProductName -ne 'Kazuizhi AI Enterprise V2.0.0 Beta') { throw 'Windows EXE version mismatch' }
& $Python (Join-Path $PSScriptRoot 'verify_v2.py') --exe $exe
if ($LASTEXITCODE -ne 0) { throw 'Installed runtime failed verification' }
$sentinel = Join-Path $testRoot 'user-data-preservation-test.txt'
Set-Content -LiteralPath $sentinel -Value 'preserve-v2-user-data'
Install-Beta
if ((Get-Content -LiteralPath $sentinel -Raw).Trim() -ne 'preserve-v2-user-data') { throw 'Reinstall modified user data' }
& $Python (Join-Path $PSScriptRoot 'verify_v2.py') --exe $exe
if ($LASTEXITCODE -ne 0) { throw 'Reinstalled runtime failed verification' }
$proc = Start-Process -FilePath (Join-Path $testRoot 'unins000.exe') -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru -WindowStyle Hidden
if ($proc.ExitCode -ne 0) { throw 'Uninstall failed' }
if (Test-Path -LiteralPath $exe) { throw 'Uninstall left application executable' }
if ((Get-Content -LiteralPath $sentinel -Raw).Trim() -ne 'preserve-v2-user-data') { throw 'Uninstall deleted user data' }
Write-Host 'PASS: install, Windows version, launch, reinstall, user-data preservation, uninstall'
