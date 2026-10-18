param(
    [string]$SiteRoot = 'C:\\inetpub\\kazuizhi',
    [string]$PublicBaseUrl = 'https://kazuizhi.com/'
)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $argsList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"{0}"' -f $PSCommandPath), '-SiteRoot', ('"{0}"' -f $SiteRoot), '-PublicBaseUrl', ('"{0}"' -f $PublicBaseUrl))
    Start-Process -FilePath 'powershell.exe' -ArgumentList ($argsList -join ' ') -Verb RunAs
    exit
}

$folder = Split-Path -Parent $PSCommandPath
$exe = Join-Path $folder 'Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe'
$resultFile = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Kazuizhi_R8-17_ROOT_DISCOVERY_RESULT.json'
if (-not (Test-Path -LiteralPath $SiteRoot -PathType Container)) { throw "Site root does not exist: $SiteRoot" }
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Kazuizhi executable not found beside this script' }

Remove-Item -LiteralPath $resultFile -Force -ErrorAction SilentlyContinue
$process = Start-Process -FilePath $exe -ArgumentList @('--r8-17-root-discovery-bootstrap', '--site-root', $SiteRoot, '--public-base-url', $PublicBaseUrl, '--result-file', $resultFile) -Wait -PassThru
if (Test-Path -LiteralPath $resultFile -PathType Leaf) { Get-Content -LiteralPath $resultFile -Raw | Write-Host }
exit [int]$process.ExitCode
