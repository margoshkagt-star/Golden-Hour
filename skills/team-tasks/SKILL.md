---
name: "team-tasks"
description: "Оркестратор командной работы: команды, инвайты, общие таски с назначением, submit/approve, уведомления members."
script: "scripts/team-tasks.mjs"
status: applied
version: "v1"
---

# team-tasks — командные таски

> Несколько людей работают над **общей целью**. Бот собирает команду, делит таски, трекает «кто что взял/сдал», уведомляет всех о прогрессе.

**Личная таска** (`task-tracker`) = одна голова. **Командная** = общий результат, **один assignee** в моменте, видят все members.

---

## Когда подключать

- «создай команду», `/team create`, «работаем вместе над …»
- «пригласи в команду», `/team invite`
- «вступить по коду», `/team accept`
- «командные задачи», «кто что делает», `/team task …`
- Первое сообщение нового пользователя → **авто-резолв инвайтов** (`invites resolve`)

**Не путать с:**
- `current-tasks` / `task-tracker` — личные задачи в `users/<key>/`
- `evening-task-triage` — личный вечерний разбор

---

## Два слоя

| Слой | Команды (через скрипт) | Примеры фраз |
|---|---|---|
| **Команды** | `team create/invite/accept/leave/list/show` | «создай команду», «пригласи @bob» |
| **Таски** | `task add/take/submit/approve/reopen/block/list` | «добавь таску», «беру», «сдал», «принято» |

Все операции — **только через** `node scripts/team-tasks.mjs …` → JSON → ответ пользователю.

---

## Жизненный цикл таски

```
planned → in_progress (take) → awaiting_review (submit) → done (approve owner)
                                                      ↘ reopen (owner)
blocked — на любом шаге
overdue — вычисляемое (дедлайн прошёл, статус ≠ done/awaiting_review)
```

| Переход | Кто |
|---|---|
| `take` | любой member (таска planned/blocked) |
| `submit` | **только assignee** |
| `approve` | **только owner** |
| `reopen` | **только owner** (из awaiting_review) |

**Auto-submit при выходе:** member с `in_progress` таской → `awaiting_review` + `submit_note: auto-submit on member leave`.

---

## Ключевые правила

1. **Ключ пользователя — `telegram_id`** (иммутабельный). `@username` — только отображение.
2. **Изоляция через membership** — чужие команды/таски не показывать. Нет «покажи всё подряд».
3. **Owner ≠ member по approve** — submit делает assignee, approve/reopen — owner.
4. **Инвайты незарегистрированным** — код живёт **5 дней UTC**. При первом сообщении боту → `invites resolve`.
5. **Все даты в UTC** (`2026-06-27T15:00:00+00:00`), не local time.

---

## Хранилище

```
data/teams/<team_id>/
  meta.json           # цель, owner, created_at
  members.json        # состав (user_key, telegram_id, role)
  invites.json        # открытые инвайты
  tasks.json          # командные таски
  notifications.log   # лог событий (owner-only read)

users/<user_key>/teams.json   # индекс «в каких командах я»
```

Схема полей: `references/data-schema.md`.

---

## CLI (обязательный flow)

**Старт сессии / новый пользователь** — после `session-start`:
```bash
node scripts/team-tasks.mjs invites resolve --user <user_key> --telegram-id <id> [--username @x]
```

**Команды:**
```bash
node scripts/team-tasks.mjs team create --user <key> --goal "Q&A сайт" --telegram-id 123 [--username @alice]
node scripts/team-tasks.mjs team invite --user <key> --team team-abc --telegram-id 456 [--username @bob]
node scripts/team-tasks.mjs team accept --user <key> --code <invite_code> --telegram-id 456
node scripts/team-tasks.mjs team leave --user <key> --team team-abc
node scripts/team-tasks.mjs team list --user <key>
node scripts/team-tasks.mjs team show --user <key> --team team-abc
```

**Таски:**
```bash
node scripts/team-tasks.mjs task add --user <key> --team team-abc --title "Верстка главной" --deadline 2026-06-27T15:00:00+00:00
node scripts/team-tasks.mjs task take --user <key> --team team-abc --task task-001 --telegram-id 456
node scripts/team-tasks.mjs task submit --user <key> --team team-abc --task task-001 [--note "готово"]
node scripts/team-tasks.mjs task approve --user <key> --team team-abc --task task-001
node scripts/team-tasks.mjs task reopen --user <key> --team team-abc --task task-001 --reason "доработать"
node scripts/team-tasks.mjs task list --user <key> --team team-abc [--status overdue]
```

**Owner-only лог:**
```bash
node scripts/team-tasks.mjs notifications --user <key> --team team-abc
```

При `{ ok: false }` — не выдумывать результат, показать `error`.

---

## Уведомления

Скрипт возвращает поле `notifications` с `recipients[]` (user_key + telegram_id). Агент **рассылает** короткое сообщение каждому recipient (кроме `exclude_user_key` если указан).

Шаблоны — `references/message-templates.md`.

---

## Отличия от личных тасков

| | Личные (`task-tracker`) | Командные (`team-tasks`) |
|---|---|---|
| Файл | `users/<key>/tasks.yaml` | `data/teams/<id>/tasks.json` |
| Multi-user | только свой `user_key` | membership в команде |
| Назначение | исполнитель = владелец | один assignee, видят все members |
| Approve | не нужен | owner подтверждает submit |
| Уведомления | себе | всем members команды |

---

## Связанные скиллы

| Скилл | Связь |
|---|---|
| `session-start` | перед работой — `invites resolve` для новичков |
| `task-decomposition` | крупную командную таску можно разбить до `task add` |
| `goal-checkin-notifier` | доставка `notifications.recipients` в Telegram |
| `help-menu` | блок «КОМАНДА» |

---

## Anti-patterns

- ❌ Показывать таски команды без проверки membership (всегда через скрипт)
- ❌ Approve не-owner'ом
- ❌ Submit не-assignee
- ❌ Хранить командные таски в `tasks.yaml` пользователя
- ❌ Local time в дедлайнах — только UTC
