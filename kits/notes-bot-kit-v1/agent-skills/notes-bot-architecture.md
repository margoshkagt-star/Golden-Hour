---
name: notes-bot-architecture
description: "Telegram-бот для сбора идей команды (aiogram 3.x) + автоконвертация в SKILL.md. Архитектура, подсистемы, потоки данных. 📓."
---

# notes-bot-architecture

Полное описание архитектуры Telegram-бота для сбора идей команды с автоконвертацией в SKILL.md для OpenClaw.

## Цель

Дать агенту в OpenClaw полную картину того, как устроен Notes-Bot Kit — из каких подсистем состоит, как они общаются, где какие файлы, какие RBAC, какие guard'ы и где они применяются. Этот скилл — «карта территории», не инструкция к действию.

## Триггер

Когда агент в OpenClaw встречает любой из признаков:
- Упоминание `@<bot>` / «бот идей» / «notes bot» / `forge_queue.jsonl`
- Задача «объясни как работает бот», «где лежит X», «почему бот не отвечает»
- Подозрение на баг в ingestion-цепочке (нет записи в `notes.jsonl`, forge не сработал, голос не расшифровался)
- Желание добавить новую команду или подсистему

## Логика

### 6 подсистем

| # | Подсистема | Файл | Назначение |
|---|---|---|---|
| 1 | **Bot core** | `runtime/scripts/telegram_notes_bot.py` | aiogram 3.x, polling, все хендлеры, команды |
| 2 | **Watchdog** | `runtime/scripts/telegram_notes_bot_watchdog.py` | Spawn bot в loop, экспоненциальный backoff 5→60 сек |
| 3 | **Intake** | `runtime/scripts/idea_intake.py` | Дедуп, классификация, split, is_forgeable() |
| 4 | **Forge fallback** | `runtime/scripts/idea_to_skill.py` | Локальный генератор SKILL.md для `/skills` |
| 5 | **Members** | `runtime/scripts/members.py` | Резолв user_id → handle/name через `members.json` |
| 6 | **Voice-transcribe** | `skills/voice-transcribe/scripts/transcribe.py` | faster-whisper: .ogg → .txt (опционально) |

### Поток сообщения

```
Telegram → polling → bot → intake → notes.jsonl + inbox/
                                    ↓ (если forgeable)
                            forge_queue.jsonl
                                    ↓ (notes-keeper через sessions_send)
                            forge-skill агент
                                    ↓
                            workspace/Golden-Hour/skills/<slug>/SKILL.md
```

### RBAC

| Роль | Доступ | Определение |
|---|---|---|
| Owner | Всё + авто-forge | `bot-config.json → owner.username` совпадает |
| Team | Read commands | username в `bot-config.json → team` |
| Guest | Только отправка сообщений | Все остальные |

### Guards (Bug #1 fix, 2026-06-21)

В `_handle_text_note`:
- `GREETINGS` — set из 17 русских/английских приветствий
- `SHORT_MSG_MAX_WORDS = 3` — короткие не триггерят forge

### Файлы данных (критичные)

- `memory/notes.jsonl` — все сообщения (append-only)
- `memory/inbox/YYYY-MM-DD.md` — дневной дамп для человека
- `memory/forge_queue.jsonl` — очередь forgeable
- `memory/bot-config.json` — конфиг
- `memory/members.json` — реестр handle'ов
- `media/inbound/<file_id>.{ogg,txt}` — голосовые + транскрипты

## Вход → Выход

| Вход | Действие | Выход |
|---|---|---|
| «Что такое бот идей?» | Описать подсистемы | Краткий список из 6 файлов с назначением |
| «Где forge-очередь?» | Указать путь | `memory/forge_queue.jsonl` + формат строк |
| «Как бот отличает owner?» | Объяснить RBAC | `bot-config.json → owner.username` |
| «Почему на привет спам?» | Сказать про Bug #1 + guard'ы | Уже пофикшено в v1 |
| «Какие команды есть?» | Сослаться | См. скилл `notes-bot-commands` |

## Что НЕ делает

- Не запускает бота (см. `notes-bot-setup` / `notes-bot-operator`)
- Не исправляет код (только описывает)
- Не отправляет сообщения в Telegram от имени Karim'а
- Не удаляет файлы данных без явного подтверждения

## Зависимости

- **Python:** 3.10+ (использует match-statement и | type hints)
- **aiogram:** 3.x
- **aiohttp:** совместимая с aiogram 3.x
- **OpenClaw:** для AgentSkills и forge-skill агента (опционально)
- **faster-whisper:** опционально, для голосового пайплайна
- **Telegram Bot API:** 7.0+

## Связанные скиллы

- `notes-bot-setup` — как поднять с нуля
- `notes-bot-operator` — как обслуживать
- `notes-bot-commands` — какие команды есть
- `notes-idea-intake` — как intake классифицирует
- `notes-forge-pipeline` — forge-пайплайн end-to-end
- `notes-voice-transcribe` — голосовой пайплайн
- `notes-watchdog` — watchdog и рестарт
