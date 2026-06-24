# Shared helpers for OpenClaw Grafana + Prometheus (Windows native binaries)
$script:OpenClawGrafanaRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:OpenClawGrafanaBinDir = Join-Path $script:OpenClawGrafanaRoot ".bin"
$script:OpenClawGrafanaVer = "11.5.2"
$script:OpenClawPromVer = "2.55.1"

function Ensure-OpenClawDir([string]$Path) {
    if (-not (Test-Path $Path)) { New-Item -ItemType Directory -Path $Path -Force | Out-Null }
}

function Download-OpenClawIfMissing([string]$Url, [string]$Dest) {
    if (Test-Path $Dest) {
        $len = (Get-Item $Dest).Length
        if ($len -gt 1MB) { return }
    }
    Write-Host "Downloading $Url ..."
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
}

function Expand-OpenClawIfMissing([string]$Zip, [string]$DestDir, [string]$Marker) {
    if (Test-Path $Marker) { return (Split-Path (Split-Path $Marker -Parent) -Parent) }
    Ensure-OpenClawDir $DestDir
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

function Test-OpenClawMetricsHttp([string]$Url, [int]$TimeoutSec = 5) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Wait-OpenClawMetricsHttp([string]$Url, [int]$TimeoutSec = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-OpenClawMetricsHttp $Url 5) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Stop-OpenClawMetricsPort([int]$Port) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { return }
    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $procIds) {
        Write-Host "Port $Port in use by PID $procId, stopping..."
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

function Write-OpenClawWatchdogLog([string]$Message) {
    $logDir = Join-Path $script:OpenClawGrafanaRoot "logs"
    Ensure-OpenClawDir $logDir
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path (Join-Path $logDir "watchdog.log") -Value $line -Encoding utf8
}

function Find-OpenClawBinary([string]$BinDir, [string]$ExeName) {
    if (-not (Test-Path $BinDir)) { return $null }
    $found = Get-ChildItem -Path $BinDir -Recurse -Filter $ExeName -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $found) { return $null }
    if ($ExeName -eq "grafana-server.exe") {
        return [pscustomobject]@{
            Exe  = $found.FullName
            Home = Split-Path (Split-Path $found.FullName -Parent) -Parent
        }
    }
    return [pscustomobject]@{
        Exe  = $found.FullName
        Home = Split-Path $found.FullName -Parent
    }
}

function Initialize-OpenClawMetricsStack {
    param(
        [switch]$SkipDownload
    )

    $here = $script:OpenClawGrafanaRoot
    $binDir = $script:OpenClawGrafanaBinDir
    $gv = $script:OpenClawGrafanaVer
    $pv = $script:OpenClawPromVer

    Ensure-OpenClawDir $binDir

    $grafana = Find-OpenClawBinary $binDir "grafana-server.exe"
    $prom = Find-OpenClawBinary $binDir "prometheus.exe"

    if (-not $grafana -or -not $prom) {
        if ($SkipDownload) {
            throw "Grafana/Prometheus binaries not found under $binDir - run start_grafana.ps1 once"
        }
        $grafanaZip = "grafana-$gv.windows-amd64.zip"
        $promZip = "prometheus-$pv.windows-amd64.zip"
        $grafanaZipPath = Join-Path $binDir $grafanaZip
        $promZipPath = Join-Path $binDir $promZip
        Download-OpenClawIfMissing "https://dl.grafana.com/oss/release/$grafanaZip" $grafanaZipPath
        Download-OpenClawIfMissing "https://github.com/prometheus/prometheus/releases/download/v$pv/$promZip" $promZipPath

        if (-not $grafana) {
            $grafanaHome = Expand-OpenClawIfMissing $grafanaZipPath $binDir (Join-Path $binDir "grafana-$gv\bin\grafana-server.exe")
            $grafana = Find-OpenClawBinary $binDir "grafana-server.exe"
            if (-not $grafana) { throw "grafana-server.exe not found under $binDir" }
        }
        if (-not $prom) {
            $null = Expand-OpenClawIfMissing $promZipPath $binDir (Join-Path $binDir "prometheus-$pv.windows-amd64\prometheus.exe")
            $prom = Find-OpenClawBinary $binDir "prometheus.exe"
            if (-not $prom) { throw "prometheus.exe not found under $binDir" }
        }
    }

    $grafanaExe = $grafana.Exe
    $grafanaHome = $grafana.Home
    $promExe = $prom.Exe
    $promHome = $prom.Home

    $grafanaData = Join-Path $here "data"
    $grafanaLogs = Join-Path $here "logs"
    $promData = Join-Path $here "prometheus-data"
    Ensure-OpenClawDir $grafanaData
    Ensure-OpenClawDir $grafanaLogs
    Ensure-OpenClawDir $promData

    $provSrc = Join-Path $here "provisioning"
    $provDst = Join-Path $grafanaHome "conf\provisioning"
    if (Test-Path $provSrc) {
        Ensure-OpenClawDir $provDst
        Copy-Item -Path (Join-Path $provSrc "*") -Destination $provDst -Recurse -Force
    }

    $iniDst = Join-Path $grafanaHome "conf\custom.ini"
    $ini = @"
[paths]
data = $grafanaData
logs = $grafanaLogs
provisioning = $provDst

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
mode = file
level = warn
"@
    Set-Content -Path $iniDst -Value $ini -Encoding utf8

  return [pscustomobject]@{
        Here         = $here
        GrafanaExe   = $grafanaExe
        GrafanaHome  = $grafanaHome
        GrafanaIni   = $iniDst
        PromExe      = $promExe
        PromHome     = $promHome
        PromCfg      = Join-Path $here "prometheus.yml"
        PromData     = $promData
        GrafanaLogs  = $grafanaLogs
    }
}

