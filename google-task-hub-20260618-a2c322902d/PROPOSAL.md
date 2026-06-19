---
name: "google-task-hub"
description: "Google Tasks + Sheet + Calendar: трекинг, статистика, КТ. Замена Obsidian/yaml."
status: proposal
version: "v1"
date: "2026-06-18T08:48:52.681Z"
---

# google-task-hub

> Единый скилл интеграции с Google: Tasks — список для рук, Sheet — источник истины и дашборды, Calendar — дедлайны с временем и контрольные точки. Переносит весь функционал `task-tracker` + `longterm-stats` с Obsidian/`state/tasks.yaml` на Google.

---

## 🎯 Когда подключать

- Нужна синхронизация задач с Google Tasks
- Пользователь отчитывается о прогрессе («сделала X», «Y на 50%»)
- Запросы статистики: «прогресс», «что горит», «итог дня», «статистика за неделю/месяц»
- Срабатывают cron-триггеры: напоминания, КТ, дедлайны, day-end
- Команды «синхронизируй задачи», «обнови дашборд»

---

## 🏗 Архитектура

```
Google Tasks (UI, галочки)
       ↕ sync по google_task_id
Google Sheet «Tasks» (источник истины: weight, progress, status, …)
       ↕ read/write
Google Calendar (дедлайны datetime + события КТ)
       ↕
google-task-hub (этот скилл)
       ↓
Telegram + листы Dashboard Short / Dashboard Long
```

**Граница:** скилл **не создаёт цели** и **не планирует последовательность** — только синхронизирует, обновляет `status`/`progress`/`actual_duration`, считает статистику, рендерит дашборды. Создание атрибутов — скилл целеполагания; порядок — скилл планирования.

---

## 📥 Источник данных

### Google Sheet

Spreadsheet ID хранится в `state/google-task-hub.json` (см. `references/config-schema.md`).

**Лист `Tasks`** — одна строка = одна задача:

| Колонка | Тип | Описание |
|---------|-----|----------|
| `task_id` | int | Внутренний ID (PK) |
| `google_task_id` | string | ID задачи в Google Tasks |
| `google_list_id` | string | ID списка Tasks |
| `name` | string | Название |
| `category` | string | Категория (= имя списка Tasks) |
| `weight` | int | 1–10 |
| `deadline` | ISO datetime | Дедлайн с временем |
| `status` | enum | planned \| in_progress \| done \| blocked \| overdue |
| `progress` | int | 0–100 |
| `actual_duration` | int | минуты, nullable |
| `estimated_duration` | int | минуты, nullable |
| `task_type` | enum | short \| long |
| `checkpoints` | JSON string | `[{"time":"14:00","target_progress":50,"description":"..."}]` |
| `calendar_deadline_event_id` | string | ID события Calendar |
| `closed_at` | ISO datetime | nullable |
| `updated_at` | ISO datetime | |

**Лист `Dashboard Short`** — формулы + блоки для краткосрочного трекера (замена `Кратковременный трекер задач.md`).

**Лист `Dashboard Long`** — агрегаты неделя/месяц/год/всё время (замена `Долговременный трекер задач.md`).

**Лист `CheckpointLog`** — история проверок КТ.

**Лист `DailyLog`** — итоги дней.

### Google Tasks — маппинг списков

| `task_type` / `category` | Список Tasks |
|--------------------------|--------------|
| short + category | «Сегодня — {category}» или «{category}» |
| long | «Долгосрочные» |

**Title в Tasks** (агент обновляет при sync out):
- `▶ 60% · Название` — in_progress
- `🔥 Название` — overdue (вычисляемый)
- `🚫 Название` — blocked
- `Название` — planned / done (completed в API)

**Notes** (первая строка, только для чтения человеком):
`id:{task_id} · вес {weight} · {progress}%`

### Google Calendar

- Событие дедлайна: `🔥 Дедлайн: {name}` на `deadline` datetime; description: `task_id:{task_id}`
- Событие КТ: `КТ {HH:MM}: {name} ({target}%)`; description: `task_id:{task_id};checkpoint`

---

## 🔄 Синхронизация (ядро скилла)

### Sync IN (Tasks → Sheet)

Запуск: cron каждые 15 мин, по команде «синхронизируй», после webhook (если есть).

```
1. LIST все task lists → для каждого списка LIST tasks
2. Сопоставить по google_task_id
3. Если completed в Tasks и progress < 100 в Sheet → progress=100, status=done, closed_at=now
4. Если новая задача в Tasks без строки → INSERT с дефолтами (weight=1, progress=0, status=planned, task_type по списку)
5. Если title/notes изменены вручную → обновить name, НЕ трогать weight/progress без явного паттерна в notes
6. updated_at = now
```

### Sync OUT (Sheet → Tasks)

Запуск: после каждого update progress/status от пользователя или агента.

```
1. PATCH task: title (с emoji/%), due (date part of deadline), notes, status
2. Если progress=100 или status=done → completed=true
3. Если calendar_deadline_event_id пуст и deadline задан → CREATE calendar event, сохранить id
4. Если checkpoints изменились → upsert calendar events КТ
5. Обновить Dashboard Short / Long (формулы пересчитываются автоматически; агент пишет текстовые блоки если нужно)
```

