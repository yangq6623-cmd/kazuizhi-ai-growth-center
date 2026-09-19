param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$setup = Join-Path $root 'installer_output_v2/Kazuizhi_AI_Enterprise_V2.1.0_R8_Final.exe'
$testRoot = Join-Path $env:RUNNER_TEMP 'KazuizhiV2InstallerTest'
$name = 'Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe'
function Install-Beta {
    $proc = Start-Process -FilePath $setup -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', ('/DIR="' + $testRoot + '"')) -Wait -PassThru -WindowStyle Hidden
    if ($proc.ExitCode -ne 0) { throw "Install failed: $($proc.ExitCode)" }
}
function Assert-PersistentFiles([hashtable]$Expected) {
    foreach ($relative in $Expected.Keys) {
        $path = Join-Path $dataRoot $relative
        if (-not (Test-Path -LiteralPath $path)) { throw "Persistent user file missing after installer operation: $relative" }
        $actual = (Get-Content -LiteralPath $path -Raw).Trim()
        if ($actual -ne $Expected[$relative]) { throw "Persistent user file changed after clean installer operation: $relative" }
    }
}
function Assert-PersistentFilesExist([hashtable]$Expected) {
    foreach ($relative in $Expected.Keys) {
        $path = Join-Path $dataRoot $relative
        if (-not (Test-Path -LiteralPath $path)) { throw "Persistent user file missing after active-runtime installer operation: $relative" }
        $raw = Get-Content -LiteralPath $path -Raw
        try { $null = $raw | ConvertFrom-Json } catch { throw "Persistent user JSON became invalid after active-runtime installer operation: $relative" }
    }
}
Install-Beta
$exe = Join-Path $testRoot $name
$version = (Get-Item -LiteralPath $exe).VersionInfo
if ($version.FileVersion -ne '2.1.0.8' -or $version.ProductName -ne 'Kazuizhi AI Enterprise V2.1.0 R8 Final') { throw 'Windows EXE version mismatch' }
& $Python (Join-Path $PSScriptRoot 'verify_v2_autonomous.py') --exe $exe
if ($LASTEXITCODE -ne 0) { throw 'Installed autonomous runtime failed verification' }

# R8 Final intentionally preserves the proven R7/V2 user-data root so upgrades
# never orphan jobs, Memory, plans, audit records or business-source configuration.
$dataRoot = Join-Path $env:LOCALAPPDATA 'Kazuizhi_AI_Enterprise_V2.0.0_Beta/data'
New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
$sentinel = Join-Path $dataRoot 'user-data-preservation-test.txt'
Set-Content -LiteralPath $sentinel -Value 'preserve-v2-user-data'

# Seed the real R7 user-data namespaces. A normal reinstall with no runtime active
# must preserve these bytes exactly.
$persistentFiles = @{
    'r7\jobs.json' = '{"schema":1,"items":[{"title":"installer-persistence-job"}]}'
    'operations\tasks.json' = '{"items":[{"title":"installer-persistence-task"}]}'
    'promotion\keywords.json' = '{"items":[{"keyword":"installer-persistence-keyword"}]}'
    'promotion\history.json' = '{"items":[{"kind":"installer-persistence-draft"}]}'
    'summaries\today.json' = '{"completed_items":["installer-persistence-summary"]}'
    'plans\latest_plan.json' = '{"tasks":[{"title":"installer-persistence-plan"}]}'
    'memory\learning_memory.json' = '{"entries":[{"statement":"installer-persistence-memory"}]}'
}
foreach ($relative in $persistentFiles.Keys) {
    $path = Join-Path $dataRoot $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path) | Out-Null
    Set-Content -LiteralPath $path -Value $persistentFiles[$relative] -NoNewline
}

# First prove byte-exact preservation under a clean reinstall.
Install-Beta
if ((Get-Content -LiteralPath $sentinel -Raw).Trim() -ne 'preserve-v2-user-data') { throw 'Clean reinstall modified user data sentinel' }
Assert-PersistentFiles $persistentFiles

# Real-world upgrade regression: the visible runtime is running from the installed
# directory and holds packaged files open. Inno Setup Restart Manager must close
# the executable being replaced without custom taskkill code.
$activeProcesses = @(
    (Start-Process -FilePath $exe -ArgumentList @('--no-browser','--port','18876') -PassThru -WindowStyle Hidden)
)
Start-Sleep -Seconds 2
foreach ($runtime in $activeProcesses) {
    $runtime.Refresh()
    if ($runtime.HasExited) { throw "Upgrade regression setup failed: runtime $($runtime.Id) exited before reinstall" }
}

Install-Beta
foreach ($runtime in $activeProcesses) {
    try { $runtime.WaitForExit(5000) | Out-Null } catch {}
    $runtime.Refresh()
    if (-not $runtime.HasExited) { throw "Installer left active runtime/helper process running: $($runtime.Id)" }
}
# While the runtime is active it may legitimately update jobs/plans. The installer contract
# is that those files remain present and valid; byte equality is intentionally checked above
# in the clean-reinstall phase instead of confusing runtime writes with installer corruption.
if ((Get-Content -LiteralPath $sentinel -Raw).Trim() -ne 'preserve-v2-user-data') { throw 'Active-runtime reinstall modified user data sentinel' }
Assert-PersistentFilesExist $persistentFiles
& $Python (Join-Path $PSScriptRoot 'verify_v2_autonomous.py') --exe $exe
if ($LASTEXITCODE -ne 0) { throw 'Reinstalled autonomous runtime failed verification' }

$proc = Start-Process -FilePath (Join-Path $testRoot 'unins000.exe') -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru -WindowStyle Hidden
if ($proc.ExitCode -ne 0) { throw 'Uninstall failed' }
if (Test-Path -LiteralPath $exe) { throw 'Uninstall left application executable' }
if ((Get-Content -LiteralPath $sentinel -Raw).Trim() -ne 'preserve-v2-user-data') { throw 'Uninstall deleted persistent user data sentinel' }
Assert-PersistentFilesExist $persistentFiles
Remove-Item -LiteralPath $sentinel -Force
Write-Host 'PASS: R8 Final install, clean byte-exact reinstall preservation, Restart Manager active-runtime upgrade, Windows version, R7 core runtime verification, active data validity, uninstall preservation'
