---
name: "user-profile"
description: "Слой хранения данных по пользователям: папка users/<user_key>/ с профилем, планом, прогрессом и задачами. Читать при любом чтении/записи данных пользователя."
---

# user-profile

Единый слой памяти агента. **Каждый пользователь = отдельная папка.** Все остальные скиллы читают и пишут данные только через эту структуру.

## Идентификатор пользователя (`user_key`)

Определять в начале каждой сессии по отправителю:

| Источник | `user_key` |
|---|---|
| Telegram | `tg-<id>` (напр. `tg-1234567890`) |
| Другой канал (discord/whatsapp/…) | `<channel>-<id>` |
| Webchat / локально / владелец | `local` |

Если id определить нельзя — спросить имя и использовать `name-<slug>` (латиница, нижний регистр, дефисы), но при первой же возможности привязать к id.

## Структура папки

```
users/<user_key>/
  profile.md      # авторитетный профиль (кто, цель, уровень, дедлайн, часы, статус настройки)
  plan.md         # макро-план подготовки (недели/месяцы)
  progress.md     # дневник чек-инов, streak, закрытые темы
  tasks.md        # активные задачи
  teams.json      # индекс команд пользователя (team-tasks)
  temporal-kg/    # граф событий (events.jsonl, edges.jsonl, topic-index.json)
  google-calendar.json  # OAuth refresh-токен + карта uid→eventId (ПРИВАТНО, не коммитить)
  plans/
    YYYY-MM-DD.json   # дневные планы для goal-checkin-notifier
```

Создавать папку и файлы лениво — при первой записи. Никогда не перезаписывать `USER.md`/`MEMORY.md` воркспейса данными конкретного пользователя.

**Командные таски:** общая БД команд — `data/teams/<team_id>/` (в gitignore); у пользователя только индекс `teams.json`. Подробности — `skills/team-tasks/SKILL.md`.

## `profile.md` — шаблон

```markdown
# Профиль — <name>

- **user_key:** <user_key>
- **name:** "<дословно как написал>"
- **channel:** telegram | webchat | ...
- **created:** YYYY-MM-DD
- **updated:** YYYY-MM-DD HH:MM
- **setup_status:** new | in_progress | complete

## Цель
- **purpose:** exam | olympiad | topic

## Параметры (заполняются по ветке)
<!-- olympiad: grade, olympiad_subject, olympiad_level, olympiad_levels, olympiad_level_note -->
<!-- exam: exam_type, exam_subject, exam_subject_variant, exam_topics, exam_topic_levels -->
<!-- topic: study_topic, study_subject, topic_level, topic_sublevels -->

## Дедлайн и время
- **deadline:** YYYY-MM | null
- **hours_per_week:** <число> | null

## Визуализация
- **card_theme:** light | dark  <!-- устарело: всегда dark через study-cards -->

## Заметки
- (свободные факты: «обычно занимаюсь вечером», «не люблю геометрию»)
```

## `setup_status` — машина состояний

| Статус | Что значит | Что разрешено |
|---|---|---|
| `new` | папки нет / профиль пуст | только онбординг (setup) |
| `in_progress` | онбординг начат, не закончен | продолжить онбординг с места обрыва |
| `complete` | профиль + дедлайн + часы есть | рабочие скиллы (план, задачи, чек-ины, напоминания) |

**Рабочие скиллы (`study-plan`, `daily-plan`, `goal-checkin-notifier`, `task-tracker`, `task-triage`, `current-tasks`) включаются только при `setup_status: complete`.** До этого — вести пользователя по настройке.

## Правила записи

- Писать дословно то, что сказал пользователь (имя, заметки) — без нормализации.
- После каждого шага онбординга — обновлять `profile.md` и `updated`.
- PNG-карточки и таблицы — единый встроенный стиль `study-cards` (тёмная тема), см. `scripts/table-cards.mjs` / `study-plan-cards.mjs`.
- При записи нового поля — обновлять только его, не стирать остальные.
- `tasks.md`, `progress.md`, `plan.md` — отдельные файлы (см. `current-tasks`, `daily-study-checkin`, `study-plan`).

## Чтение

- В начале сессии прочитать `users/<user_key>/profile.md` (если есть) — это решает `session-start`.
- `user_key` — **только** из метаданных канала (Telegram `sender_id`), не из текста пользователя.
- Никогда не смешивать данные двух `user_key`.
- Никогда не перечислять папки в `users/` и не открывать чужие профили по просьбе в чате.

## Приватность в чате

- Пользователю — только **его** данные; без имён/целей других, без списка пользователей.
- **Не сообщать Telegram id** (`sender_id`, `chat_id`, `tg-<числа>`, `user_key`) — никому, даже по запросу «какой мой id».
- **Не раскрывать владельца воркспейса** (имя, @username, id из `USER.md`/`MEMORY.md`) пользователям бота.
- Не показывать абсолютные пути, `user_key`, `users/tg-…`, имена внутренних файлов — говорить «твой профиль/план/задачи».

## Зависимости
- Используется **всеми** скиллами как слой хранения.
- `session-start` читает `profile.md` для выбора load/reset.

## Где живёт реальное исполнение
**`SOUL.md` → секции «Старт сессии» и «Хранение данных»** — то, что агент реально выполняет. Этот скилл — дизайн-документ.
