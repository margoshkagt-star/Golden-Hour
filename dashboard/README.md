# Фельпик Dashboard

Веб-дашборд для OpenClaw: Kanban, календарь (день/неделя/месяц), costs, roster агентов.

## Запуск

```powershell
cd dashboard
.\start_dashboard.ps1
```

Откройте: http://127.0.0.1:18790/

## Состав

| Файл | Назначение |
|------|------------|
| `dashboard.html` | UI (SPA) |
| `backend.py` | HTTP API, task-pool, snapshot |
| `gateway-chat.js` | Чат с gateway |
| `start_dashboard.ps1` | Запуск backend + браузер |

## Grafana (опционально)

```powershell
cd grafana
.\start_grafana.ps1
```

Подробности: `STATUS.md`
