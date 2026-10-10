$ErrorActionPreference = 'SilentlyContinue'
$taskName = 'Kazuizhi AI Phase1 Supervisor'
$startupPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Kazuizhi AI Phase1 Supervisor.lnk'
$exePath = Join-Path $PSScriptRoot 'Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe'
Stop-ScheduledTask -TaskName $taskName
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
if (Test-Path -LiteralPath $startupPath) { Remove-Item -LiteralPath $startupPath -Force }
Start-Sleep -Milliseconds 750
Get-Process -Name 'Kazuizhi_AI_Enterprise_V2.0.0_Beta' | Where-Object {
    try { $_.Path -eq $exePath } catch { $false }
} | Stop-Process -Force
for ($attempt = 0; $attempt -lt 10; $attempt++) {
    $remaining = @(Get-Process -Name 'Kazuizhi_AI_Enterprise_V2.0.0_Beta' | Where-Object {
        try { $_.Path -eq $exePath } catch { $false }
    })
    if (-not $remaining) { break }
    Start-Sleep -Milliseconds 250
}
