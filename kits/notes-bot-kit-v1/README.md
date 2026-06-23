# Notes-Bot Kit v1

**Полный экспортный пакет Telegram-бота для сбора идей команды + автоконвертации в SKILL.md.**

> Бот `@Goldenteam239bot` (id `8991800752`) — рабочий production-инстанс у Karim'а. Этот пакет — 1:1 слепок его runtime + полный набор инструкций, чтобы любой другой пользователь OpenClaw мог развернуть такой же бот у себя, вставив только токен от @BotFather.

---

## Что в коробке

```
notes-bot-kit-v1/
├── README.md                         ← ты здесь
├── INSTALL.md                        ← пошаговая установка (человек)
├── ARCHITECTURE.md                   ← как всё устроено (полная развертка)
├── COMMANDS.md                       ← референс всех команд бота
├── OPERATIONS.md                     ← эксплуатация, логи, бэкапы, дебаг
├── CHANGELOG.md
├── .env.example                      ← шаблон переменных окружения
├── bot-config.template.json          ← шаблон конфига (опционально, есть в runtime/)
├── install.ps1                       ← автоустановщик для Windows
├── uninstall.ps1                     ← автоудаление
│
├── runtime/                          ← 1:1 production-код (можно запускать как есть)
│   ├── scripts/
│   │   ├── telegram_notes_bot.py              ← главный скрипт бота (63 KB, aiogram 3.x)
│   │   ├── telegram_notes_bot_watchdog.py     ← watchdog с экспоненциальным backoff
│   │   ├── idea_intake.py                     ← классификатор + is_forgeable()
│   │   ├── idea_to_skill.py                   ← локальный forge-fallback для /skills
│   │   ├── members.py                         ← реестр user_id → handle
│   │   └── forge_check.py                     ← утилита проверки forgeable
│   └── workspace/
│       └── memory/
│           ├── bot-config.template.json
│           ├── bot-config.reference.json      ← реальный production-конфиг (для примера)
│           ├── members.template.json
│           ├── members.reference.json         ← реальный production-реестр
│           ├── notes.jsonl.empty              ← пустышка (создаётся автоматом)
│           └── inbox/.gitkeep
│
├── agent-skills/                     ← 8 SKILL.md для OpenClaw (см. ниже)
│   ├── README.md
│   ├── notes-bot-architecture.md
│   ├── notes-bot-setup.md
│   ├── notes-bot-operator.md
│   ├── notes-bot-commands.md
│   ├── notes-idea-intake.md
│   ├── notes-forge-pipeline.md
│   ├── notes-voice-transcribe.md
│   └── notes-watchdog.md
│
└── examples/
    ├── inbox-sample.md               ← как выглядит дневной дамп для человека
    ├── notes.jsonl-sample.jsonl      ← 8 реальных строк из production notes.jsonl
    ├── idea-to-skill-flow.md         ← пошаговый путь идеи → SKILL.md
    └── SKILL.md-template.md          ← шаблон сгенерированного forge-skill скилла
```

---

## Быстрый старт (3 минуты)

### Windows (PowerShell)

```powershell
cd notes-bot-kit-v1
# 1. Создай бота в Telegram через @BotFather, скопируй токен
# 2. Запусти установщик (он скопирует runtime, запишет .env, зарегистрирует watchdog в Планировщике задач)
.\install.ps1 -BotToken "1234567890:AAHxYz..."

# Готово. Открой бота в Telegram, напиши /start
# Бот узнает твой chat_id и сохранит owner
```

Если Python не в `C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe` — задай:
```powershell
$env:NOTES_BOT_PYTHON = "C:\Path\To\python.exe"
.\install.ps1 -BotToken "..."
```

### Ручная установка (без install.ps1)

```powershell
# Скопируй runtime/scripts/ куда удобно
xcopy /E /I runtime\scripts C:\NotesBot\scripts
xcopy /E /I runtime\workspace\memory C:\NotesBot\memory

# Создай .env (см. .env.example)
echo TEAM_BOT_TOKEN=1234567890:AAHxYz... > C:\NotesBot\.env

# Запусти watchdog (он сам поднимет бота)
python C:\NotesBot\scripts\telegram_notes_bot_watchdog.py
```

---

## Что бот умеет

