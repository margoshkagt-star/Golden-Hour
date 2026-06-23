# agent-skills/

Это **AgentSkills** — переиспользуемые процедуры для OpenClaw-агентов, которые работают с ботом идей (Notes-Bot Kit).

## Формат

Каждый файл — стандартный OpenClaw `SKILL.md`:
- Frontmatter: `name` (slug) + `description` (≤160 байт)
- Секции: Цель / Триггер / Логика / Вход → Выход / Что НЕ делает / Зависимости
- Без `...`, «дописать», TODO
- Без реальных API-ключей и секретов

## Как установить в свой OpenClaw

**Вариант A — через Skill Workshop (рекомендуется):**
```powershell
# Из OpenClaw webchat
skill_workshop(action=create, name=notes-bot-architecture,
  description="<из frontmatter>",
  proposal_content=<содержимое .md файла>)
# Потом применить:
skill_workshop(action=apply, proposal_id=...)
```

**Вариант B — копированием в skills/ директорию:**
```powershell
# Если ваш OpenClaw читает скиллы из папки
Copy-Item -Recurse "agent-skills\*" "$env:USERPROFILE\.openclaw\workspaces\<agent>\skills\"
```

**Вариант C — прочитать как документацию:**
Открой любой файл и читай. Они самодостаточны как доки.

## Список скиллов

| Скилл | Назначение | Кому полезен |
|---|---|---|
| `notes-bot-architecture` | Что такое бот идей, его подсистемы и потоки | Любому агенту, который впервые видит бот |
| `notes-bot-setup` | Как поднять бот с нуля (токен, конфиг, watchdog) | Агенту-инсталлятору |
| `notes-bot-operator` | Ежедневная эксплуатация: логи, рестарт, бэкапы, дебаг | Агенту-оператору |
| `notes-bot-commands` | Референс всех команд бота (как помощь пользователю) | Агенту-помощнику |
| `notes-idea-intake` | Классификация идей (дедуп, стоп-слова, is_forgeable) | Агенту, который читает `notes.jsonl` |
| `notes-forge-pipeline` | Путь идеи → SKILL.md через forge-skill агента | Агенту-оркестратору forge-пайплайна |
| `notes-voice-transcribe` | Голосовой пайплайн (Whisper) | Агенту, который работает с голосовыми |
| `notes-watchdog` | Watchdog: перезапуск бота, backoff, мониторинг | Агенту-оператору |

## Источник правды

Все скиллы отражают **production-систему** из runtime/ в этом пакете. При обновлении runtime — синхронизируй соответствующие скиллы.

## Версия

v1 (2026-06-23). См. `../CHANGELOG.md`.
