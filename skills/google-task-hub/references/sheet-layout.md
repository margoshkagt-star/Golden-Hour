# sheet-layout.md

## Лист `Tasks` (источник истины)

| Колонка | Поле | Тип | Описание |
|---------|------|-----|----------|
| A | `task_id` | int | внутренний PK |
| B | `google_task_id` | string | ID задачи в Google Tasks |
| C | `google_list_id` | string | ID Task list |
| D | `name` | string | название |
| E | `category` | string | категория (= лист Tasks) |
| F | `weight` | int | 1–10 |
| G | `deadline` | ISO datetime | дедлайн |
| H | `status` | enum | planned / in_progress / done / blocked / overdue |
| I | `progress` | int | 0–100 |
| J | `actual_duration` | int | минуты, nullable |
| K | `estimated_duration` | int | минуты, nullable |
| L | `task_type` | enum | short / long |
| M | `checkpoints` | JSON string | `[{"time":"14:00","target_progress":50,"description":"..."}]` |
| N | `calendar_deadline_event_id` | string | ID события в Calendar |
| O | `closed_at` | ISO datetime | когда закрыта |
| P | `updated_at` | ISO datetime | последнее обновление |

## Лист `Dashboard Short` (краткосрочный)

Текущие задачи на сегодня/неделю, прогресс по категориям, риски.

Структура:
- A1: `# Dashboard Short` (заголовок)
- A3: `## Сегодня`
- A4+: список задач на сегодня с прогрессом
- B20: `## Прогресс по категориям`
- B21+: категория + суммарный прогресс

Генерируется `render_dashboard.py` (с флагом `--short`).

## Лист `Dashboard Long` (долгосрочный)

Долговременные задачи, статистика за неделю/месяц/год.

Структура:
- A1: `# Dashboard Long`
- A3: `## Долговременные задачи`
- A4+: список long-задач с прогрессом
- A20: `## Статистика`
- A21+: неделя/месяц/год/всё время — вес + часы

Генерируется `render_dashboard.py` (с флагом `--long`).

## Лист `CheckpointLog`

История срабатывания КТ (контрольных точек):
- timestamp, task_id, target_progress, actual_progress, status

## Лист `DailyLog`

Ежедневный итог:
- date, tasks_done, hours_spent, weight_done, top_categories
