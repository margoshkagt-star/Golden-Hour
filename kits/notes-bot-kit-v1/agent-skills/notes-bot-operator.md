---
name: notes-bot-operator
description: "Ежедневная эксплуатация Notes-Bot: логи, рестарт, бэкапы notes.jsonl, дебаг, типичные баги. ⚙️."
---

# notes-bot-operator

Операционные процедуры для Notes-Bot Kit: логирование, рестарт, бэкап, мониторинг, разрешение типичных проблем.

## Цель

Держать бот живым 24/7. Быстро находить root cause когда что-то сломалось. Не терять данные (`notes.jsonl` — главный актив). Уметь рестартить без потери сообщений.

## Триггер

- Бот не отвечает на сообщения в Telegram
- В логах ERROR / Traceback
- Watchdog в цикле рестартов (каждые 5 сек — баг, не норма)
- Запрос на бэкап / восстановление
- Запрос «как посмотреть что в боте» / «что было за неделю»
- Подозрение на конфликт (два бота polling одновременно)

## Логика

### 1. Где логи

| Файл | Что |
|---|---|
| `<install>/scripts/telegram_notes_bot.log` | Бот: каждый update, ошибки, решения forge, транскрипты |
| `<install>/scripts/telegram_notes_bot.watchdog.log` | Watchdog: spawn, exit codes, backoff |
| `<install>/memory/skills-digest.md` | Forge-операции (slug, summary, ts) |

### 2. Хвост live

```powershell
Get-Content "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.log" -Tail 50 -Wait
Get-Content "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.watchdog.log" -Tail 20 -Wait
```

### 3. Проверка состояния

Должно быть РОВНО 2 процесса:
- watchdog
- bot

```powershell
Get-Process python | Where-Object { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -match 'telegram_notes_bot' }
```

### 4. Мягкий рестарт (рекомендуется)

Убить ТОЛЬКО бот (watchdog сам поднимет новый через 5 сек):
```powershell
Get-Process python | Where-Object {
    (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -match 'telegram_notes_bot\.py' -and
    (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -notmatch 'watchdog'
} | Stop-Process -Force
```

### 5. Типичные проблемы и фиксы

| Симптом | Root cause | Фикс |
|---|---|---|
| Бот молчит | Процесс умер / токен битый | Чек логов → рестарт → чек `.env` |
| Два бота polling | Watchdog не убил старый перед spawn | Убить лишние `telegram_notes_bot.py` |
| «Привет» спам | (уже пофикшено в v1) | Скип |
| `/start` не отвечает «хозяин» | `owner.username` не совпадает | Поправить в `bot-config.json`, рестарт |
| Голос без транскрипта | Whisper не установлен / `asr.server_side: false` | `pip install faster-whisper` + переключить флаг |
| `/skills` 0 драфтов | Нет forgeable ИДЕЙ или `workspace/Golden-Hour/` не существует | Создать папку вручную или использовать forge-skill агента |

### 6. Бэкап

**Критичное (бэкапить обязательно):**
- `memory/notes.jsonl` (все сообщения)
- `memory/bot-config.json` (конфиг)
- `memory/members.json` (реестр)

**Опционально:**
- `memory/inbox/*.md` (дневные дампы — восстановимы из notes.jsonl)
- `memory/forge_queue.jsonl`, `forge_results.jsonl` (очередь + лог forge)
- `media/inbound/*.ogg` + `*.txt` (голосовые + транскрипты)

См. `OPERATIONS.md` → раздел «Бэкап данных» для готовых скриптов.

### 7. Дебаг intake

```powershell
# Полная переклассификация, dry-run
python "$env:LOCALAPPDATA\NotesBotKit\scripts\idea_intake.py" --dry-run

# Только новые
python "$env:LOCALAPPDATA\NotesBotKit\scripts\idea_intake.py" --new-only

# Сколько forgeable
(Get-Content "$env:LOCALAPPDATA\NotesBotKit\memory\forge_queue.jsonl" | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object { $_.status -eq 'pending' } | Measure-Object).Count
```

### 8. Мониторинг (минимум)

Лог должен обновляться каждые ≤5 мин при нормальной нагрузке. Если тишина 10+ мин — что-то не так. Heartbeat можно добавить в v2.

## Вход → Выход

| Вход | Действие | Выход |
|---|---|---|
| «Бот молчит» | Чек логов + процессов + .env | Рестарт / фикс конфига |
| «Сделай бэкап» | Скрипт из OPERATIONS.md | Архив в `NotesBotBackups/` |
| «Что было за неделю?» | `Get-Content notes.jsonl \| tail -N` | Сводка |
| «Сколько forgeable?» | Парсинг `forge_queue.jsonl` | Число pending |
| «Два бота» | Kill лишних | 1 бот + watchdog |
| «Лог разросся» | Не трогать (для v1); в v2 — ротация | — |

## Что НЕ делает

- Не удаляет `notes.jsonl` без подтверждения Karim'а
- Не меняет `bot-config.json` без понимания последствий
- Не останавливает watchdog (только в крайнем случае)
- Не отправляет сообщения в Telegram от имени владельца
- Не пушит в git / не делает внешних действий без явного «go»

## Зависимости

| Зависимость | Назначение |
|---|---|
| PowerShell 5.1+ | Команды управления |
| Python 3.10+ | Запуск intake / forge-check |
| Логи в `<install>/scripts/` | Первоисточник диагностики |
| Scheduled Task `NotesBotKitWatchdog` | Автозапуск |

## Связанные скиллы

- `notes-bot-architecture` — общая картина
- `notes-bot-setup` — установка
- `notes-bot-commands` — референс команд
- `notes-watchdog` — watchdog-специфика
- `notes-idea-intake` — дебаг intake
- `notes-forge-pipeline` — дебаг forge
