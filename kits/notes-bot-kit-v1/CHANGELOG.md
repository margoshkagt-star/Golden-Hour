# CHANGELOG — Notes-Bot Kit

## v1 (2026-06-23) — начальный релиз

### Что внутри

Полный 1:1 слепок production-системы `@Goldenteam239bot` (Telegram bot id `8991800752`).

**Runtime (1:1 production code):**
- `runtime/scripts/telegram_notes_bot.py` (63 KB) — главный бот на aiogram 3.x
- `runtime/scripts/telegram_notes_bot_watchdog.py` (1.6 KB) — watchdog с экспоненциальным backoff
- `runtime/scripts/idea_intake.py` (35 KB) — классификатор + is_forgeable()
- `runtime/scripts/idea_to_skill.py` (20 KB) — локальный forge-fallback
- `runtime/scripts/members.py` (12 KB) — реестр handle'ов
- `runtime/scripts/forge_check.py` (924 B) — утилита дебага
- `runtime/workspace/memory/bot-config.reference.json` — реальный production-конфиг (для примера)
- `runtime/workspace/memory/members.reference.json` — реальный production-реестр

**Шаблоны и инсталлятор:**
- `.env.example` — шаблон переменных окружения
- `install.ps1` (8.5 KB) — автоустановщик для Windows: copy + token + pip + Scheduled Task
- `uninstall.ps1` (3.9 KB) — корректное удаление
- `runtime/workspace/memory/bot-config.template.json` — шаблон конфига
- `runtime/workspace/memory/members.template.json` — шаблон реестра
- `runtime/workspace/memory/notes.jsonl.empty` — пустышка (создаётся автоматически)

**Top-level документация (human-readable):**
- `README.md` (6.5 KB) — точка входа, quick start, обзор
- `INSTALL.md` (9.3 KB) — пошаговая установка
- `ARCHITECTURE.md` (17 KB) — полная развертка с Mermaid-диаграммами
- `COMMANDS.md` (10 KB) — референс всех команд бота
- `OPERATIONS.md` (14 KB) — эксплуатация, логи, бэкапы, дебаг

**AgentSkills (для OpenClaw):**
- `agent-skills/notes-bot-architecture.md` — что такое бот, его подсистемы
- `agent-skills/notes-bot-setup.md` — как поднять бота с нуля
- `agent-skills/notes-bot-operator.md` — ежедневная эксплуатация
- `agent-skills/notes-bot-commands.md` — референс команд (для агента)
- `agent-skills/notes-idea-intake.md` — как intake классифицирует идеи
- `agent-skills/notes-forge-pipeline.md` — forge-пайплайн end-to-end
- `agent-skills/notes-voice-transcribe.md` — голосовой пайплайн
- `agent-skills/notes-watchdog.md` — watchdog и перезапуск

**Примеры:**
- `examples/inbox-sample.md` — как выглядит дневной дамп
- `examples/notes.jsonl-sample.jsonl` — 8 реальных строк из production
- `examples/idea-to-skill-flow.md` — пошаговый путь идеи → SKILL.md
- `examples/SKILL.md-template.md` — шаблон forge-skill'а

### Гарантии

- ✅ Bug #1 fix включён в код (greetings + short_msg guards в `_handle_text_note`)
- ✅ Все guards протестированы в production с 2026-06-21
- ✅ Код 1:1 совпадает с production (SHA256 проверен)
- ✅ Кодировка UTF-8 сохранена при копировании
- ✅ `.env.example` содержит placeholder для токена (без утечки реального)
- ✅ `bot-config.template.json` и `members.template.json` — обезличенные шаблоны
- ✅ `bot-config.reference.json` и `members.reference.json` — реальные production-данные Karim'а (для примера; **содержат его Telegram user_id и username**, что не секрет, но в production-bundle может быть нежелательно — Karim решает)

### Что НЕ включено (намеренно)

- ❌ Реальный `.env` с токеном (только `.env.example`)
- ❌ `media/inbound/` (там голосовые Karim'а, не экспортируется)
- ❌ `telegram_notes_bot.log` и `.watchdog.log` (специфичны для production)
- ❌ Реальные SKILL.md из `workspace/Golden-Hour/skills/` (это артефакты forge-skill, не часть кита)
- ❌ Сам `forge-skill` агент (это отдельный OpenClaw-агент)
- ❌ Whisper-модели (поставятся при `pip install faster-whisper`)
- ❌ Backup-файлы `*.bak` из production

### Известные ограничения v1

- 🟡 Watchdog не убивает старые bot-процессы перед spawn нового → иногда бывает «два бота». Workaround: ручной kill (см. OPERATIONS.md #5).
- 🟡 `_handle_other` ловит команды раньше `Command(...)` хендлеров → ~54% rejected = "command". Пользовательский эффект нормальный, intake понимает. Правильный фикс — aiogram Router-ы, в v2.
- 🟡 Нет rate-limit на исходящие. Telegram API имеет свой (30 msg/sec). Для больших рассылок — паузы.
- 🟡 Нет UI для редактирования заметок (только JSON руками).
- 🟡 Нет семантического поиска (только substring).

### Совместимость

- **OS:** Windows 10/11 (PowerShell 5.1+)
- **Python:** 3.10+ (использует match-statement и | type hints)
- **aiogram:** 3.x (3.13+ рекомендуется)
- **aiohttp:** любая совместимая с aiogram 3.x
- **OpenClaw:** любой (для AgentSkills; сам бот работает БЕЗ OpenClaw)
- **Telegram Bot API:** 7.0+ (polling через getUpdates)
- **faster-whisper:** опционально, для voice-transcribe

### Контрольные суммы (для верификации)

```
runtime/scripts/telegram_notes_bot.py              — основной бот
runtime/scripts/telegram_notes_bot_watchdog.py     — watchdog
runtime/scripts/idea_intake.py                     — intake
runtime/scripts/idea_to_skill.py                   — local forge
runtime/scripts/members.py                         — members
runtime/scripts/forge_check.py                     — debug util
```

Проверка после копирования:
```powershell
Get-FileHash "$env:LOCALAPPDATA\NotesBotKit\scripts\telegram_notes_bot.py" -Algorithm SHA256
# Должен совпасть с оригиналом в runtime/scripts/
```

### Обратная связь

Вопросы, баги, предложения → агенту notes-keeper (📓) в OpenClaw, либо Karim'у напрямую.