function Test-OpenClawMetricsBinsInstalled {
    $binDir = $script:OpenClawGrafanaBinDir
    if (-not (Test-Path $binDir)) { return $false }
    $g = Get-ChildItem -Path $binDir -Recurse -Filter "grafana-server.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    $p = Get-ChildItem -Path $binDir -Recurse -Filter "prometheus.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    return ($null -ne $g -and $null -ne $p)
}

function Start-OpenClawPrometheus {
    param(
        [Parameter(Mandatory)][pscustomobject]$Stack,
        [ValidateSet("Normal", "Hidden")][string]$WindowStyle = "Hidden",
        [switch]$ForceRestart
    )

    if ($ForceRestart) { Stop-OpenClawMetricsPort 9090 }
    if (Test-OpenClawMetricsHttp "http://127.0.0.1:9090/-/ready" 3) { return $true }

    $outLog = Join-Path $Stack.GrafanaLogs "prometheus.out.log"
    $errLog = Join-Path $Stack.GrafanaLogs "prometheus.err.log"
    $style = if ($WindowStyle -eq "Hidden") { "Hidden" } else { "Normal" }

    Start-Process -FilePath $Stack.PromExe -ArgumentList @(
        "--config.file=$($Stack.PromCfg)",
        "--storage.tsdb.path=$($Stack.PromData)",
        "--web.listen-address=127.0.0.1:9090"
    ) -WorkingDirectory $Stack.PromHome -WindowStyle $style `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog | Out-Null

    return (Wait-OpenClawMetricsHttp "http://127.0.0.1:9090/-/ready" 45)
}

function Start-OpenClawGrafana {
    param(
        [Parameter(Mandatory)][pscustomobject]$Stack,
        [ValidateSet("Normal", "Hidden")][string]$WindowStyle = "Hidden",
        [switch]$ForceRestart
    )

    if ($ForceRestart) { Stop-OpenClawMetricsPort 3000 }
    if (Test-OpenClawMetricsHttp "http://127.0.0.1:3000/api/health" 3) { return $true }

    $outLog = Join-Path $Stack.GrafanaLogs "grafana.out.log"
    $errLog = Join-Path $Stack.GrafanaLogs "grafana.err.log"
    $style = if ($WindowStyle -eq "Hidden") { "Hidden" } else { "Normal" }
    $env:GF_PATHS_CONFIG = $Stack.GrafanaIni

    Start-Process -FilePath $Stack.GrafanaExe -ArgumentList @(
        "--homepath=$($Stack.GrafanaHome)",
        "--config=$($Stack.GrafanaIni)"
    ) -WorkingDirectory $Stack.GrafanaHome -WindowStyle $style `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog | Out-Null

    return (Wait-OpenClawMetricsHttp "http://127.0.0.1:3000/api/health" 120)
}

function Start-OpenClawMetricsStack {
    param(
        [ValidateSet("Normal", "Hidden")][string]$WindowStyle = "Hidden",
        [switch]$ForceRestart,
        [switch]$SkipDownload
    )

    if ($ForceRestart) {
        Stop-OpenClawMetricsPort 9090
        Stop-OpenClawMetricsPort 3000
    }

    $stack = Initialize-OpenClawMetricsStack -SkipDownload:$SkipDownload
    $promOk = Start-OpenClawPrometheus -Stack $stack -WindowStyle $WindowStyle -ForceRestart:$ForceRestart
    $grafOk = Start-OpenClawGrafana -Stack $stack -WindowStyle $WindowStyle -ForceRestart:$ForceRestart
    return [pscustomobject]@{
        Stack       = $stack
        Prometheus  = $promOk
        Grafana     = $grafOk
    }
}

function Start-OpenClawMetricsWatchdog {
    param([string]$GrafanaRoot = $script:OpenClawGrafanaRoot)

    $pidFile = Join-Path $GrafanaRoot ".watchdog.pid"
    if (Test-Path $pidFile) {
        $oldPid = [int](Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($oldPid -gt 0) {
            $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
            if ($proc -and $proc.Path -like "*powershell*") { return $oldPid }
        }
    }

    $watchdog = Join-Path $GrafanaRoot "watchdog.ps1"
    if (-not (Test-Path $watchdog)) { throw "watchdog.ps1 not found: $watchdog" }

    $logDir = Join-Path $GrafanaRoot "logs"
    Ensure-OpenClawDir $logDir
    $outLog = Join-Path $logDir "watchdog.out.log"
    $errLog = Join-Path $logDir "watchdog.err.log"

    $p = Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", $watchdog
    ) -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog

    $p.Id | Set-Content -Path $pidFile -Encoding ascii
    return $p.Id
}
