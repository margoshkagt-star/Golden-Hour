# OPERATIONS — эксплуатация Notes-Bot Kit

> Ежедневная работа: логи, рестарты, бэкапы, дебаг, типичные проблемы.

## Содержание

1. [Где логи](#1-где-логи)
2. [Проверка состояния](#2-проверка-состояния)
3. [Рестарт](#3-рестарт)
4. [Бэкап данных](#4-бэкап-данных)
5. [Типичные проблемы](#5-типичные-проблемы)
6. [Дебаг intake / forge](#6-дебаг-intake--forge)
7. [Обновление конфига на лету](#7-обновление-конфига-на-лету)
8. [Мониторинг (опционально)](#8-мониторинг-опционально)

---

## 1. Где логи

| Файл | Что пишется | Ротация |
|---|---|---|
| `<install>/scripts/telegram_notes_bot.log` | Бот: каждый update, ошибки хендлеров, транскрипты, решения forge | append-only, вручную |
| `<install>/scripts/telegram_notes_bot.watchdog.log` | Watchdog: spawn, exit codes, backoff | append-only, вручную |
| `<install>/memory/skills-digest.md` | Forge-операции: slug, summary, ts | append-only |
| `<install>/memory/forge_results.jsonl` | Результаты forge-skill (успех/фейл + summary) | append-only |

### Хвост логов (live)

```powershell
# Бот
Get-Content "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.log" -Tail 50 -Wait

# Watchdog
Get-Content "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.watchdog.log" -Tail 20 -Wait
```

### Что искать в логе бота

**Хороший update:**
```
2026-06-23 14:30:01 INFO aiogram.dispatcher: Update 12345 is handled. Duration 47 ms
2026-06-23 14:30:01 INFO notes_bot: auto-queued for forge: 'Бот должен присылать мотивационные цитаты...'
```

**Гreeting проигнорирован (фикс Bug #1):**
```
2026-06-23 14:30:15 INFO notes_bot: greeting skipped: 'привет'
```

**Short message, не триггерит forge:**
```
2026-06-23 14:30:20 INFO notes_bot: short message, skip auto_skill: 'ок'
```

**Voice транскрибирован:**
```
2026-06-23 14:30:25 INFO notes_bot: voice downloaded: <file_id>.ogg (12345 bytes)
2026-06-23 14:30:32 INFO notes_bot: voice transcribed: 8.2s, 47 chars
```

**Ошибка:**
```
2026-06-23 14:30:40 ERROR notes_bot: voice download/transcribe pipeline failed: <Traceback>
```

---

## 2. Проверка состояния

### Быстрая сводка

```powershell
# Какие python-процессы бота запущены
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        return ($cmd -and ($cmd -match 'telegram_notes_bot'))
    } catch { return $false }
} | Format-Table Id, StartTime

# Должно быть РОВНО 2:
#   watchdog  (start time ~ log on)
#   bot       (start time ~ чуть позже watchdog)
```

### Сколько идей / заметок

```powershell
# Всего строк в notes.jsonl
(Get-Content "$env:LOCALAPPDATA\NotesBotKit\memory\notes.jsonl" | Measure-Object -Line).Lines

# Forgeable в очереди
Get-Content "$env:LOCALAPPDATA\NotesBotKit\memory\forge_queue.jsonl" | ForEach-Object {
    $_.Trim() | ConvertFrom-Json
} | Where-Object { $_.status -eq 'pending' } | Measure-Object | Select-Object -ExpandProperty Count

# Готово (за всё время)
Get-Content "$env:LOCALAPPDATA\NotesBotKit\memory\forge_results.jsonl" | ForEach-Object {
    $_.Trim() | ConvertFrom-Json
} | Where-Object { $_.status -eq 'done' } | Measure-Object | Select-Object -ExpandProperty Count
```

### Последняя активность

```powershell
# Последние 5 заметок
Get-Content "$env:LOCALAPPDATA\NotesBotKit\memory\notes.jsonl" -Tail 5 | ForEach-Object {
    $_.Trim() | ConvertFrom-Json | Format-Table ts, kind, @{n='author';e={$_.username}}, @{n='content';e={$_.content.Substring(0, [Math]::Min(50, $_.content.Length))}}
}

# Последние 5 дней inbox'а
Get-ChildItem "$env:LOCALAPPDATA\NotesBotKit\memory\inbox\*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name, LastWriteTime
```

---

## 3. Рестарт

### Мягкий рестарт (рекомендуется)

Watchdog сам поднимет бота, если его убить:
```powershell
# Убить ТОЛЬКО бот (НЕ watchdog)
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        return ($cmd -and ($cmd -match 'telegram_notes_bot\.py') -and ($cmd -notmatch 'watchdog'))
    } catch { return $false }
} | Stop-Process -Force

# Watchdog через 5 сек spawn'нет новый бот
Get-Content "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.watchdog.log" -Tail 5 -Wait
```

### Жёсткий рестарт (watchdog + bot)

```powershell
# Убить оба
Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        return ($cmd -and ($cmd -match 'telegram_notes_bot'))
    } catch { return $false }
} | Stop-Process -Force

# Подождать 5 сек
Start-Sleep -Seconds 5

# Запустить заново (отдельно от Scheduled Task — для отладки)
python "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot_watchdog.py"
```

Через Ctrl+C (или закрытие окна) watchdog корректно завершается. Если бот запускается через Scheduled Task — он перезапустится автоматически.

### Рестарт через Scheduled Task

```powershell
# Остановить task (watchdog завершится)
Stop-ScheduledTask -TaskName "NotesBotKitWatchdog"

# Запустить заново
Start-ScheduledTask -TaskName "NotesBotKitWatchdog"

# Проверить статус
Get-ScheduledTask -TaskName "NotesBotKitWatchdog" | Format-List State, LastRunTime, LastTaskResult
```

---

## 4. Бэкап данных

### Что бэкапить

**Критично:**
- `memory/notes.jsonl` — все заметки (append-only, может вырасти до десятков MB)
- `memory/bot-config.json` — конфиг
- `memory/members.json` — реестр handle'ов

**Полезно (можно восстановить):**
- `memory/inbox/*.md` — дневные дампы (восстановимы из notes.jsonl)
- `memory/forge_queue.jsonl` — очередь forge
- `memory/forge_results.jsonl` — лог forge
- `memory/skills-digest.md` — forge-история
- `media/inbound/*.ogg`, `*.txt` — голосовые и транскрипты

**НЕ бэкапим:**
- `__pycache__/` — пересоздаётся автоматически
- `.env` (опционально, удобно) — но безопаснее НЕ бэкапить, токен в менеджере паролей
- Логи (ротируются)

### Ручной бэкап

```powershell
$Root = "$env:LOCALAPPDATA\NotesBotKit"
$Backup = "$env:USERPROFILE\NotesBotBackups\$(Get-Date -Format yyyyMMdd_HHmmss)"
New-Item -ItemType Directory -Force -Path $Backup | Out-Null

# Критичное
Copy-Item "$Root\memory\notes.jsonl" "$Backup\"
Copy-Item "$Root\memory\bot-config.json" "$Backup\"
Copy-Item "$Root\memory\members.json" "$Backup\"

# Опционально
Copy-Item -Recurse "$Root\memory\inbox" "$Backup\inbox"
Copy-Item "$Root\memory\forge_queue.jsonl" "$Backup\"
Copy-Item "$Root\memory\forge_results.jsonl" "$Backup\"
Copy-Item "$Root\memory\skills-digest.md" "$Backup\"

Write-Host "Backup: $Backup"
```

### Автоматический бэкап (через Scheduled Task)

Создай `backup.ps1`:
```powershell
$Root = "$env:LOCALAPPDATA\NotesBotKit"
$BackupDir = "$env:USERPROFILE\NotesBotBackups"
$Keep = 14  # дней

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$stamp = Get-Date -Format yyyyMMdd_HHmmss
$dst = "$BackupDir\$stamp"
New-Item -ItemType Directory -Force -Path $dst | Out-Null

Copy-Item "$Root\memory\notes.jsonl" "$dst\"
Copy-Item "$Root\memory\bot-config.json" "$dst\"
Copy-Item "$Root\memory\members.json" "$dst\"
Copy-Item -Recurse "$Root\memory\inbox" "$dst\inbox"

# Удалить старые
Get-ChildItem $BackupDir -Directory | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$Keep) } | Remove-Item -Recurse -Force

# Сжать текущий
Compress-Archive -Path "$dst\*" -DestinationPath "$dst.zip" -Force
Remove-Item -Recurse -Force $dst
```

Регистрация в Планировщике:
```powershell
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\Path\To\backup.ps1"
$Trigger = New-ScheduledTaskTrigger -Daily -At "03:00"
Register-ScheduledTask -TaskName "NotesBotKitBackup" -Action $Action -Trigger $Trigger -RunLevel Highest -Force
```

### Восстановление из бэкапа

```powershell
# Останови бота
Stop-ScheduledTask -TaskName "NotesBotKitWatchdog"

# Восстанови файлы
$RestoreFrom = "$env:USERPROFILE\NotesBotBackups\20260623_030000"
$Root = "$env:LOCALAPPDATA\NotesBotKit"

Copy-Item "$RestoreFrom\notes.jsonl" "$Root\memory\notes.jsonl" -Force
Copy-Item "$RestoreFrom\bot-config.json" "$Root\memory\bot-config.json" -Force
Copy-Item "$RestoreFrom\members.json" "$Root\memory\members.json" -Force

# Запустить бота
Start-ScheduledTask -TaskName "NotesBotKitWatchdog"
```

---

## 5. Типичные проблемы

### Проблема: бот молчит

**Симптом:** отправляешь сообщение — ответа нет.

**Диагностика:**
```powershell
# 1. Бот запущен?
Get-Process python | Where-Object { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -match 'telegram_notes_bot' }
# Если пусто — watchdog тоже мёртв

# 2. Watchdog в Scheduled Task?
Get-ScheduledTask -TaskName "NotesBotKitWatchdog" | Format-List State, LastTaskResult

# 3. Лог watchdog
Get-Content "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.watchdog.log" -Tail 30
```

**Фиксы:**
- Watchdog мёртв → запустить Scheduled Task или руками `python ...telegram_notes_bot_watchdog.py`
- Бот мёртв, watchdog жив → watchdog сам поднимет через 5 сек
- Оба живы, но молчат → проверь `TELEGRAM_BOT_TOKEN` в `.env` (см. INSTALL.md #7)
- Бот падает с ошибкой → смотри `telegram_notes_bot.log` последние 50 строк

---

### Проблема: «два бота» (конфликт polling)

**Симптом:** в `telegram_notes_bot.log`:
```
ERROR aiogram.dispatcher: terminated by other getUpdates request
```

**Фикс:**
```powershell
# Убить ВСЕ bot-процессы (оставить watchdog если он есть)
Get-Process python | Where-Object {
    (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine -match 'telegram_notes_bot\.py'
} | Stop-Process -Force

# Watchdog через 5 сек поднимет новый
Start-Sleep -Seconds 10

# Проверить — должен быть ровно 1 бот
(Get-Process python | Where-Object { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine -match 'telegram_notes_bot\.py' }).Count
```

---

### Проблема: «/start» не отвечает «хозяин»

**Симптом:** бот отвечает "Принято ✅" вместо "Привет, хозяин!".

**Причина:** `bot-config.json → owner.username` не совпадает с твоим Telegram username.

**Фикс:**
```powershell
$cfg = Get-Content "$env:LOCALAPPDATA\NotesBotKit\memory\bot-config.json" -Raw | ConvertFrom-Json
$cfg.owner.username = "my_real_username"  # без @
$cfg | ConvertTo-Json -Depth 5 | Set-Content "$env:LOCALAPPDATA\NotesBotKit\memory\bot-config.json" -Encoding UTF8

# Рестарт бота (НЕ watchdog)
Get-Process python | Where-Object { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine -match 'telegram_notes_bot\.py' } | Stop-Process -Force
```

---

### Проблема: голосовые не транскрибируются

**Симптом:** бот отвечает "Записано 🎙 (Xs) — без транскрипта (Whisper недоступен)".

**Диагностика:**
```powershell
# 1. faster-whisper установлен?
python -c "import faster_whisper; print('ok', faster_whisper.__version__)" 2>&1

# 2. ffmpeg в PATH?
ffmpeg -version 2>&1 | Select-Object -First 1

# 3. bot-config.json → asr.server_side = true?
(Get-Content "$env:LOCALAPPDATA\NotesBotKit\memory\bot-config.json" -Raw | ConvertFrom-Json).asr.server_side

# 4. voice-transcribe skill установлен?
Test-Path "$env:LOCALAPPDATA\NotesBotKit\skills\voice-transcribe\scripts\transcribe.py"
```

**Фиксы:**
- Whisper не стоит → `pip install faster-whisper` + первый запуск скачает модель (~500MB)
- ffmpeg нет → скачать с https://www.gyan.dev/ffmpeg/builds/, распаковать, добавить в PATH
- `asr.server_side = false` → переключить в `bot-config.json` + рестарт бота
- skill не установлен → взять из этого пакета `agent-skills/notes-voice-transcribe.md` (SKILL.md) → применить

---

### Проблема: `/skills` ничего не делает

**Симптом:** бот отвечает "🛠 Сгенерировано 0 драфтов".

**Причины:**
1. Нет forgeable-идей (все < 30 символов или все greetings)
2. `workspace/Golden-Hour/` папка не существует → бот не может создать там SKILL.md

**Диагностика:**
```powershell
# 1. Сколько forgeable?
python "$env:LOCALAPPDATA\NotesBotKit\scripts\idea_intake.py" --dry-run 2>&1 | Select-String "ideas|rejected"

# 2. Папка Golden-Hour есть?
Test-Path "$env:USERPROFILE\.openclaw\workspace\Golden-Hour\skills"
# или другой путь — смотри WORKSPACE в idea_to_skill.py
```

**Фиксы:**
- Создай `workspace/Golden-Hour/skills/` вручную
- Или используй **forge-skill агента** — он гибче в путях (см. `agent-skills/notes-forge-pipeline.md`)

---

## 6. Дебаг intake / forge

### Ручной прогон intake

```powershell
# Полная классификация, dry-run (ничего не пишет)
python "$env:LOCALAPPDATA\NotesBotKit\scripts\idea_intake.py" --dry-run

# С записью в memory/ideas.md
python "$env:LOCALAPPDATA\NotesBotKit\scripts\idea_intake.py"

# Только новые с последнего запуска
python "$env:LOCALAPPDATA\NotesBotKit\scripts\idea_intake.py" --new-only
```

### Сколько forgeable-идей в очереди

```powershell
$queue = Get-Content "$env:LOCALAPPDATA\NotesBotKit\memory\forge_queue.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$queue | Group-Object status | Format-Table Name, Count
```

### Утилита forge_check.py

```powershell
# Показывает последние 15 заметок и помечает forgeable
python "$env:LOCALAPPDATA\NotesBotKit\scripts\forge_check.py"
```

### Сбросить состояние intake

```powershell
# Если хочешь переклассифицировать ВСЁ с нуля
Remove-Item "$env:LOCALAPPDATA\NotesBotKit\memory\ideas_state.json"

# Следующий /classify (или запуск idea_intake.py) обработает всё
python "$env:LOCALAPPDATA\NotesBotKit\scripts\idea_intake.py"
```

### Очистить forge_queue.jsonl

```powershell
# Удалить все pending (например после восстановления forge-skill)
$queue = Get-Content "$env:LOCALAPPDATA\NotesBotKit\memory\forge_queue.jsonl" | ForEach-Object { $_ | ConvertFrom-Json }
$keep = $queue | Where-Object { $_.status -ne 'pending' } | ForEach-Object { $_ | ConvertTo-Json -Compress }
$keep | Set-Content "$env:LOCALAPPDATA\NotesBotKit\memory\forge_queue.jsonl" -Encoding UTF8
```

---

## 7. Обновление конфига на лету

Большинство полей `bot-config.json` **НЕ требует рестарта** — бот читает его при каждом вызове:

- `owner`, `team` — подхватываются мгновенно
- `commands` — меню Telegram нужно явно обновить через `/start` (бот шлёт `set_my_commands` при старте)
- `digest.interval_hours` — подхватывается при следующем цикле (через ≤3ч)
- `asr.server_side` — требует рестарта бота (инициализация пайплайна)

**Поля, требующие рестарта бота:**
- Любые пути (но они hardcoded — не меняй без нужды)

**Как понять, что бот подхватил изменение:**
- `is_owner(user)` вызывается на каждый update → если поменял `owner.username`, сразу заработает
- `load_config()` — кэша нет, читается с диска каждый раз

---

## 8. Мониторинг (опционально)

### Heartbeat от бота

Бот каждую минуту пишет в лог `Update handled`. Если 5+ минут тишины — что-то не так.

```powershell
# Алертилка: если последняя строка лога старше 10 мин
$log = "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.log"
$last = (Get-Item $log).LastWriteTime
$age = (Get-Date) - $last
if ($age.TotalMinutes -gt 10) {
    Write-Warning "Бот молчит уже $($age.TotalMinutes) мин"
}
```

### Telegram-уведомление о падении

Бот сам шлёт в Telegram при `get_me` failure 5 попыток подряд — запись об ошибке в логе. Чтобы получить активный алерт, добавь в Scheduled Task `NotesBotKitWatchdog`:

```powershell
# В install.ps1 при создании task:
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 99 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 0)  # бесконечно
```

Плюс добавь в `telegram_notes_bot_watchdog.py` логику «если 10 рестартов подряд за 5 минут — отправь alert». Это P2 задача, не реализовано в v1.

---

## 9. Полезные алиасы

Добавь в свой PowerShell profile (`$PROFILE`):

```powershell
function nb-status {
    $procs = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        try { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine -match 'telegram_notes_bot' }
        catch { $false }
    }
    Write-Host "Notes-Bot processes: $($procs.Count)"
    $procs | Format-Table Id, StartTime, @{n='script';e={if ((Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -match 'watchdog') {'watchdog'} else {'bot'}}}
}

function nb-restart {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        try { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine -match 'telegram_notes_bot\.py' }
        catch { $false }
    } | Stop-Process -Force
    Write-Host "Bot killed. Watchdog поднимет через 5 сек."
}

function nb-tail {
    Get-Content "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.log" -Tail 30 -Wait
}

function nb-tail-wd {
    Get-Content "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.watchdog.log" -Tail 30 -Wait
}

function nb-queue {
    $q = Get-Content "$env:LOCALAPPDATA\NotesBotKit\memory\forge_queue.jsonl" -ErrorAction SilentlyContinue | ForEach-Object { $_ | ConvertFrom-Json }
    $q | Group-Object status | Format-Table Name, Count
    $pending = $q | Where-Object { $_.status -eq 'pending' } | Select-Object -First 10
    if ($pending) { $pending | Format-Table queued_at, @{n='preview';e={$_.content.Substring(0, [Math]::Min(60, $_.content.Length))}} }
}

Set-Alias nbs nb-status
Set-Alias nbr nb-restart
Set-Alias nbt nb-tail
Set-Alias nbd nb-tail-wd
Set-Alias nbq nb-queue
```

Теперь в любой сессии:
```powershell
nbs    # статус
nbr    # рестарт бота
nbt    # хвост лога бота
nbd    # хвост watchdog
nbq    # forge queue
```
