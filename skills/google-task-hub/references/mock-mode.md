# mock-mode.md

## Зачем

Mock-режим позволяет:
- разрабатывать и тестировать скилл **без реального Google-аккаунта**
- демонстрировать работу скилла (для задания, ревью команды)
- прогонять pytest-тесты в CI
- отлаживать логику sync без риска испортить реальные данные

## Как включить

В `state/google-task-hub.json`:
```json
{ "mode": "mock", ... }
```

Или флагом:
```bash
py scripts/sync_in.py --mock
```

## Структура mock-store

```
skills/google-task-hub/tests/fixtures/mock_store/
├── tasklists.json          # список Task lists
├── tasks/
│   ├── <list_id>.json      # задачи одного list
│   └── ...
├── spreadsheet.json        # листы и значения
├── calendar_events.json    # события календаря
└── .version                # счётчик для конфликтов
```

## Соответствие real API

| Real API call | Mock-store файл |
|---------------|-----------------|
| `tasklists.list()` | `tasklists.json` |
| `tasks.list(list_id)` | `tasks/<list_id>.json` |
| `tasks.patch(id, body)` | обновляет `tasks/<list_id>.json` |
| `tasks.insert(body)` | добавляет в `tasks/<list_id>.json` |
| `spreadsheets.values.get()` | `spreadsheet.json` |
| `calendar.events.list()` | `calendar_events.json` |

## Демо-данные

После установки в `mock_store/` лежат:
- 1 task list «Долговременные задачи» с 3 задачами (long)
- 1 task list «Work» с 4 задачами (short)
- Spreadsheet с листами `Tasks` (8 строк), `Dashboard Short`, `Dashboard Long`
- Calendar с 2 событиями (1 дедлайн + 1 КТ)

## Переключение на real

```bash
py scripts/auth_setup.py   # один раз, с client_secret.json
# в state/google-task-hub.json: "mode": "real"
```

После этого все скрипты автоматически пойдут в реальный Google API.
