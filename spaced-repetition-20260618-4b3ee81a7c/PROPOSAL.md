---
name: "spaced-repetition"
description: "Anki-кривая 1-3-7-14-30 дней для слабых тем в daily-plan."
status: proposal
version: "v1"
date: "2026-06-18T08:40:25.832Z"
author: pending-clarification
status_source: agent-generated-2026-06-18 (per karim's request)
---

# Spaced Repetition — spaced-repetition

Anki-кривая: новый материал → 1 день → 3 → 7 → 14 → 30. Слабые темы (zero/weak) автоматически попадают в план на повтор через правильный интервал.

## Кривая

| Уровень | Интервал |
|---|---|
| zero | 1 день |
| weak | 3 дня |
| medium | 7 дней |
| strong | 14 дней |
| expert | 30 дней |

Успех → up, ошибка → down, пропуск → missed + 2 дня.

## Алгоритм

1. Слабые темы (zero/weak/medium), сортировка по `last_reviewed` ascending.
2. `next_review = last_reviewed + interval(level)`. Если `next_review <= today` — due.
3. Top-3 due на сегодня.
4. Вставить в `daily-plan` как `[review]` задачи.
5. В `daily-study-checkin`: качество 1-5 → новый уровень, записать `last_reviewed`.
6. Адаптация под дедлайн: <14 дней сжать, <7 — все слабые ежедневно.

## Связанные

- `daily-plan`, `daily-study-checkin`, `study-plan`, `goal-planned`

Подробная спецификация в `skills-library/drafts/spaced-repetition/SKILL.md`.