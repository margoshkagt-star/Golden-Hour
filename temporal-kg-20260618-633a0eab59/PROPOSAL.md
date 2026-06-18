---
name: "temporal-kg"
description: "Temporal knowledge graph: события + связи во времени."
status: proposal
version: "v1"
date: "2026-06-18T08:40:25.835Z"
author: pending-clarification
status_source: agent-generated-2026-06-18 (per karim's request)
---

# Temporal Knowledge Graph — temporal-kg

## Файлы

- `memory/temporal-kg/events.jsonl` — события
- `memory/temporal-kg/edges.jsonl` — рёбра
- `memory/temporal-kg/topic-index.json` — индекс по темам

## События (узлы)

`study`, `solve`, `checkin`, `milestone`, `drift`, `reflection`.

## Рёбра

`preceded_by` / `followed_by` / `same_topic` / `caused_by` / `resolves` / `blocked_by` / `unblocks`.

## API

```python
temporal_kg.emit(event_type, **fields)
temporal_kg.link(from_id, to_id, edge_type)
temporal_kg.update_topic_index(topic, event_id)
```

## Чтение

- «Что знаю про тему X» → topic-index + events → timeline + success_rate + edges
- «Что было 2 недели назад» → фильтр по ts
- «Забытые темы» → `days_since_last > review_interval`

## Связанные (пишут/читают)

daily-study-checkin, task-triage, study-plan, goal-planned, spaced-repetition, reflection-loop, adaptive-weights, critical-review.

Подробная спецификация в `skills-library/drafts/temporal-kg/SKILL.md`.