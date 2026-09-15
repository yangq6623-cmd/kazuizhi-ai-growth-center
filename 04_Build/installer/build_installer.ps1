Write-Host "Building Kazuizhi AI V1.9.5 Enterprise Installer"

$root = Resolve-Path "$PSScriptRoot\..\.."
$output = Join-Path $root "installer_output"

# Clean old installer output to prevent stale package reuse
if (Test-Path $output) {
    Remove-Item $output -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $output | Out-Null

Set-Location $PSScriptRoot

$iss = Get-ChildItem -Path $PSScriptRoot -Filter "*.iss" | Select-Object -First 1

if ($null -eq $iss) {
    throw "No Inno Setup script found"
}

Write-Host "Using installer script: $($iss.FullName)"

if (Get-Command iscc -ErrorAction SilentlyContinue) {
    iscc $iss.FullName
} else {
    throw "Missing Inno Setup compiler"
}

$setup = Get-ChildItem -Path $root -Filter "*Setup.exe" -Recurse | Where-Object { $_.FullName -notlike "*installer_output*" } | Select-Object -First 1

if ($null -eq $setup) {
    throw "Installer exe was not generated"
}

Copy-Item $setup.FullName (Join-Path $output $setup.Name) -Force

Write-Host "Installer output created"
Write-Host "Installer: $($setup.FullName)"
Get-ChildItem $output
