Write-Host "Building Kazuizhi AI V1.9.5 Enterprise Installer"

$root = Resolve-Path "$PSScriptRoot\..\.."
$output = Join-Path $root "installer_output"
New-Item -ItemType Directory -Force -Path $output | Out-Null

Set-Location $PSScriptRoot

# Locate Inno Setup script dynamically to avoid filename mismatch
$iss = Get-ChildItem -Path $PSScriptRoot -Filter "*.iss" | Select-Object -First 1

if ($null -eq $iss) {
    throw "No Inno Setup script found"
}

Write-Host "Using installer script: $($iss.FullName)"

if (Get-Command iscc -ErrorAction SilentlyContinue) {
    iscc $iss.FullName
} else {
    Write-Host "Inno Setup compiler not found"
    throw "Missing Inno Setup compiler"
}

# Search generated installer dynamically. Do not bind to old Alpha/legacy names.
$setup = Get-ChildItem -Path $root -Filter "*Setup.exe" -Recurse | Select-Object -First 1

if ($null -eq $setup) {
    throw "Installer exe was not generated"
}

Copy-Item $setup.FullName (Join-Path $output $setup.Name) -Force

Write-Host "Installer output created"
Write-Host "Installer: $($setup.FullName)"
Get-ChildItem $output
