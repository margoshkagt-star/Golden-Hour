# Start local Prometheus + Grafana for OpenClaw metrics (Windows, no Docker)
param(
    [switch]$NoBrowser,
    [switch]$Watchdog,
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $Here "lib.ps1")

if ($Watchdog) {
    $wdPid = Start-OpenClawMetricsWatchdog -GrafanaRoot $Here
    Write-Host "Watchdog running (PID $wdPid) - auto-restarts Grafana/Prometheus"
    Write-Host "Logs: $Here\logs\watchdog.log"
    Start-Sleep -Seconds 3
}

$result = Start-OpenClawMetricsStack -WindowStyle $(if ($Watchdog) { "Hidden" } else { "Normal" }) -ForceRestart:$ForceRestart

if (-not $result.Prometheus) {
    Write-Warning "Prometheus slow to start - see logs\prometheus.err.log"
}
if (-not $result.Grafana) {
    Write-Error "Grafana did not start on port 3000. See logs\grafana.err.log"
    exit 1
}

$url = 'http://127.0.0.1:3000/d/openclaw-overview/openclaw-overview?orgId=1&refresh=30s&kiosk'
Write-Host ""
Write-Host 'OK Grafana:  http://127.0.0.1:3000/'
Write-Host "OK Dashboard: $url"
Write-Host 'OK Prometheus: http://127.0.0.1:9090'
Write-Host 'OK Felpik: http://127.0.0.1:18790/ then Costs tab Grafana'
if ($Watchdog) {
    Write-Host ""
    Write-Host "Watchdog: keeps services alive (close only via Task Manager or stop watchdog PID)"
}
Write-Host ""
if (-not $NoBrowser) {
    Start-Process $url
}
