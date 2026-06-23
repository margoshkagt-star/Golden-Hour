<#
.SYNOPSIS
    Notes-Bot Kit — удаление установки.

.DESCRIPTION
    1. Убивает watchdog и bot-процессы.
    2. Удаляет Scheduled Task (если есть).
    3. Спрашивает про удаление файлов runtime + .env + memory.

.PARAMETER InstallRoot
    Откуда удалять. По умолчанию $env:LOCALAPPDATA\NotesBotKit.

.PARAMETER KeepData
    Не удалять memory/ (notes.jsonl, inbox, ideas.md, skills-digest.md).

.EXAMPLE
    .\uninstall.ps1
    .\uninstall.ps1 -InstallRoot D:\NotesBotKit -KeepData
#>
[CmdletBinding()]
param(
    [string]$InstallRoot,
    [switch]$KeepData
)

$ErrorActionPreference = "Stop"
if (-not $InstallRoot) { $InstallRoot = Join-Path $env:LOCALAPPDATA "NotesBotKit" }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Notes-Bot Kit — uninstaller" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "InstallRoot: $InstallRoot"
Write-Host ""

# ---------- 1. Kill processes ----------
Write-Host "[1/3] Останавливаю процессы ..." -ForegroundColor Yellow
$procs = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        return ($cmd -and ($cmd -match 'telegram_notes_bot'))
    } catch { return $false }
}
if ($procs) {
    $procs | ForEach-Object { Write-Host "  Killing PID $($_.Id)" -ForegroundColor DarkYellow }
    $procs | Stop-Process -Force
} else {
    Write-Host "  Активных процессов бота не найдено." -ForegroundColor DarkGray
}

# ---------- 2. Remove scheduled task ----------
Write-Host "[2/3] Удаляю Scheduled Task ..." -ForegroundColor Yellow
$TaskName = "NotesBotKitWatchdog"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  Task '$TaskName' удалён." -ForegroundColor Green
} else {
    Write-Host "  Task '$TaskName' не найден." -ForegroundColor DarkGray
}

# ---------- 3. Remove files ----------
Write-Host "[3/3] Удаляю файлы ..." -ForegroundColor Yellow
if (-not (Test-Path $InstallRoot)) {
    Write-Host "  Папка $InstallRoot не существует — нечего удалять." -ForegroundColor DarkGray
    return
}
if ($KeepData) {
    Write-Host "  -KeepData: сохраняю memory/ (notes.jsonl, inbox, ideas.md) ..." -ForegroundColor DarkYellow
    $temp = Join-Path $env:TEMP "NotesBotKit_memory_backup_$(Get-Date -Format yyyyMMdd_HHmmss)"
    Move-Item -Path (Join-Path $InstallRoot "memory") -Destination $temp -Force
    Remove-Item -Path $InstallRoot -Recurse -Force
    New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
    Move-Item -Path $temp -Destination (Join-Path $InstallRoot "memory") -Force
    Write-Host "  Files удалены, memory сохранён в $InstallRoot\memory." -ForegroundColor Green
} else {
    $confirm = Read-Host "  Точно удалить $InstallRoot (включая memory/notes.jsonl)? [y/N]"
    if ($confirm -eq 'y' -or $confirm -eq 'Y') {
        Remove-Item -Path $InstallRoot -Recurse -Force
        Write-Host "  Удалено." -ForegroundColor Green
    } else {
        Write-Host "  Отменено." -ForegroundColor DarkYellow
    }
}

# ---------- 4. Optional: clean ~/.openclaw/.env ----------
$OpenClawEnv = Join-Path $env:USERPROFILE ".openclaw\.env"
if ((Test-Path $OpenClawEnv) -and -not $KeepData) {
    $ans = Read-Host "  Удалить строки TEAM_BOT_TOKEN/TELEGRAM_BOT_TOKEN из $OpenClawEnv ? [y/N]"
    if ($ans -eq 'y' -or $ans -eq 'Y') {
        $clean = Get-Content $OpenClawEnv | Where-Object { $_ -notmatch '^\s*(TEAM_BOT_TOKEN|TELEGRAM_BOT_TOKEN)\s*=' }
        Set-Content -LiteralPath $OpenClawEnv -Value $clean -Encoding UTF8
        Write-Host "  .env очищен." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Готово." -ForegroundColor Cyan
