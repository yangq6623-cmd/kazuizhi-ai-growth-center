Write-Host "Building Kazuizhi AI V1.9.5 Installer"

$iss = "Kazuizhi_AI_V1.9.5_Setup.iss"

if (Get-Command iscc -ErrorAction SilentlyContinue) {
    iscc $iss
    Write-Host "Installer build complete"
} else {
    Write-Host "Inno Setup compiler not found"
    exit 1
}
