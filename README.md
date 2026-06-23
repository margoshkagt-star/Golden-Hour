# Golden Hour — командные таски (ветка `team-tasks-install`)

OpenClaw-агент для **командной работы**: несколько людей над одной целью, инвайты, общие таски, submit/approve, уведомления в Telegram.

> **Установка:** [TEAM-TASKS-SETUP.md](TEAM-TASKS-SETUP.md)  
> Полный дистрибутив (учёба + план): ветка [`agent-install`](https://github.com/margoshkagt-star/Golden-Hour/tree/agent-install)

## Что внутри

| Компонент | Назначение |
|---|---|
| `SOUL.md` | Логика агента (командные таски + онбординг) |
| `skills/team-tasks/` | Оркестратор командной работы |
| `scripts/team-tasks.mjs` | CLI: `team *`, `task *`, `invites resolve` |
| `data/teams/` | Хранилище команд (приватное, в gitignore) |

## Скиллы (18 + онбординг)

**Ядро:** `team-tasks`, `session-start`, `user-profile`, `help-menu`, `goal-checkin-notifier`

**Личные таски:** `current-tasks`, `task-tracker`, `task-decomposition`, `task-triage`, `evening-task-triage`

**Оркестрация:** `delegate-via-subagents`, `agent-orchestration`, `subagent-queue-pattern`, `coder`, `critical-review`, `work-on-site`, `note-to-file`

**Онбординг:** `skills/_onboarding/*`

## Быстрая проверка

```powershell
git clone -b team-tasks-install https://github.com/margoshkagt-star/Golden-Hour.git team-tasks
cd team-tasks
node scripts/run-tests.mjs
```
