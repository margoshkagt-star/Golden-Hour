# Start local Prometheus + Grafana for OpenClaw metrics (Windows, no Docker)
param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$BinDir = Join-Path $Here ".bin"
$GrafanaVer = "11.5.2"
$PromVer = "2.55.1"
$GrafanaZip = "grafana-$GrafanaVer.windows-amd64.zip"
$PromZip = "prometheus-$PromVer.windows-amd64.zip"
$GrafanaUrl = "https://dl.grafana.com/oss/release/$GrafanaZip"
$PromUrl = "https://github.com/prometheus/prometheus/releases/download/v$PromVer/$PromZip"

function Ensure-Dir([string]$Path) {
    if (-not (Test-Path $Path)) { New-Item -ItemType Directory -Path $Path -Force | Out-Null }
}

function Download-IfMissing([string]$Url, [string]$Dest) {
    if (Test-Path $Dest) {
        $len = (Get-Item $Dest).Length
        if ($len -gt 1MB) { Write-Host "Already downloaded: $(Split-Path -Leaf $Dest) ($([math]::Round($len/1MB)) MB)"; return }
    }
    Write-Host "Downloading $Url ..."
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
}

function Expand-IfMissing([string]$Zip, [string]$DestDir, [string]$Marker) {
    if (Test-Path $Marker) { return (Split-Path (Split-Path $Marker -Parent) -Parent) }
    Ensure-Dir $DestDir
    Write-Host "Extracting $(Split-Path -Leaf $Zip) (may take 1-2 min) ..."
    Expand-Archive -Path $Zip -DestinationPath $DestDir -Force
    if (-not (Test-Path $Marker)) {
        $found = Get-ChildItem -Path $DestDir -Recurse -Filter (Split-Path $Marker -Leaf) -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            return (Split-Path (Split-Path $found.FullName -Parent) -Parent)
        }
        throw "After extract, not found: $Marker"
    }
    return (Split-Path (Split-Path $Marker -Parent) -Parent)
}

function Stop-Port([int]$Port) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { return }
    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $procIds) {
        Write-Host "Port $Port in use by PID $procId, stopping..."
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

function Wait-Http([string]$Url, [int]$TimeoutSec = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
        } catch {}
        Start-Sleep -Seconds 2
    }
    return $false
}

Ensure-Dir $BinDir
$GrafanaZipPath = Join-Path $BinDir $GrafanaZip
$PromZipPath = Join-Path $BinDir $PromZip
Download-IfMissing $GrafanaUrl $GrafanaZipPath
Download-IfMissing $PromUrl $PromZipPath

$GrafanaHome = Expand-IfMissing $GrafanaZipPath $BinDir (Join-Path $BinDir "grafana-$GrafanaVer\bin\grafana-server.exe")
$GrafanaExe = Join-Path $GrafanaHome "bin\grafana-server.exe"
if (-not (Test-Path $GrafanaExe)) {
  $alt = Get-ChildItem -Path $BinDir -Recurse -Filter "grafana-server.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($alt) {
    $GrafanaExe = $alt.FullName
    $GrafanaHome = Split-Path (Split-Path $GrafanaExe -Parent) -Parent
  } else {
    throw "grafana-server.exe not found under $BinDir"
  }
}

$PromHome = Expand-IfMissing $PromZipPath $BinDir (Join-Path $BinDir "prometheus-$PromVer.windows-amd64\prometheus.exe")
$PromExe = Join-Path $PromHome "prometheus.exe"
if (-not (Test-Path $PromExe)) {
  $alt = Get-ChildItem -Path $BinDir -Recurse -Filter "prometheus.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($alt) {
    $PromExe = $alt.FullName
    $PromHome = Split-Path $PromExe -Parent
  } else {
    throw "prometheus.exe not found under $BinDir"
  }
}

$GrafanaData = Join-Path $Here "data"
$GrafanaLogs = Join-Path $Here "logs"
$PromData = Join-Path $Here "prometheus-data"
Ensure-Dir $GrafanaData
Ensure-Dir $GrafanaLogs
Ensure-Dir $PromData

$ProvSrc = Join-Path $Here "provisioning"
$ProvDst = Join-Path $GrafanaHome "conf\provisioning"
if (Test-Path $ProvSrc) {
    Ensure-Dir $ProvDst
    Copy-Item -Path (Join-Path $ProvSrc "*") -Destination $ProvDst -Recurse -Force
}

$IniDst = Join-Path $GrafanaHome "conf\custom.ini"
$ini = @"
[paths]
data = $GrafanaData
logs = $GrafanaLogs
provisioning = $ProvDst

[server]
http_addr = 127.0.0.1
http_port = 3000
domain = 127.0.0.1
root_url = http://127.0.0.1:3000/

[security]
allow_embedding = true
cookie_samesite = lax

[auth.anonymous]
enabled = true
org_name = Main Org.
org_role = Viewer

[users]
default_theme = dark
allow_sign_up = false

[log]
mode = console
level = warn
"@
Set-Content -Path $IniDst -Value $ini -Encoding utf8

$PromCfg = Join-Path $Here "prometheus.yml"
Stop-Port 9090
Stop-Port 3000

Write-Host "Starting Prometheus on http://127.0.0.1:9090 ..."
Start-Process -FilePath $PromExe -ArgumentList @(
    "--config.file=$PromCfg",
    "--storage.tsdb.path=$PromData",
    "--web.listen-address=127.0.0.1:9090"
) -WorkingDirectory $PromHome -WindowStyle Normal

if (-not (Wait-Http 'http://127.0.0.1:9090/-/ready' 30)) {
    Write-Warning 'Prometheus slow to start - check the Prometheus window'
}

Write-Host "Starting Grafana on http://127.0.0.1:3000 ..."
$env:GF_PATHS_CONFIG = $IniDst
Start-Process -FilePath $GrafanaExe -ArgumentList @(
    "--homepath=$GrafanaHome",
    "--config=$IniDst"
) -WorkingDirectory $GrafanaHome -WindowStyle Normal

if (-not (Wait-Http 'http://127.0.0.1:3000/api/health' 120)) {
    Write-Error 'Grafana did not start on port 3000. Check the Grafana console window.'
    exit 1
}

$url = 'http://127.0.0.1:3000/d/openclaw-overview/openclaw-overview?orgId=1&refresh=30s&kiosk'
Write-Host ""
Write-Host 'OK Grafana:  http://127.0.0.1:3000/  (use port 3000, not bare 127.0.0.1)'
Write-Host "OK Dashboard: $url"
Write-Host 'OK Prometheus: http://127.0.0.1:9090'
Write-Host 'OK Felpik: http://127.0.0.1:18790/ then Costs tab Grafana'
Write-Host ""
if (-not $NoBrowser) {
    Start-Process $url
}
