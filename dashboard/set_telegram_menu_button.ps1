# Обновить только кнопку меню бота (без туннеля)
param(
    [string]$PublicUrl = "",
    [string]$MenuText = "",
    [string]$BotToken = ""
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = "C:\Users\Admin\.openclaw\.env"

function Read-DotEnvKey([string]$Key) {
    if (-not (Test-Path $EnvFile)) { return "" }
    foreach ($line in Get-Content $EnvFile -Encoding UTF8) {
        if ($line -match "^\s*$Key\s*=\s*(.+)$") {
            return $Matches[1].Trim().Trim('"').Trim("'")
        }
    }
    return ""
}

function Default-MenuText {
    $clip = [System.Text.Encoding]::UTF8.GetString([byte[]](0xF0, 0x9F, 0x93, 0x8B))
    return $clip + " " + [char]0x0417 + [char]0x0430 + [char]0x0434 + [char]0x0430 + [char]0x0447 + [char]0x0438
}

if (-not $BotToken) {
    $BotToken = $env:TELEGRAM_MINIAPP_BOT_TOKEN
    if (-not $BotToken) { $BotToken = $env:TELEGRAM_BOT_TOKEN }
    if (-not $BotToken) { $BotToken = Read-DotEnvKey "TELEGRAM_BOT_TOKEN" }
}

if (-not $MenuText) {
    $MenuText = $env:TELEGRAM_MINIAPP_MENU_TEXT
    if (-not $MenuText) { $MenuText = Read-DotEnvKey "TELEGRAM_MINIAPP_MENU_TEXT" }
    if (-not $MenuText) { $MenuText = Default-MenuText }
}

if (-not $PublicUrl) {
    $PublicUrl = $env:TELEGRAM_MINIAPP_URL
    if (-not $PublicUrl) { $PublicUrl = Read-DotEnvKey "TELEGRAM_MINIAPP_URL" }
    if (-not $PublicUrl) {
        $errLog = Join-Path $Here "cloudflared-miniapp.err.log"
        if (Test-Path $errLog) {
            $m = Select-String -Path $errLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1
            if ($m) { $PublicUrl = $m.Matches[0].Value }
        }
    }
}

if (-not $PublicUrl) {
    Write-Host "URL not found. Pass -PublicUrl https://xxxx.trycloudflare.com" -ForegroundColor Yellow
    exit 1
}

if (-not $BotToken) {
    Write-Host "No TELEGRAM_BOT_TOKEN in .env" -ForegroundColor Yellow
    exit 1
}

$miniappUrl = ($PublicUrl.TrimEnd('/')) + "/miniapp"
Write-Host "Menu button: $MenuText" -ForegroundColor Cyan
Write-Host "URL: $miniappUrl" -ForegroundColor Green

$bodyObj = @{ menu_button = @{ type = "web_app"; text = $MenuText; web_app = @{ url = $miniappUrl } } }
$body = $bodyObj | ConvertTo-Json -Depth 5 -Compress
$utf8Body = [System.Text.Encoding]::UTF8.GetBytes($body)
$uri = "https://api.telegram.org/bot$BotToken/setChatMenuButton"
Invoke-RestMethod -Uri $uri -Method Post -ContentType "application/json; charset=utf-8" -Body $utf8Body | Out-Null
Write-Host "Done." -ForegroundColor Green
