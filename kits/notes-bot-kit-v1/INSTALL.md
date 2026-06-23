# INSTALL — пошаговая установка Notes-Bot Kit

> Читай от начала до конца. Если что-то непонятно — открой ARCHITECTURE.md или OPERATIONS.md.

## 0. Требования

| Что | Минимум | Проверить |
|---|---|---|
| OS | Windows 10/11 | — |
| PowerShell | 5.1+ | `$PSVersionTable.PSVersion` |
| Python | 3.10+ (НЕ WindowsApps stub) | `python --version` |
| pip | встроен в Python | `python -m pip --version` |
| Telegram-аккаунт | владелец бота | — |
| Свободное место | ~200 MB (без Whisper) / ~1.5 GB (с faster-whisper) | — |

### Проверь Python

```powershell
# ПЛОХО (WindowsApps stub — выдаёт пустую версию, бот НЕ запустится):
python --version    # может быть пусто или Microsoft Store stub

# ХОРОШО (реальный интерпретатор):
C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe --version
# или
py --version
```

Если в PATH только WindowsApps stub — установи Python 3.12 с [python.org](https://www.python.org/downloads/) и/или задай `$env:NOTES_BOT_PYTHON`.

### Проверь aiogram

```powershell
python -c "import aiogram, aiohttp; print(aiogram.__version__, aiohttp.__version__)"
# Должно напечатать что-то вроде: 3.13.0 3.10.10
```

Если нет:
```powershell
python -m pip install --upgrade pip
python -m pip install aiogram aiohttp
```

Опционально (для голосовых):
```powershell
python -m pip install faster-whisper
# + ffmpeg в PATH: https://www.gyan.dev/ffmpeg/builds/
```

---

## 1. Создай бота в Telegram

1. Открой Telegram → найди [@BotFather](https://t.me/BotFather)
2. `/newbot`
3. Имя: `My Team Ideas` (или как хочешь)
4. Username: `MyTeamIdeasBot` (должен заканчиваться на `Bot`, быть уникальным)
5. Скопируй токен: `1234567890:AAHxYz...` (формат `<digits>:<35+ chars>`)

**Сразу настрой команды бота (опционально, бот выставит сам при старте, но можешь заранее):**

```
/setcommands → @MyTeamIdeasBot
start - Регистрация владельца
info - Сводка по идеям
ideas - Все идеи участников
skills - Сгенерировать драфты SKILL.md из идей
rejected - Отсеянные идеи
split - Разбить идею на под-идеи
classify - Обновить ideas.md
```

---

## 2. Установка через install.ps1 (рекомендуется)

```powershell
# Из папки kit'а
cd notes-bot-kit-v1

# Вариант A: токен аргументом
.\install.ps1 -BotToken "1234567890:AAHxYz..."

# Вариант B: токен из .env (создай .env рядом с install.ps1, см. .env.example)
.\install.ps1

# Кастомный путь установки
.\install.ps1 -BotToken "..." -InstallRoot D:\NotesBotKit

# Только запуск, без регистрации в Планировщике задач
.\install.ps1 -BotToken "..." -SkipScheduledTask
```

Что делает install.ps1:

1. Копирует `runtime/scripts/` → `$InstallRoot\scripts\` (по умолчанию `%LOCALAPPDATA%\NotesBotKit\scripts\`)
2. Создаёт `memory/bot-config.json` из шаблона
3. Создаёт `memory/members.json` из шаблона
4. Записывает `.env` с токеном в `$InstallRoot\` И в `~/.openclaw/.env` (если папка есть)
5. Ставит `aiogram` + `aiohttp` через pip (если ещё не стоят)
6. Регистрирует watchdog в **Планировщике задач Windows** (`NotesBotKitWatchdog`) — стартует при логине, рестартит каждые 1 мин если упал
7. Запускает watchdog прямо сейчас — бот поднимется в течение 5 сек

**Проверка:**

```powershell
# Смотри лог
Get-Content "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.watchdog.log" -Tail 20 -Wait

# Должно появиться:
# 2026-06-23 14:30:01 watchdog start; bot=...\telegram_notes_bot.py; restart_delay=5s
# 2026-06-23 14:30:01 spawning bot...
# 2026-06-23 14:30:04 Bot started: @MyTeamIdeasBot (id 1234567890) on attempt 1
# 2026-06-23 14:30:04 Bot menu commands set to: ['start', 'info', 'ideas', 'skills', 'rejected', 'split', 'classify']
```

Открой бота в Telegram, напиши `/start` — бот ответит приветствием и запишет твой chat_id в `bot-config.json → owner.chat_id`.

---

## 3. Установка вручную (если install.ps1 не подходит)

```powershell
# 1. Куда ставим
$Root = "D:\NotesBotKit"
New-Item -ItemType Directory -Force -Path $Root\scripts, $Root\memory\inbox | Out-Null

# 2. Копируем код
Copy-Item -Recurse -Force .\runtime\scripts\* $Root\scripts\

# 3. Копируем шаблоны конфига
Copy-Item -Force .\runtime\workspace\memory\bot-config.template.json $Root\memory\bot-config.json
Copy-Item -Force .\runtime\workspace\memory\members.template.json $Root\memory\members.json
New-Item -ItemType File -Path $Root\memory\notes.jsonl -Force | Out-Null

# 4. Создаём .env
@"
TEAM_BOT_TOKEN=1234567890:AAHxYz...
TELEGRAM_BOT_TOKEN=1234567890:AAHxYz...
"@ | Set-Content -LiteralPath $Root\.env -Encoding UTF8

# 5. Запускаем watchdog (отдельно от install.ps1)
python $Root\scripts\telegram_notes_bot_watchdog.py
```

---

## 4. Настройка владельца и команды

### 4.1. Владелец (owner)

`bot-config.json → owner` должен содержать ТВОЙ Telegram username. Бот определяет owner по `username` (case-insensitive).

```json
{
  "owner": {
    "username": "my_telegram_username",   // без @
    "chat_id": 123456789,                  // бот проставит при /start
    "user_id": 123456789,
    "first_name": "My Name"
  }
}
```

**Как получить chat_id автоматически:** отправь боту `/start`. Бот увидит `from_user.id`, запишет в `bot-config.json` и пришлёт тебе сообщение "Твой chat_id = 123456789 записан."

### 4.2. Команда (team)

`bot-config.json → team` — список Telegram username'ов членов команды, которым доступны read-only команды (/info, /ideas, /rejected, /split, /classify):

```json
{
  "team": [
    "alice",
    "bob",
    "carol"
  ]
}
```

**Важно:** username в `team` должен совпадать с тем, что в Telegram у этих людей (lowercase, без `@`). Если человек ещё не написал боту — chat_id будет неизвестен, но username достаточно для определения.

### 4.3. Анонимные гости

Любой пользователь Telegram, не owner и не в team, может:
- Прислать текст → запишется в `notes.jsonl` + `inbox/`, бот ответит "Принято ✅"
- Прислать голосовое → то же (с Whisper если включён)

Но НЕ получит доступ к командам.

---

## 5. Что проверить после установки

### 5.1. Бот жив

```powershell
Get-Process python | ForEach-Object {
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
    if ($cmd -match 'telegram_notes_bot') { Write-Host "PID $($_.Id): $cmd" }
}
```

Должно быть **ровно 2 процесса**:
- `telegram_notes_bot_watchdog.py` (watchdog)
- `telegram_notes_bot.py` (бот)

Если больше — старые копии убей (см. OPERATIONS.md).

### 5.2. Команды работают

В Telegram напиши боту:
- `/start` → должен ответить приветствием
- `/today` → (если есть заметки за сегодня) список
- `/info` → категоризированная витрина идей
- `/ideas week` → все идеи за неделю

### 5.3. Forge-пайплайн (опционально)

Если у тебя есть `forge-skill` агент в OpenClaw:

1. Напиши боту нормальную идею (>3 слов, не greeting, например: «Бот должен присылать мотивационные цитаты по утрам»)
2. Бот запишет её в `notes.jsonl` + `inbox/`
3. Бот тихо положит forgeable-копию в `forge_queue.jsonl`
4. В webchat / Telegram напиши `notes-keeper` агенту: «обработай forge_queue»
5. notes-keeper дёрнет forge-skill через `sessions_send`
6. forge-skill за ≤5 мин вернёт готовый SKILL.md в `workspace/Golden-Hour/skills/<slug>/` (или туда, куда ты его настроишь)

Без forge-skill агента — `/skills` запустит локальный fallback (`idea_to_skill.run_pipeline`), который тоже создаёт SKILL.md, но без research и тестов.

---

## 6. Удаление

```powershell
# Через uninstaller
.\uninstall.ps1

# С сохранением данных (notes.jsonl, inbox)
.\uninstall.ps1 -KeepData

# Кастомный путь
.\uninstall.ps1 -InstallRoot D:\NotesBotKit
```

Что делает:
1. Убивает watchdog и bot-процессы
2. Удаляет Scheduled Task `NotesBotKitWatchdog`
3. Спрашивает про удаление файлов (или сохраняет если -KeepData)
4. Спрашивает про очистку `TEAM_BOT_TOKEN` из `~/.openclaw/.env`

---

## 7. Частые ошибки при установке

| Симптом | Причина | Решение |
|---|---|---|
| `python` выдаёт пустую версию | PATH указывает на WindowsApps stub | Используй `C:\...\Python312\python.exe` или задай `$env:NOTES_BOT_PYTHON` |
| `ModuleNotFoundError: aiogram` | pip ставил в другой Python | Убедись что используешь тот же `python`, что и в `$env:NOTES_BOT_PYTHON` |
| `Missing TEAM_BOT_TOKEN in .env` | .env не найден или пустой | Проверь `$Root\.env`, что `TEAM_BOT_TOKEN=<токен>` (без пробелов вокруг `=`) |
| Бот стартует и сразу падает | `bot-config.json` — невалидный JSON | Проверь: `Get-Content $Root\memory\bot-config.json -Raw \| ConvertFrom-Json` |
| `/start` не отвечает "хозяин" | username в `bot-config.json` не совпадает с твоим Telegram username | Проверь case (lowercase!) и отсутствие `@` |
| Бот видит сообщения, но не пишет в `notes.jsonl` | Диск переполнен или нет прав на запись | Проверь `Test-Path $Root\memory\notes.jsonl -PathType Leaf` и права |
| Два бота запущены одновременно | Старый watchdog не убит перед стартом нового | `Get-Process python \| Where ... \| Stop-Process` (см. OPERATIONS.md) |

---

## 8. Следующие шаги

- Прочитай [ARCHITECTURE.md](./ARCHITECTURE.md) — чтобы понимать, как всё работает под капотом.
- Прочитай [OPERATIONS.md](./OPERATIONS.md) — логи, бэкапы, рестарт, дебаг.
- Если планируешь forge-пайплайн — установи/создай агента `forge-skill` (см. `agent-skills/notes-forge-pipeline.md`).
- Если нужен голос — поставь faster-whisper + ffmpeg, переключи `bot-config.json → asr.server_side: true`.
