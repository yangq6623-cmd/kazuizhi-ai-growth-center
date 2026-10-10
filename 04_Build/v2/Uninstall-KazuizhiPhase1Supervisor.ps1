$ErrorActionPreference = 'SilentlyContinue'
$taskName = 'Kazuizhi AI Phase1 Supervisor'
$startupPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Kazuizhi AI Phase1 Supervisor.lnk'
Stop-ScheduledTask -TaskName $taskName
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
if (Test-Path -LiteralPath $startupPath) { Remove-Item -LiteralPath $startupPath -Force }
