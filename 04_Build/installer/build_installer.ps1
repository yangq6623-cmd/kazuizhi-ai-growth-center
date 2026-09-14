Write-Host "Building Kazuizhi AI V1.9.5 Installer"

$root = Resolve-Path "$PSScriptRoot\..\.."
$output = Join-Path $root "installer_output"
New-Item -ItemType Directory -Force -Path $output | Out-Null

$iss = Join-Path $PSScriptRoot "Kazuizhi_AI_V1.9.5_Setup.iss"

if (Get-Command iscc -ErrorAction SilentlyContinue) {
    iscc $iss
} else {
    Write-Host "Inno Setup compiler not found"
    throw "Missing Inno Setup compiler"
}

$setup = Get-ChildItem -Path $PSScriptRoot -Filter "Kazuizhi_AI_V1.9.5_Setup.exe" -Recurse | Select-Object -First 1

if ($null -eq $setup) {
    throw "Installer exe was not generated"
}

Copy-Item $setup.FullName (Join-Path $output $setup.Name) -Force
Write-Host "Installer output created"
Get-ChildItem $output
