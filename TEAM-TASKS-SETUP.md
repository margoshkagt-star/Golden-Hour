# SETUP — установка командных тасков (ветка `team-tasks-install`)

Минимальный дистрибутив OpenClaw-агента для **командной работы**: команды, инвайты, общие таски, уведомления в Telegram.

> Полный «Золотой час» (учёба, план, календарь) — ветка [`agent-install`](https://github.com/margoshkagt-star/Golden-Hour/tree/agent-install).

---

## 1. Предпосылки

| Требование | Проверка |
|---|---|
| **Node.js ≥ 18** | `node --version` |
| **OpenClaw** | `openclaw --version` |
| **Telegram-бот** | токен от [@BotFather](https://t.me/BotFather) |
| **LLM-провайдер** | API-ключ в `openclaw.json` |

---

## 2. Клонирование

```powershell
$ws = "$env:USERPROFILE\.openclaw\workspaces\team-tasks"
git clone -b team-tasks-install https://github.com/margoshkagt-star/Golden-Hour.git $ws
cd $ws
```

---

## 3. Служебные файлы

```powershell
Copy-Item USER.example.md USER.md
Copy-Item MEMORY.example.md MEMORY.md
Copy-Item memory\task-categories.example.md memory\task-categories.md
Copy-Item memory\user-priorities.example.md memory\user-priorities.md
```

Настройте `openclaw.agent.example.json` → `~/.openclaw/openclaw.json` (агент, Telegram, `session.dmScope: per-channel-peer`).

---

## 4. Проверка скриптов

```powershell
node scripts/session-start.mjs --user tg-123456789
node scripts/team-tasks.mjs team create --user tg-111 --goal "Наш проект" --telegram-id 111
node scripts/run-tests.mjs
```

---

## 5. Скиллы в этой ветке (18 + онбординг)

### Ядро командных тасков
| Скилл | Зачем |
|---|---|
| **`team-tasks`** | Команды, инвайты, lifecycle таски, `data/teams/` |
| **`session-start`** | Старт сессии + `invites resolve` |
| **`user-profile`** | `user_key`, `tg-<id>`, папка пользователя |
| **`help-menu`** | Меню с блоком «КОМАНДА» |
| **`goal-checkin-notifier`** | Доставка `notifications.recipients` в Telegram |

### Личные таски (граница с командными)
| Скилл | Зачем |
|---|---|
| `current-tasks` | Личный список (`tasks.md`) |
| `task-tracker` | Личный yaml-трекер |
| `task-decomposition` | Разбивка крупных задач |
| `task-triage` | Приоритизация списков |
| `evening-task-triage` | Вечерний разбор личных дел |

### Командная оркестрация (сабагенты)
| Скилл | Зачем |
|---|---|
| `delegate-via-subagents` | Research / writing / code → сабагент |
| `agent-orchestration` | Тяжёлые параллельные задачи |
| `subagent-queue-pattern` | Устойчивый spawn + очередь результатов |
| `coder` | Код только через `code-writer` |
| `critical-review` | Ревью скиллов и системы |
| `work-on-site` | Стиль работы с кодом проекта |
| `note-to-file` | Сохранение результатов в `memory/` |

### Онбординг (`skills/_onboarding/`)
`hello-intro`, `purpose-select`, ветки exam/olympiad/topic, `setup-finalize` — пока `setup_status ≠ complete` командные таски **не включать**.

---

## 6. Первый запуск

1. Пользователь пишет боту → `session-start` → при `telegram_id` сразу `invites resolve`.
2. Новый пользователь → онбординг → `setup_status: complete`.
3. Owner: «создай команду …» → `team create`.
4. `team invite` → код на 5 дней UTC → новый member: `team accept` или авто при первом сообщении.
5. `task add` → `take` → `submit` → owner `approve`.
6. Поле `notifications` в JSON ответа скрипта → разослать через Telegram всем `recipients`.

Подробности: `skills/team-tasks/SKILL.md`, `SOUL.md`.

---

## 7. Данные

```
data/teams/<team_id>/     # командные БД (gitignore)
users/<user_key>/         # профиль + teams.json (gitignore)
users/_example/           # шаблон
```

---

## 8. code-writer (опционально)

Скилл `coder` требует саб-агента `code-writer` в `openclaw.json`. См. `skills/coder/references/architecture.md`.
