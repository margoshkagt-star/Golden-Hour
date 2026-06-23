---
name: notes-bot-setup
description: "Установка Notes-Bot Kit с нуля: токен, конфиг, watchdog, pip. Windows PowerShell install.ps1. 🛠."
---

# notes-bot-setup

Пошаговая установка Telegram-бота для сбора идей команды из пакета Notes-Bot Kit.

## Цель

Поднять полностью рабочий бот за 3 минуты: получить токен у @BotFather, скопировать runtime, зарегистрировать watchdog в автозапуске, проверить что бот отвечает на `/start`.

## Триггер

Когда пользователь говорит «установи бот идей», «подними Notes-Bot», «разверни kit», «нужен новый бот для команды», или даёт явное указание настроить бота из этого пакета.

## Логика

### Шаг 1 — Требования (30 сек)

Проверить:
- Windows 10/11, PowerShell 5.1+
- Python 3.10+ (НЕ WindowsApps stub — он выдаёт пустую версию)
- aiogram, aiohttp установлены или готовность их поставить
- Свободное место: ~200 MB без Whisper / ~1.5 GB с faster-whisper

### Шаг 2 — Токен (1 мин)

1. Открыть Telegram, найти [@BotFather](https://t.me/BotFather)
2. `/newbot`, задать имя и username (заканчивается на `Bot`)
3. Скопировать токен формата `<digits>:<35+ chars>`

### Шаг 3 — Установка через install.ps1 (1 мин)

```powershell
cd notes-bot-kit-v1
.\install.ps1 -BotToken "1234567890:AAHxYz..."
```

Что делает install.ps1:
1. Копирует `runtime/scripts/` → `$env:LOCALAPPDATA\NotesBotKit\scripts\`
2. Создаёт `memory/bot-config.json` из шаблона
3. Создаёт `memory/members.json` из шаблона
4. Записывает `.env` с токеном (в kit + в `~/.openclaw/.env` если папка есть)
5. Ставит `aiogram` + `aiohttp` через pip
6. Регистрирует watchdog в Планировщике задач (`NotesBotKitWatchdog`, AtLogOn, auto-restart)
7. Запускает watchdog в текущей сессии

### Шаг 4 — Регистрация владельца (30 сек)

Открыть бота в Telegram, написать `/start`. Бот определит owner по username, запишет `chat_id` в `bot-config.json`, пришлёт приветствие с командами.

### Шаг 5 — Проверка (30 сек)

```powershell
Get-Content "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.watchdog.log" -Tail 10
# Должно быть: "Bot started: @MyBot (id ...) on attempt 1"

Get-Process python | Where-Object { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -match 'telegram_notes_bot' } | Measure-Object | Select-Object Count
# Должно быть 2: watchdog + bot
```

В Telegram нажать `/info` — должна прийти категоризированная витрина.

### Шаг 6 — Настройка команды (опционально)

В `bot-config.json → team` добавить Telegram username'ы коллег, которым нужны read-only команды. После редактирования — рестарт бота (НЕ watchdog).

### Fallback — ручная установка

Если install.ps1 не подходит (другой shell, нет Scheduled Task):
```powershell
$Root = "D:\NotesBotKit"
New-Item -ItemType Directory -Force -Path $Root\scripts, $Root\memory\inbox | Out-Null
Copy-Item -Recurse -Force .\runtime\scripts\* $Root\scripts\
Copy-Item -Force .\runtime\workspace\memory\bot-config.template.json $Root\memory\bot-config.json
Copy-Item -Force .\runtime\workspace\memory\members.template.json $Root\members.json
"TEAM_BOT_TOKEN=<token>" | Set-Content "$Root\.env" -Encoding UTF8
python "$Root\scripts\telegram_notes_bot_watchdog.py"
```

## Вход → Выход

| Вход | Действие | Выход |
|---|---|---|
| «Установи бот» | Запустить install.ps1 с токеном | Работающий бот + Scheduled Task |
| «Где взять токен?» | Инструкция к @BotFather | Готовый токен |
| «install.ps1 упал» | Дебаг (см. частые ошибки в INSTALL.md) | Исправленный шаг |
| «Python не находится» | Задать `$env:NOTES_BOT_PYTHON` или установить 3.10+ | Рабочий путь к Python |
| «Бот молчит после установки» | Чек логов + процесса | Рестарт / фикс |

## Что НЕ делает

- Не создаёт Telegram-аккаунт за пользователя (человек делает сам через @BotFather)
- Не модифицирует `~/.openclaw/openclaw.json` (главный конфиг OpenClaw)
- Не ставит forge-skill агента (это отдельный OpenClaw-агент, не часть кита)
- Не коммитит в git (если только пользователь явно не попросит)
- Не отправляет ничего в Telegram без явного триггера от пользователя

## Зависимости

| Зависимость | Назначение |
|---|---|
| PowerShell 5.1+ | Запуск install.ps1 |
| Python 3.10+ | Runtime бота |
| aiogram 3.x | Telegram Bot API |
| aiohttp | HTTP-клиент для aiogram |
| Telegram Bot API | Polling getUpdates |
| Scheduled Task (Windows) | Автозапуск watchdog (через install.ps1) |

## Связанные скиллы

- `notes-bot-architecture` — общая картина
- `notes-bot-operator` — что делать после установки
- `notes-bot-commands` — какие команды есть
- `notes-watchdog` — как работает watchdog