| Фича | Описание |
|---|---|
| **Приём заметок** | Любой текст, голосовое (с Whisper-транскриптом), фото, документы — всё идёт в `memory/notes.jsonl` + `memory/inbox/YYYY-MM-DD.md` |
| **Greeting-guard** | На «привет» / «ок» / 1-2 слова бот НЕ спамит и НЕ триггерит forge-пайплайн (фикс Bug #1 от 2026-06-21) |
| **Forge-пайплайн** | Если текст длиннее 30 символов и не greeting — бот ставит идею в очередь `forge_queue.jsonl` → notes-keeper подхватывает → дёргает `forge-skill` агента → готовый SKILL.md ложится в `workspace/Golden-Hour/skills/<slug>/` |
| **Команды владельца** | /start /help /today /week /digest /search /info /ideas /skills /rejected /split /classify |
| **Команды команды** | /info /ideas /skills /rejected /split /classify (read-only) |
| **Гостевой режим** | Любой пользователь может прислать текст/голос — запишется в `notes.jsonl` + `inbox/`, бот ответит «Принято ✅» |
| **Реестр handle'ов** | `memory/members.json` хранит `user_id → @username / first_name` для красивого вывода |
| **Periodic digest** | Каждые 3ч (настраивается) бот шлёт owner'у непрочитанные заметки |
| **Категоризация** | /info раскладывает идеи по 8 категориям (Wellness / Образование / Продуктивность / ...) |
| **Метки реализации** | /info автоматически помечает идеи, по которым уже есть SKILL.md в staging или production |

---

## Архитектура одной строкой

```
Telegram → aiogram polling → idea_intake (classify + forgeable?) → notes.jsonl + inbox/
                                                          ↓ (если forgeable)
                                                  forge_queue.jsonl
                                                          ↓ (notes-keeper через sessions_send)
                                                  forge-skill агент
                                                          ↓ (Research → Design → Tests → Save → Report)
                                                  workspace/Golden-Hour/skills/<slug>/SKILL.md
```

Полная развертка — в [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Где что лежит (production reference)

В рабочей инсталляции Karim'а:

```
C:\Users\Admin\.openclaw\
├── .env                                           ← TEAM_BOT_TOKEN (НЕ коммитить)
└── workspace\
    ├── scripts\
    │   ├── telegram_notes_bot.py                  ← 63 KB, ~1500 строк
    │   ├── telegram_notes_bot_watchdog.py         ← 1.6 KB
    │   ├── idea_intake.py                         ← 35 KB
    │   ├── idea_to_skill.py                       ← 20 KB
    │   ├── members.py                             ← 12 KB
    │   ├── forge_check.py                         ← 924 B
    │   ├── telegram_notes_bot.log                 ← боевой лог (НЕ удалять!)
    │   └── telegram_notes_bot.watchdog.log        ← лог watchdog
    └── memory\
        ├── bot-config.json                        ← owner/team/commands/asr/digest
        ├── notes.jsonl                            ← все сообщения бота (append-only)
        ├── members.json                           ← реестр user_id → handle
        ├── forge_queue.jsonl                      ← очередь forgeable-идей
        ├── forge_results.jsonl                    ← результаты forge-skill
        ├── forge_state.json
        ├── ideas.md                               ← вывод /classify (human)
        ├── ideas_rejected.md                      ← отсеянные (human)
        ├── ideas_state.json
        ├── skills-digest.md                       ← лог forge-операций
        ├── bot-ideas-state.json
        └── inbox\
            └── YYYY-MM-DD.md                      ← дневной дамп для человека
```

---

## Что НЕ входит в этот пакет (намеренно)

Этот пакет — **бот идей и forge-пайплайн**. НЕ включено:

- ❌ **OpenClaw runtime** — устанавливается отдельно (https://docs.openclaw.ai)
- ❌ **forge-skill агент** — это отдельный OpenClaw-агент. Пакет описывает, как с ним общаться через `sessions_send`, но самого агента в bundle нет. Инсталлятор может создать своего агента или подключить существующего.
- ❌ **Golden-Hour репозиторий** — куда forge-skill кладёт SKILL.md. Это внешний git-репо, создаётся отдельно. Бот работает и без него (просто идеи будут копиться в forge_queue.jsonl).
- ❌ **Готовые скиллы из Golden-Hour** — это артефакты forge-skill'а, не часть кита.
- ❌ **Whisper-модель для voice-transcribe** — ставится отдельно (`pip install faster-whisper`). По умолчанию голосовые сохраняются с duration, без транскрипта (см. `bot-config.json → asr.server_side`).

---

## Версия и автор

- **Версия:** v1 (2026-06-23)
- **Прообраз:** production-бот @Goldenteam239bot (id `8991800752`)
- **Автор:** Karim (beatusx, chat_id `1038917447`)
- **Сборщик пакета:** Notes-Keeper агент (📓, agentId=`notes-keeper`)
- **Связанные субагенты:** forge-skill (🔨, фабрика SKILL.md)
