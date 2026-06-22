# google-api.md

## Установленные пакеты

```
py -m pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
```

- `google-api-python-client` — официальный клиент Google API
- `google-auth-oauthlib` — OAuth 2.0 flow
- `google-auth-httplib2` — HTTP транспорт для Google Auth

## Используемые API

### Google Tasks API (v1)
- `tasklists.list` — список всех Task lists
- `tasks.list` — задачи в list
- `tasks.get` / `tasks.patch` / `tasks.insert` / `tasks.delete`
- `tasks.move` — переместить задачу

### Google Sheets API (v4)
- `spreadsheets.create` — создать таблицу
- `spreadsheets.values.get` / `update` / `append`
- `spreadsheets.batchUpdate` — структурные изменения (формулы, форматирование)

### Google Calendar API (v3)
- `events.list` / `events.insert` / `events.patch` / `events.delete`

## OAuth Scopes

```
https://www.googleapis.com/auth/tasks
https://www.googleapis.com/auth/spreadsheets
https://www.googleapis.com/auth/calendar.events
```

## Файл client_secret.json

Скачивается из Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs (Desktop app). Кладётся в `~/.openclaw/credentials/google/client_secret.json`.

**Внимание:** Google Cloud Console недоступен из РФ. Варианты:
- Зарубежный Google-аккаунт + VPN
- Передать задачу коллеге/другу за пределами РФ
- Использовать mock-режим (для разработки и демо)

## Файл token.json

Создаётся автоматически при первом запуске `auth_setup.py`. Хранит refresh token. Лежит в `~/.openclaw/credentials/google/token.json`.

## Mock-режим

Когда `mode: mock` или credentials нет:
- `google_api_client.py` подменяет реальные API-вызовы на чтение/запись JSON-файлов в `mock_dir`
- Структура mock-store повторяет реальные API responses
- Скрипты `sync_in.py` / `sync_out.py` / `render_dashboard.py` работают одинаково в обоих режимах

См. `mock-mode.md` для деталей.