### Конфликты

- **Источник истины для метаданных:** Sheet
- **Источник истины для «галочки»:** если пользователь отметила в Tasks — Sheet подстраивается (sync IN)
- При расхождении progress: Sheet побеждает, кроме completed в Tasks → 100%

---

## 💬 Команды → действия

| Команда | Действие |
|---------|----------|
| «прогресс», «что по прогрессу?» | шаблон `progress` (краткоср.) |
| «что горит?», «горит?» | шаблон `urgent` |
| «напомни про X» | шаблон `reminder` |
| «итог дня» | шаблон `day-end` + запись DailyLog + hook longterm |
| «статистика за неделю/месяц/год», «всё время» | шаблоны `weekly`/`monthly`/`yearly`/`all-time` |
| «долговременные задачи» | `long-tasks` |
| «что горит долгосрочно» | `long-deadlines` |
| «сделала X», «Y на 50%» | update Sheet row + sync OUT + `progress` |
| «синхронизируй задачи» | sync IN + sync OUT |
| «обнови дашборд» | перерендер текстовых блоков Dashboard Short |
| «обнови долговременный дашборд» | Dashboard Long |

Шаблоны вывода — **идентичны** `task-tracker` и `longterm-stats` (скопировать дословно из applied-версий).

---

## ⏰ Авто-триггеры

| Триггер | Действие |
|---------|----------|
| За 5 мин до старта (Calendar/Sheet) | `reminder` |
| За 30 мин / 2 ч / 4 ч до deadline | `urgent`-лайт |
| После deadline, progress < 100 | `urgent` + overdue, каждый час |
| В момент КТ (Calendar) | `checkpoint` — сравнить actual vs target_progress |
| 22:00 или 2 ч бездействия | `day-end` |
| Каждые 2 ч активной работы | короткий `progress` |
| Воскресенье 22:00 | `weekly` + Dashboard Long |
| Последний день месяца 22:00 | `monthly` + Dashboard Long |
| Cron каждые 15 мин | sync IN |

Каналы: cron → `systemEvent`; ручной → Telegram.

---

## 🧮 Формулы

Без изменений относительно `task-tracker` + `longterm-stats`:

```
overall = Σ(weight × progress) / Σ(weight)
category_progress = Σ(weight × progress) / Σ(weight) в категории
period_progress_hours = Σ(actual_duration) / Σ(estimated_duration)
risk = (planned_progress - actual_progress) / planned_progress > 0.25
overdue = now > deadline AND progress < 100
```

Реализация: агент считает в коде/логике; Sheet-дashboard дублирует через формулы IMPORTRANGE/QUERY где возможно.

---

## 🔐 Авторизация Google

- OAuth credentials: `~/.openclaw/credentials/google/` (Tasks API, Sheets API, Calendar API)
- Scopes: `tasks`, `spreadsheets`, `calendar.events`
- При первом запуске — guided setup; ID spreadsheet и list mapping в `state/google-task-hub.json`

Подробности: `references/google-api.md`

---

## 📁 Структура скилла

```
google-task-hub/
├── SKILL.md
├── references/
│   ├── config-schema.md
│   ├── google-api.md
│   ├── sheet-layout.md
│   └── sync-rules.md
└── scripts/          # опционально, фаза 2
    ├── sync_in.py
    └── sync_out.py
```

---

## 🔗 Связь с существующими скиллами

| Скилл | После внедрения |
|-------|-----------------|
| `task-tracker` | **deprecated** → логика внутри `google-task-hub` (краткоср.) |
| `longterm-stats` | **deprecated** → логика внутри `google-task-hub` (долгоср.) |
| `goal-checkin-notifier` | читает deadline/scheduled из Sheet вместо plan json |
| целеполагание | CREATE row в Sheet + task в Tasks + calendar event |
| Obsidian дашборды | **отключить** после миграции |

---

## 📋 MVP по фазам

**Фаза 1 (скилл v1):** Sheet как yaml; все шаблоны в Telegram; ручной sync.
**Фаза 2:** двусторонний Tasks sync; Calendar дедлайны.
**Фаза 3:** Calendar КТ + checkpoint template; cron.
**Фаза 4:** Dashboard листы; deprecate Obsidian.

---

## ⚠️ Явные ограничения

- Не создаёт задачи с нуля (→ целеполагание)
- Не меняет weight/deadline/category без делегирования
- Не планирует порядок (→ планирование)
- Google Tasks API не хранит время due — время только Calendar + Sheet

---

## 📋 Критерии приёмки

1. «сделала X на 50%» → Sheet обновлён, Tasks title показывает `▶ 50%`, Telegram — шаблон progress
2. Галочка в Tasks → Sheet progress=100
3. «что горит» → те же таблицы что в task-tracker
4. «итог дня» → day-end + строка DailyLog
5. «статистика за неделю» → weekly из longterm-stats
6. Dashboard Short/Long открываются в браузере и актуальны
