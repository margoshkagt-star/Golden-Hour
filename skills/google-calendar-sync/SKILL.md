---
name: "google-calendar-sync"
description: "Двусторонняя синхронизация с Google Calendar: бот ставит учебные слоты/дедлайны/задачи в календарь и забирает изменения обратно (перенос, выполнено, удаление). OAuth device flow, отдельно для каждого пользователя. Требует setup_status=complete."
---

# google-calendar-sync

Связывает план пользователя с его Google Calendar. **Движок** — `scripts/gcal.mjs` (делает API), **агент** — собирает события из плана/задач и трактует изменения обратно.

## Когда
- «подключи календарь», «добавь в гугл календарь», «синхронизируй», «выгрузи план в календарь»
- Авто: при наличии подключения — после `daily-plan`/`study-plan` (push) и на heartbeat (pull)
- Требует `setup_status: complete` и подключённого календаря (`users/<user_key>/google-calendar.json`)

## Запуск движка
Из корня воркспейса агента (`golden-hour`):
```
node scripts/gcal.mjs <команда> --user <user_key> [опции]
```
Все команды печатают **одну строку JSON** (`{"ok":true,...}` / `{"ok":false,"error":...}`).

## A. Подключение (один раз на пользователя) — OAuth device flow
1. `node scripts/gcal.mjs connect --user <user_key>`
   → вернёт `verification_url` (`https://www.google.com/device`) и `user_code`.
2. Прислать пользователю в чат:
   ```
   📅 Чтобы подключить Google Calendar:
   1. Открой <verification_url>
   2. Введи код: <user_code>
   3. Разреши доступ и напиши «готово»
   (ссылка живёт <expires_in_min> мин)
   ```
3. Когда пользователь написал «готово» (или авто-поллинг): `node scripts/gcal.mjs connect:poll --user <user_key>`
   - `{"action":"pending"}` → подождать `interval` сек и повторить (до успеха/истечения)
   - `{"action":"connected"}` → готово, подтвердить пользователю
4. Статус: `node scripts/gcal.mjs status --user <user_key>`. Отключить: `disconnect`.

## B. Выгрузка в календарь (бот → Google) — `upsert`
1. Агент собирает массив событий из источников пользователя:
   - **Дневные слоты** из `users/<user_key>/plans/YYYY-MM-DD.json` (утро/день/вечер)
   - **Дедлайны/вехи** из `users/<user_key>/plan.md` (дедлайн, конец недели/блока) — обычно `allDay`
   - **Задачи с датами** из `users/<user_key>/tasks.md`
2. Сформировать файл `users/<user_key>/.gcal-events.json` — массив объектов:
   ```json
   [
     {"uid":"gh:tg-1:daily:2026-06-18:morning","title":"📘 Алгебра: теория","start":"2026-06-18T10:00:00","end":"2026-06-18T11:00:00","description":"Слот из плана"},
     {"uid":"gh:tg-1:deadline:ege","title":"🎯 ЕГЭ","start":"2027-06-01","allDay":true},
     {"uid":"gh:tg-1:task:42","title":"Решить вариант №3","start":"2026-06-20T18:00:00","end":"2026-06-20T19:00:00"}
   ]
   ```
   **Правила `uid`** (стабильные, чтобы обновлять, а не плодить дубли):
   - `gh:<user_key>:daily:<дата>:<слот>` · `gh:<user_key>:deadline:<ключ>` · `gh:<user_key>:week:<N>` · `gh:<user_key>:task:<id>`
3. `node scripts/gcal.mjs upsert --user <user_key> --file users/<user_key>/.gcal-events.json`
   - Скрипт создаёт новые (`created`) и обновляет существующие по `uid` (`updated`), хранит карту `uid → eventId` в `google-calendar.json`.
4. Показать пользователю сводку (создано/обновлено) — без сырого JSON.

## C. Забор изменений (Google → бот) — `pull`
1. `node scripts/gcal.mjs list --user <user_key> --days 14`
   → вернёт `items` (только события бота, с `uid`, `start/end`, `done`, `status`) и `deleted` (отменённые).
2. Агент сравнивает с планом и применяет:
   - **`done:true`** (заголовок начинается с `✅` / `[x]` / `done:`) → отметить тему/задачу выполненной в `progress.md` (+streak), снять из активных.
   - **сдвиг времени** (`start` ≠ запланированного) → перенести слот в плане/`tasks.md`, при необходимости — пересобрать соседние.
   - **`status:"cancelled"` / в `deleted`** → отметить пропуск в `progress.md`, убрать из активных задач.
3. Кратко отчитаться пользователю: «Вижу: перенёс алгебру на 14:00, отметил выполненным вариант №3».

## Удаление одного события
`node scripts/gcal.mjs delete --user <user_key> --uid <uid>` (например, тема убрана из плана).

## Конвенция «выполнено» в календаре
У Google Calendar нет «галочки». Пользователь отмечает выполненное, **добавив в начало названия** `✅` (или `[x]`). Об этом сказать при подключении.

## Данные
- `users/<user_key>/google-calendar.json` — refresh-токен, `calendar_id`, карта `uid→eventId`. **Приватно, не коммитить.**
- `users/<user_key>/.gcal-events.json` — временный буфер выгрузки.
- Учётка приложения (`clientId`/`clientSecret`) — в `secrets.json` (общая на всех), см. `GOOGLE-CALENDAR.md`.

## Что НЕ делает
- ❌ Не работает без подключения и без `setup_status: complete`.
- ❌ Не дублирует события (всегда через `uid`).
- ❌ Не лезет в чужой `user_key`.
- ❌ Не хранит токены в общем `USER.md`/репозитории.

## Зависимости
- Движок: `scripts/gcal.mjs` (Node ≥ 18). Источники: `daily-plan`, `study-plan`, `current-tasks`.
- Настройка приложения: `GOOGLE-CALENDAR.md`.

## Где живёт реальное исполнение
**`SOUL.md` → секция «Google Calendar»** — то, что агент реально выполняет. Этот скилл — дизайн-документ.
