---
name: "temporal-kg"
description: "Temporal knowledge graph: хранит события с временными метками и связями между ними. Не «что знаю», а «когда и как связано». Для адаптивного обучения и self-review."
author: pending-clarification
status_source: agent-generated-2026-06-18 (per karim's request)
---

# Temporal Knowledge Graph — temporal-kg

**Use when:** нужно понять не «что я знаю по физике», а «когда я последний раз трогал тему X, что предшествовало, что было после, какие были ошибки в этот период». Линейный `progress.md` для этого не подходит.

**Don't use when:**
- Нужен простой список задач → `task-tracker`
- Нужен дневник чек-инов → `daily-study-checkin`
- Нужен отчёт «что изучил за неделю» → `progress.md` (и так сойдёт)

## Назначение

`progress.md` сейчас — это **линейный дневник**: запись за записью, теряются связи. Например:
- «15.06 ошибся в задаче на закон Кулона»
- «17.06 решил ту же задачу правильно»

Это **одна и та же** тема, но в линейном дневнике связь не видна. Temporal KG хранит **граф событий с временными метками и явными рёбрами** между ними.

## Структура графа

**Ноды (events)** — атомарные события:
- `study(topic, result)` — изучал тему, результат (success/partial/fail)
- `solve(problem_id, result, error_type)` — решал задачу
- `checkin(date, mood, energy, topics)` — ежедневный чек-ин
- `milestone(topic, target_date, actual_date, status)` — закрытие темы
- `drift(topic, days_late, reason)` — отставание
- `reflection(event_id, cause, adaptation)` — рефлексия

**Рёбра (relations)** — связи между событиями:
- `preceded_by` / `followed_by` — линейная хронология
- `same_topic` — про одну тему
- `caused_by` — причинность (drift вызван reflection'ом N дней назад)
- `resolves` — задача решена после ошибки в X
- `blocked_by` / `unblocks` — зависимости

## Формат хранения

Один файл на «срез» или один большой JSONL. Прагматично: **JSONL**, аппенд-only, по строке на событие.

`memory/temporal-kg/events.jsonl`:
```json
{"id": "e_001", "ts": "2026-06-15T19:30:00+03:00", "type": "solve", "topic": "электродинамика/закон-кулона", "problem_id": "p_42", "result": "fail", "error_type": "знак заряда"}
{"id": "e_002", "ts": "2026-06-17T20:15:00+03:00", "type": "solve", "topic": "электродинамика/закон-кулона", "problem_id": "p_42", "result": "success", "duration_min": 12}
{"id": "e_003", "ts": "2026-06-17T20:30:00+03:00", "type": "reflection", "linked_event": "e_001", "cause": "не понял знак заряда", "adaptation": "пересмотрел §X учебника"}
```

**Рёбра** — отдельный файл `memory/temporal-kg/edges.jsonl`:
```json
{"from": "e_002", "to": "e_001", "type": "resolves", "ts": "2026-06-17T20:30:00"}
{"from": "e_003", "to": "e_001", "type": "caused_by", "ts": "2026-06-17T20:30:00"}
{"from": "e_001", "to": "e_000", "type": "same_topic", "ts": "2026-06-15T19:30:00"}
```

**Topic-индекс** — для быстрого поиска по теме:
`memory/temporal-kg/topic-index.json`:
```json
{
  "электродинамика/закон-кулона": {
    "events": ["e_001", "e_002"],
    "first_seen": "2026-06-15",
    "last_seen": "2026-06-17",
    "success_rate": 0.5,
    "drift_count": 0,
    "milestone_closed": false
  }
}
```

## Алгоритм

### 1. Запись события
Любой скилл может **emit** событие в temporal-kg:
- `task-triage` после выполнения подзадачи → `solve(problem_id, result, error_type)`
- `daily-study-checkin` → `checkin(date, mood, energy, topics)`
- `study-plan` при достижении milestone → `milestone(topic, target, actual, status)`
- `reflection-loop` → `reflection(linked_event, cause, adaptation)`
- `goal-planned` при drift → `drift(topic, days_late, reason)`

API:
```python
temporal_kg.emit(event_type, **fields)  # append to events.jsonl
temporal_kg.link(from_id, to_id, edge_type)  # append to edges.jsonl
temporal_kg.update_topic_index(topic, event_id)
```

### 2. Чтение: «что я знаю про тему X?»
Запрос: «дай summary по теме X»:
1. Взять список event_id из `topic-index.json[X]`.
2. Прочитать события из `events.jsonl`.
3. Построить timeline с результатами.
4. Выдать:
   - First seen / last seen
   - Success rate (solve → success / total solve)
   - Drift count
   - Milestone status
   - Reflection notes (если есть)
   - Edge: «X решил после Y ошибки, причина: Z»

### 3. Чтение: «что было 2 недели назад?»
Запрос: «что я делал по физике 2 недели назад?»:
1. Фильтр events.jsonl по `ts` в окне.
2. Группировка по типу события.
3. Граф связей (рёбра) внутри окна.
4. Темы, в которых была активность.
5. Дрейфы и рефлексии за окно.

### 4. Чтение: «какие темы забыты?»
1. Все `same_topic` события по `topic-index.json`.
2. `days_since_last = today - last_seen`.
3. Если `days_since_last > review_interval` (из `spaced-repetition`) — тема due.

### 5. Чтение: «граф связей темы X»
Визуализация через `diagram-maker` (Excalidraw/SVG):
- Узлы — события (тип, дата, результат)
- Рёбра — `preceded_by` / `caused_by` / `resolves`
- Цвета: success=зелёный, fail=красный, reflection=жёлтый

## Интеграция с другими скиллами

| Скилл | Что пишет | Что читает |
|---|---|---|
| `daily-study-checkin` | `checkin` события | — |
| `task-triage` | `solve` события | — |
| `study-plan` | `milestone` события | `drift` для адаптации |
| `goal-planned` | `drift` события | timeline цели |
| `spaced-repetition` | — | `last_seen` для расчёта due |
| `reflection-loop` | `reflection` события | предыдущие `drift` для паттерна |
| `adaptive-weights` | — | `drift` события для `stall_penalty` |
| `critical-review` | — | граф для аудита «каша в стыковке» |

## Анти-паттерны

- ❌ Записывать каждое движение мыши — info overload
- ❌ Не обновлять `topic-index.json` — поиск по теме сломается
- ❌ Хранить в SQL/БД — overkill для текущего размера, JSONL читаемый
- ❌ Визуализировать весь граф целиком — нужно уметь drill-down
- ❌ Не линковать события (только `events.jsonl` без `edges.jsonl`) — теряется суть temporal KG
- ❌ Писать в KG без обратной связи в plan/checkin — граф растёт, но не используется
- ❌ Удалять старые события — temporal KG тем и ценен, что помнит

## Масштабирование

- **Сейчас (0–500 событий):** один JSONL, читать целиком.
- **1000+ событий:** разбить по годам/месяцам, `events-2026-06.jsonl`.
- **10000+:** переехать на SQLite, индексы по `topic` и `ts`.
- **Production:** Temporal Knowledge Graph как сервис (Temporal.io / Apache TinkerPop).

## Связанные навыки

- `spaced-repetition` — потребитель `last_seen`
- `adaptive-weights` — потребитель `drift_count`
- `reflection-loop` — эмиттер `reflection` событий
- `diagram-maker` — визуализация графа
- `critical-review` — потребитель для аудита

## Пример запроса (что увидит пользователь)

```
📊 Электродинамика / закон Кулона

**Timeline:**
- 15.06 19:30 — solve p_42 — ❌ (знак заряда)
- 17.06 20:15 — solve p_42 — ✅ (12 мин)
- 17.06 20:30 — reflection — пересмотрел §X

**Stats:**
- 2 solve, success rate 50%
- 0 drift
- last_seen: 3 дня назад
- status: ⚠️ слабая тема, due на повтор через 1 день (zero-level)

**Edges:**
- e_002 (17.06 success) resolves e_001 (15.06 fail)
- e_003 (reflection) caused_by e_001
```

**Это сильно информативнее, чем «15.06: ошибся. 17.06: решил».**
