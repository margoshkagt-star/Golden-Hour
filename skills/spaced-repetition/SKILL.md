---
name: "spaced-repetition"
description: "Anki-стиль: повторение слабых тем по растущим интервалам (1→3→7→14→30)."
status: live
script: "scripts/spaced-repetition.mjs"
version: "v2-thin"
date: "2026-06-19T11:30:00.000Z"
---

# spaced-repetition

**Скрипт:** `node scripts/spaced-repetition.mjs --user <user_key> [--date YYYY-MM-DD]`

## Когда вызывать
- «что повторить», «слабые темы на сегодня», «Anki-очередь»
- Автоматически в `daily-plan` — бустить слабые темы в расписании
- После чек-ина — обновить интервалы по результатам

## Что делает
1. Берёт слабые темы (level=weak) из `profile.md` + факт повторения из `progress.md`
2. Считает due-темы (прошло ≥ интервала с последнего повторения)
3. Интервалы: 1→3→7→14→30 дней (после каждого успешного повтора ×2, не больше 30)
4. Возвращает JSON: due-список, кандидаты, обновлённые интервалы

## Контракт
- stdout = JSON `{ ok, date, due: [{topic, interval, last_seen}], candidates, count }`
- Если `due` пуст — пользователю сказать «сегодня повторов нет»
- При обновлении — писать в `progress.md` запись `[sr] <topic>: done at <date>, next at <date+N>`

## Связь
- `lib/spaced-repetition.mjs` — логика интервалов
- Использует: `progress.md` (записи), `profile.md` (level), **`temporal-kg/topic-index.json`** (`last_seen`)
- Запускается: `daily-plan.mjs` (через `task-weighting` для boost)
