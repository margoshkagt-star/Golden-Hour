# Open chat with auto-login via Felpik dashboard /go/chat
param(
    [string]$SessionKey = "agent:main:main",
    [int]$DashboardPort = 18790,
    [switch]$WaitForGateway
)

$ErrorActionPreference = "Continue"
$HostAddr = "127.0.0.1"
$GwPort = 18789

if ($WaitForGateway) {
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        $gw = Get-NetTCPConnection -LocalPort $GwPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($gw) { break }
        Start-Sleep -Seconds 2
    }
}

$gw = Get-NetTCPConnection -LocalPort $GwPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $gw) {
    Write-Host "Gateway not running on :$GwPort. Run: openclaw gateway restart"
    exit 1
}

$db = Get-NetTCPConnection -LocalPort $DashboardPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $db) {
    Write-Host "Dashboard not running on :$DashboardPort. Run: .\start_dashboard.ps1"
    exit 1
}

$sessionEncoded = [uri]::EscapeDataString($SessionKey)
$url = "http://${HostAddr}:${DashboardPort}/go/chat?session=$sessionEncoded"
Write-Host "Opening chat (auto-login): session=$SessionKey"
Start-Process $url
