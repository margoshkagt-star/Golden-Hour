# Scripts — командные таски

Детерминированные скрипты. Агент **вызывает скрипт → читает JSON → отвечает пользователю**.

Контракт: stdout = `{ ok: true, ... }` или `{ ok: false, error }`.

## Быстрый старт

```powershell
node scripts/session-start.mjs --user tg-5649925712
node scripts/team-tasks.mjs team create --user tg-111 --goal "Q&A сайт" --telegram-id 111
node scripts/team-tasks.mjs team list --user tg-111
node scripts/team-tasks.mjs task list --user tg-111 --team team-abc123
node scripts/run-tests.mjs
```

## Скрипты

| Скрипт | Скилл | Назначение |
|---|---|---|
| `session-start.mjs` | session-start | фаза пользователя, сводка профиля |
| `team-tasks.mjs` | team-tasks | команды, инвайты, общие таски |
| `run-tests.mjs` | — | unit-тесты team-tasks |

## Библиотека `scripts/lib/`

- `cli.mjs` — args, paths, JSON I/O
- `profile.mjs` — парсер `profile.md`
- `team-tasks.mjs` — логика команд и тасков

## Переменные окружения

- `GH_WORKSPACE` — путь к воркспейсу (по умолчанию: родитель `scripts/`)
