---
name: "longterm-stats"
description: "Статистика за период: streak, выполненные задачи, время."
status: live
script: "scripts/longterm-stats.mjs"
version: "v2-thin"
date: "2026-06-19T11:30:00.000Z"
---

# longterm-stats

**Скрипт:** `node scripts/longterm-stats.mjs --user <user_key> [--period week|month|year|all]`

## Когда вызывать
- «статистика за неделю/месяц/год/всё время»
- «сколько я сделал за X», «мой streak»

## Что делает
1. Парсит `users/<user_key>/tasks.yaml` (закрытые задачи + время)
2. Парсит `users/<user_key>/progress.md` (чекин-ы, streak)
3. Парсит `users/<user_key>/plans/*.json` (запланированные/выполненные)
4. Читает `users/<user_key>/temporal-kg/` (события за период)
5. Считает: streak, задач выполнено / пропущено, часы по темам, % от плана
5. Возвращает JSON

## Контракт
- stdout = JSON `{ ok, period, summary, by_topic, streak, hours }`
- `summary` — 1-3 строки для пользователя
- `by_topic` — разбивка по темам (топ-N)
- `streak` — текущая и лучшая серия дней

## Связь
- `lib/cli.mjs` — args, paths
- Не зависит от других скиллов
