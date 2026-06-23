---
name: notes-watchdog
description: "Watchdog Notes-Bot: перезапуск при падении, экспоненциальный backoff 5→60 сек, регистрация в Планировщике задач Windows. 🐕."
---

# notes-watchdog

Watchdog для Notes-Bot Kit: следит за процессом бота, перезапускает при падении, логирует события. Регистрация в автозапуске через Windows Scheduled Task (создаётся install.ps1).

## Цель

Держать бот живым 24/7 без ручного вмешательства. При любом падении (исключение, kill, segfault, network blip) — автоматически поднять заново. Никогда не сдаваться.

## Триггер

- Бот упал и нужно его поднять
- Задача «зарегистрировать watchdog в автозапуске»
- Дебаг: watchdog в цикле рестартов (каждые 5 сек — баг)
- Мониторинг: бот жив или мёртв
- Вопросы про экспоненциальный backoff, exit codes

## Логика

### Алгоритм

```python
# runtime/scripts/telegram_notes_bot_watchdog.py (упрощённо)
backoff = RESTART_DELAY  # 5 сек
MAX_BACKOFF = 60

while True:
    log("spawning bot...")
    rc = subprocess.call([sys.executable, BOT])  # блокирующий
    log(f"bot exited with code {rc}")
    time.sleep(backoff)
    backoff = min(backoff * 2, MAX_BACKOFF) if rc != 0 else RESTART_DELAY
```

**Backoff:**
- Успешный старт → сброс на 5 сек
- Падение → 5 → 10 → 20 → 40 → 60 (cap)
- Никогда не сдаётся (точка)

### Почему экспоненциальный

Если бот падает МГНОВЕННО (например, `import` ошибка из-за битого модуля) — бесконечный spawn зациклит CPU. Backoff даёт время посмотреть лог и починить.

Если бот падает через 1 час работы — backoff уже сброшен, новый запуск через 5 сек.

### Регистрация в Windows (install.ps1)

`install.ps1` создаёт Scheduled Task `NotesBotKitWatchdog`:

| Параметр | Значение | Зачем |
|---|---|---|
| Action | `python <kit>/scripts/telegram_notes_bot_watchdog.py` | Запуск watchdog |
| Trigger | `AtLogOn` | Старт при логине пользователя |
| Principal | `Interactive`, `RunLevel Highest` | Доступ к диску/сети |
| Settings.RestartCount | 99 | Если процесс watchdog умер — Windows перезапустит task |
| Settings.RestartInterval | 1 мин | Частота рестарта task'а |
| Settings.AllowStartIfOnBatteries | True | На ноутбуке без зарядки тоже стартует |
| Settings.DontStopIfGoingOnBatteries | True | Не приостанавливать при разряде |
| Settings.ExecutionTimeLimit | 0 | Бесконечно |

### Логи watchdog

`<kit>/scripts/telegram_notes_bot.watchdog.log` (append-only):

```
2026-06-23 14:30:01 watchdog start; bot=...\telegram_notes_bot.py; restart_delay=5s
2026-06-23 14:30:01 spawning bot...
2026-06-23 14:30:04 bot exited with code 0; restarting in 5s    ← корректное завершение (Ctrl+C)
2026-06-23 14:30:09 spawning bot...
2026-06-23 14:30:12 bot exited with code 1; restarting in 10s   ← crash, backoff растёт
2026-06-23 14:30:22 spawning bot...
2026-06-23 14:30:25 bot exited with code 1; restarting in 20s
2026-06-23 14:30:45 spawning bot...
2026-06-23 14:30:48 Bot started: @MyBot (id ...) on attempt 1  ← в логе БОТА, но виден из контекста
```

### Типичные сценарии

**Сценарий 1: бот упал из-за network blip**

```
2026-06-23 14:30:01 spawning bot...
2026-06-23 14:30:04 bot exited with code 1; restarting in 10s   ← упал
2026-06-23 14:30:14 spawning bot...
2026-06-23 14:30:17 Bot started: @MyBot (id ...) on attempt 1  ← поднялся
2026-06-23 14:30:17 bot exited with code 0; restarting in 5s   ← ??? странно, обычно 0 = корректное завершение
```

