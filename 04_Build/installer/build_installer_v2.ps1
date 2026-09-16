$ErrorActionPreference = 'Stop'
$compiler = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (!$compiler) { $compiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
if (!(Test-Path -LiteralPath $compiler)) { throw 'Inno Setup 6 compiler missing' }
& $compiler (Join-Path $PSScriptRoot 'Kazuizhi_AI_V2.0.0_Beta_Setup.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed: $LASTEXITCODE" }
$setup = Join-Path $PSScriptRoot '../../installer_output_v2/Kazuizhi_AI_Enterprise_V2.0.0_Beta_R7_UX1_Setup.exe'
if (!(Test-Path -LiteralPath $setup)) { throw 'V2 R7.1 Setup was not produced' }
