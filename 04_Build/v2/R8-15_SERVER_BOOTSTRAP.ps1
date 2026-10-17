param(
    [string]$SiteRoot = 'C:\inetpub\kazuizhi',
    [string]$PublicBaseUrl = 'https://kazuizhi.com/'
)

$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$admin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    $argsList = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $PSCommandPath),
        '-SiteRoot', ('"{0}"' -f $SiteRoot),
        '-PublicBaseUrl', ('"{0}"' -f $PublicBaseUrl)
    )
    Start-Process -FilePath 'powershell.exe' -ArgumentList ($argsList -join ' ') -Verb RunAs
    exit
}

$folder = Split-Path -Parent $PSCommandPath
$exe = Join-Path $folder 'Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe'
$resultFile = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Kazuizhi_R8-15_DEPLOY_RESULT.json'

Write-Host '============================================================'
Write-Host 'Kazuizhi R8-15 SEO/GEO public deploy bootstrap'
Write-Host ('Site root: ' + $SiteRoot)
Write-Host ('Public URL: ' + $PublicBaseUrl)
Write-Host ('Managed write scope only: ' + (Join-Path $SiteRoot 'seo'))
Write-Host 'Protected: Web.config / App_Data / SQL / APK / uploads'
Write-Host '============================================================'

if (-not (Test-Path -LiteralPath $SiteRoot -PathType Container)) {
    Write-Error "Site root does not exist: $SiteRoot"
    exit 3
}
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    Write-Error "Kazuizhi executable not found beside this script: $exe"
    exit 2
}

Remove-Item -LiteralPath $resultFile -Force -ErrorAction SilentlyContinue
$arguments = @(
    '--r8-15-server-bootstrap',
    '--site-root', $SiteRoot,
    '--public-base-url', $PublicBaseUrl,
    '--result-file', $resultFile
)
$process = Start-Process -FilePath $exe -ArgumentList $arguments -Wait -PassThru
$code = [int]$process.ExitCode

Write-Host ('R8-15 process exit code: ' + $code)
if (Test-Path -LiteralPath $resultFile -PathType Leaf) {
    Write-Host ('Deployment report: ' + $resultFile)
    Get-Content -LiteralPath $resultFile -Raw | Write-Host
} else {
    Write-Warning 'No deployment report was produced. Keep this window open and send a screenshot for diagnosis.'
}

if ($code -eq 0) {
    Write-Host 'R8-15 field bootstrap completed. Only verified real public URLs count as PUBLISHED.'
} else {
    Write-Warning 'R8-15 field bootstrap did not reach a clean verified publish state. The report contains the exact gate that stopped it.'
}

Read-Host 'Press Enter to close'
exit $code