Если бот стартует и тут же завершается с code=0 — возможно конфликт polling (два бота одновременно, см. Bug #2).

**Сценарий 2: watchdog в цикле**

```
2026-06-23 14:30:01 spawning bot...
2026-06-23 14:30:04 bot exited with code 1; restarting in 10s
2026-06-23 14:30:14 spawning bot...
2026-06-23 14:30:17 bot exited with code 1; restarting in 20s
2026-06-23 14:30:37 spawning bot...
2026-06-23 14:30:40 bot exited with code 1; restarting in 40s
... (60s, 60s, 60s, ...) ← БАГ, не норма
```

**Норма:** 1-2 падения в день (network blip, кратковременная потеря связи). **Не норма:** каждые 30-60 сек.

### Дебаг цикла рестартов

1. Остановить watchdog:
   ```powershell
   Stop-ScheduledTask -TaskName "NotesBotKitWatchdog"
   # или закрыть окно где запущен руками
   ```

2. Запустить бот напрямую (без watchdog) — увидишь stderr сразу:
   ```powershell
   python "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.py"
   # Смотри Traceback, исправляй
   ```

3. Проверить конкурентные процессы:
   ```powershell
   Get-Process python | Where-Object { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -match 'telegram_notes_bot' }
   # Должно быть РОВНО 1 (этот бот)
   # Если больше — kill лишних
   ```

4. После исправления — запустить watchdog заново:
   ```powershell
   Start-ScheduledTask -TaskName "NotesBotKitWatchdog"
   ```

### Что НЕ делает (в v1)

- ❌ Не убивает старые bot-процессы перед spawn нового → может быть «два бота» (Bug #2)
- ❌ Не шлёт алерт в Telegram при N падениях подряд (P2 задача)
- ❌ Не ротирует лог (растёт бесконечно, ~50 KB/день при нормальной нагрузке)
- ❌ Не мониторит интернет (если Telegram API недоступен — aiogram бросит exception, watchdog перезапустит)
- ❌ Не делает health-check endpoint (нет HTTP-сервера)

### Известные баги watchdog

**Bug #2 — два инстанса бота одновременно**

- Симптом: `terminated by other getUpdates request` в логе
- Workaround: ручной kill лишних
- Правильный фикс (P2): watchdog должен сначала `Stop-Process` все `telegram_notes_bot.py` (не watchdog), потом spawn

### Альтернативы (не в v1)

- **NSSM (Non-Sucking Service Manager)** — превращает watchdog в Windows-сервис
- **systemd (Linux)** — если переезд на Linux
- **supervisord** — кросс-платформенный
- **Docker restart policy** — если бот в контейнере

## Вход → Выход

| Вход | Действие | Выход |
|---|---|---|
| «Бот упал» | Watchdog сам поднимет | Бот работает через 5-60 сек |
| «Зацикливается рестартами» | Стоп watchdog, дебаг бота руками | Найдена причина, исправлена |
| «Не стартует при логине» | Чек Scheduled Task `NotesBotKitWatchdog` | Включён / пересоздан |
| «Убить watchdog» | `Stop-ScheduledTask` или Ctrl+C | Watchdog остановлен, бот тоже |
| «Изменить backoff» | Поправить `RESTART_DELAY` в watchdog (или env var `NOTES_BOT_RESTART_DELAY`) | Новое поведение |
| «Лог watchdog» | `Get-Content ...\telegram_notes_bot.watchdog.log -Tail` | История spawn/exit |

## Что НЕ делает

- Не исправляет баги в боте (только перезапускает)
- Не мониторит сетевую связность
- Не алертит Karim'а автоматически (только лог)
- Не ротирует логи
- Не запускает бота на другой машине (single-host watchdog)

## Зависимости

| Зависимость | Назначение |
|---|---|
| Python 3.10+ | Сам watchdog |
| subprocess, time, pathlib | stdlib |
| Scheduled Task (Windows) | Автозапуск (через install.ps1) |
| `<kit>/scripts/telegram_notes_bot.py` | Что спавнить |
| `<kit>/scripts/telegram_notes_bot.watchdog.log` | Куда писать |

## Связанные скиллы

- `notes-bot-architecture` — где watchdog в общей картине
- `notes-bot-setup` — установка + регистрация task'а
- `notes-bot-operator` — что делать при цикле рестартов
