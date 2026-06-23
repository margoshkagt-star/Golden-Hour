# Temporal KG — data schema (Golden Hour)

Per-user storage: `users/<user_key>/temporal-kg/`

| File | Назначение |
|---|---|
| `events.jsonl` | События (append-only, одна строка = JSON) |
| `edges.jsonl` | Связи между событиями |
| `topic-index.json` | Индекс по темам для быстрого поиска |

## Event (`events.jsonl`)

```json
{"id":"e_1782140000_abc","ts":"2026-06-22T19:30:00+03:00","type":"solve","topic":"алгебра/производная","problem_id":"p_42","result":"fail","error_type":"знак"}
```

**Типы:** `study`, `solve`, `checkin`, `milestone`, `drift`, `reflection`

## Edge (`edges.jsonl`)

```json
{"from":"e_002","to":"e_001","type":"resolves","ts":"2026-06-22T20:30:00+03:00"}
```

**Типы:** `preceded_by`, `followed_by`, `same_topic`, `caused_by`, `resolves`, `blocked_by`, `unblocks`

## Topic index (`topic-index.json`)

```json
{
  "алгебра/производная": {
    "events": ["e_001", "e_002"],
    "first_seen": "2026-06-15",
    "last_seen": "2026-06-17",
    "success_count": 1,
    "fail_count": 1,
    "solve_count": 2,
    "drift_count": 0,
    "milestone_closed": false
  }
}
```

## CLI

```bash
node scripts/temporal-kg.mjs emit --user <key> --type solve --topic "..." --result success
node scripts/temporal-kg.mjs topic --user <key> --topic "..."
node scripts/temporal-kg.mjs reflection --user <key> --topic "..." --causes "..." --adaptation "..."
node scripts/temporal-kg.mjs checkin --user <key> --mood 4 --topics "Алгебра"
node scripts/temporal-kg.mjs forgotten --user <key> --days 7
```

## Эмиттеры (обязательно через скрипт)

| Скилл | Команда |
|---|---|
| `daily-study-checkin` | `checkin` |
| `reflection-loop` | `reflection` (+ опц. `drift`) |
| Закрытие задачи / разбор ошибки | `solve` |
| `study-plan` milestone | `milestone` |

`progress.md` остаётся человекочитаемым дневником; KG — машиночитаемый граф.

## Потребители

| Скилл | Читает |
|---|---|
| `spaced-repetition` | `topic-index.json` → `last_seen` |
| `longterm-stats` | события за период (`kgPeriodStats`) |
| Агент по запросу | `topic`, `window`, `forgotten` |

## Миграция

`node scripts/temporal-kg.mjs import-progress --user <key>` — из существующего `progress.md`.
