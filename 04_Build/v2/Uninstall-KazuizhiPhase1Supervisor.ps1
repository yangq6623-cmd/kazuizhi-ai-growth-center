$ErrorActionPreference = 'SilentlyContinue'
$taskName = 'Kazuizhi AI Phase1 Supervisor'
$startupPath = Join-Path ([Environment]::GetFolderPath('Startup')) '卡嘴子 AI 第一阶段后台守护.lnk'
Stop-ScheduledTask -TaskName $taskName
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
if (Test-Path -LiteralPath $startupPath) { Remove-Item -LiteralPath $startupPath -Force }
