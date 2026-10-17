$ErrorActionPreference = 'Stop'
$command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$candidates = @(
    $(if ($command) { $command.Source }),
    $(Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
    $(Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    $(Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$compiler = $candidates | Select-Object -First 1
if (!$compiler) { throw 'Inno Setup 6 compiler missing' }
& $compiler (Join-Path $PSScriptRoot 'Kazuizhi_AI_V2.0.0_Beta_Setup.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed: $LASTEXITCODE" }
$setup = Join-Path $PSScriptRoot '../../installer_output_v2/Kazuizhi_AI_Enterprise_V2.2.2_R8_Autonomous_Mission_Core.exe'
if (!(Test-Path -LiteralPath $setup)) { throw 'V2.2.2 R8 Autonomous Mission Core Setup was not produced' }
