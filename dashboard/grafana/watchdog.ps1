# Keep Prometheus (:9090) and Grafana (:3000) alive — restarts if they exit.
$ErrorActionPreference = "Continue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $Here "lib.ps1")

$intervalSec = 20
Write-OpenClawWatchdogLog "watchdog started (PID $PID)"

try {
    $stack = Initialize-OpenClawMetricsStack -SkipDownload
} catch {
    Write-OpenClawWatchdogLog "init failed: $_"
    exit 1
}

while ($true) {
  try {
    if (-not (Test-OpenClawMetricsHttp "http://127.0.0.1:9090/-/ready" 4)) {
      Write-OpenClawWatchdogLog "Prometheus down - starting"
      if (-not (Start-OpenClawPrometheus -Stack $stack -WindowStyle Hidden)) {
        Write-OpenClawWatchdogLog "Prometheus failed to start (see logs/prometheus.err.log)"
      }
    }
    if (-not (Test-OpenClawMetricsHttp "http://127.0.0.1:3000/api/health" 4)) {
      Write-OpenClawWatchdogLog "Grafana down - starting"
      if (-not (Start-OpenClawGrafana -Stack $stack -WindowStyle Hidden)) {
        Write-OpenClawWatchdogLog "Grafana failed to start (see logs/grafana.err.log)"
      }
    }
  } catch {
    Write-OpenClawWatchdogLog "loop error: $_"
  }
  Start-Sleep -Seconds $intervalSec
}
