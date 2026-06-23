# Scripts — Золотой час

Детерминированные скрипты для скиллов. Агент **вызывает скрипт → читает JSON → формулирует ответ**. Не пересчитывает план/веса в голове.

Контракт (как `gcal.mjs`): stdout = один JSON `{ ok: true, ... }` или `{ ok: false, error }`.

## Быстрый старт

```powershell
cd "$env:USERPROFILE\.openclaw\workspaces\golden-hour"

# Статус сессии
node scripts/session-start.mjs --user tg-5649925712

# Макро-план (перезапись: --force)
node scripts/study-plan.mjs --user tg-5649925712 --dry-run
node scripts/study-plan.mjs --user tg-5649925712

# Дневной план
node scripts/daily-plan.mjs --user tg-5649925712 --date 2026-06-19 --dry-run
node scripts/daily-plan.mjs --user tg-5649925712

# Веса тем
node scripts/task-weighting.mjs --user tg-5649925712

# Повторы (spaced repetition)
node scripts/spaced-repetition.mjs --user tg-5649925712

# Статистика
node scripts/longterm-stats.mjs --user tg-5649925712 --period week

# Командные таски
node scripts/team-tasks.mjs team create --user tg-111 --goal "Q&A сайт" --telegram-id 111
node scripts/team-tasks.mjs team list --user tg-111
node scripts/team-tasks.mjs task list --user tg-111 --team team-abc123

# Тесты
node scripts/run-tests.mjs
node scripts/morning-plan.mjs --dry-run
node scripts/morning-plan.mjs
node scripts/agent-qa.mjs --session qa-YYYYMMDD
```

## Cron (утро)

`morning-plan.mjs` в **07:00** Europe/Moscow — до morning brief (09:00). Инструкция: `scripts/cron/morning-plan.md`.

```powershell
# OpenClaw cron
.\scripts\cron\register-morning-plan.ps1

# или Windows Task Scheduler (без LLM)
.\scripts\cron\register-task-scheduler.ps1
```

## Скрипты

| Скрипт | Скилл | Назначение |
|---|---|---|
| `session-start.mjs` | session-start | фаза пользователя, сводка профиля |
| `study-plan.mjs` | study-plan | генерация `plan.md` |
| `task-weighting.mjs` | task-weighting | eff_priority / eff_difficulty |
| `daily-balancer.mjs` | daily-balancer | сборка дня из кандидатов (JSON) |
| `daily-plan.mjs` | daily-plan | `plans/YYYY-MM-DD.json` |
| `morning-plan.mjs` | daily-plan (batch) | все `users/*` на сегодня |
| `spaced-repetition.mjs` | spaced-repetition | due-темы на повтор |
| `longterm-stats.mjs` | longterm-stats | агрегаты из tasks.yaml и plans/ |
| `team-tasks.mjs` | team-tasks | команды, инвайты, общие таски |
| `gcal.mjs` | google-calendar-sync | Google Calendar API |
| `run-tests.mjs` | — | unit-тесты формул |

## Библиотека `scripts/lib/`

- `cli.mjs` — args, paths, JSON I/O
- `profile.mjs` — парсер `profile.md`
- `plan-parse.mjs` — парсер `plan.md`, текущая неделя
- `dates.mjs` — даты (+03:00)
- `task-weighting.mjs` — формулы весов
- `daily-balancer.mjs` — алгоритм баланса дня
- `spaced-repetition.mjs` — интервалы повтора
- `task-templates.mjs` — шаблоны названий задач
- `study-plan.mjs` — генератор markdown плана
- `team-tasks.mjs` — командные команды и таски (`data/teams/`)

## Переменные окружения

- `GH_WORKSPACE` — путь к воркспейсу (по умолчанию: родитель `scripts/`)

## Правила для агента

1. Планирование (`study-plan`, `daily-plan`, `task-weighting`) — **только через скрипты**.
2. Перед записью — `--dry-run`, показать пользователю `summary`, затем без флага.
3. При `{ ok: false }` — не выдумывать результат, передать `error` пользователю.
