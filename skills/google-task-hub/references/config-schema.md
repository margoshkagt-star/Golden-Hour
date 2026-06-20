# config-schema.md

## `state/google-task-hub.json`

Конфиг скилла. Лежит в `state/google-task-hub.json` (рабочая копия) или `state/google-task-hub.example.json` (шаблон).

```json
{
  "schema": "openclaw.google-task-hub.config.v1",
  "mode": "real | mock",
  "spreadsheet_id": null,
  "task_list_id": null,
  "calendar_id": "primary",
  "list_mappings": {
    "short": {
      "category": null,
      "task_list_id": null
    },
    "long": {
      "task_list_id": null
    }
  },
  "scopes": [
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar.events"
  ],
  "credentials_path": "~/.openclaw/credentials/google/client_secret.json",
  "token_path": "~/.openclaw/credentials/google/token.json",
  "mock_dir": "skills/google-task-hub/tests/fixtures/mock_store",
  "sync_interval_min": 15,
  "dashboard": {
    "short_sheet_name": "Dashboard Short",
    "long_sheet_name": "Dashboard Long",
    "checkpointlog_sheet_name": "CheckpointLog",
    "dailylog_sheet_name": "DailyLog"
  }
}
```

## Поля

| Поле | Тип | Описание |
|------|-----|----------|
| `mode` | enum | `real` — реальный Google API, `mock` — локальный JSON-store |
| `spreadsheet_id` | string/null | ID Google Spreadsheet (после создания через `auth_setup` или вручную) |
| `task_list_id` | string/null | ID Google Task list (после создания) |
| `calendar_id` | string | ID календаря (по умолчанию `primary`) |
| `list_mappings.short.category` | string/null | категория задач `short`, которые маппятся в отдельный Task list |
| `list_mappings.short.task_list_id` | string/null | ID Task list для short-задач |
| `list_mappings.long.task_list_id` | string/null | ID Task list для long-задач |
| `scopes` | string[] | OAuth scopes |
| `credentials_path` | string | путь к `client_secret.json` |
| `token_path` | string | путь к `token.json` (создаётся при первом OAuth) |
| `mock_dir` | string | путь к папке с mock-данными (для `mode=mock`) |
| `sync_interval_min` | int | интервал cron для sync IN (по умолчанию 15 мин) |
| `dashboard.*_sheet_name` | string | имена листов в Spreadsheet |

## Состояние

После `auth_setup` (Phase 1, при наличии credentials) заполняются:
- `spreadsheet_id` — ID созданной таблицы
- `task_list_id` — ID Task list
- `list_mappings.*.task_list_id` — ID конкретных списков

Если credentials нет — остаётся `mode: mock`, можно тестировать и демонстрировать.
