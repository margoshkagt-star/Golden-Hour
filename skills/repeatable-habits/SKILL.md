---
name: "repeatable-habits"
description: "Планировщик повторяющихся привычек и действий (daily/weekly/monthly) с учётом streak и адаптивного расписания"
---

<!-- source: ts=2026-06-18 user_id=1038917447 -->

<!-- source: ts=2026-06-17T12:16:35+03:00 user_id=1038917447 -->
# repeatable-habits

## Цель
Помогает пользователю golden-hour вести список повторяющихся действий (привычки, ритуалы, регулярные задачи) с автотрекингом streak, адаптивным расписанием (если пропустил — сдвигает), и интеграцией в `daily-plan` / `goal-checkin-notifier`.

## Триггер
- **Авто:** после завершения онбординга (`setup_status: complete`) и в момент генерации `daily-plan` — добавляет сегодняшние привычки в список задач.
- **Вручную:** «добавь привычку X каждый день», «какой у меня streak по Y», «пропустил сегодня — сдвинь Z».

## Логика
1. Хранение списка привычек: `users/<user_key>/habits.yaml` (формат: `name`, `cadence` = `daily/weekly/monthly`, `time_of_day` = `HH:MM`, `weight` = 1-5, `streak` = int, `last_done` = `YYYY-MM-DD`, `adaptive` = bool).
2. **Утренний бриф:** `goal-checkin-notifier` в `morning_brief.weather_block` рядом добавляет `habits_block` — список привычек на сегодня (по `cadence` + `last_done`).
3. **Трекинг выполнения:** когда пользователь в течение дня отмечает «сделал X» (через `current-tasks` / `goal-checkin-notifier`) — обновить `last_done`, увеличить `streak` на 1.
4. **Адаптивное расписание:** если `last_done < today - cadence * 2`, предложить пользователю сдвинуть (через `goal-checkin-notifier` evening check-in).
5. **Streak сгорает** если `last_done < today - cadence` — сбросить `streak` в 0.
6. **Вечерний отчёт:** `goal-checkin-notifier` evening check-in показывает «сегодня выполнено N из M, streak по X = N дней».

## Вход / Выход
- **Вход:** `user_key`, текущая дата, `habits.yaml`.
- **Выход:** обновлённый `habits.yaml` (streak/last_done), блок в `morning_brief`, вечерний отчёт.

## Примеры
### Пример 1
**Запрос:** «добавь привычку "читать 30 минут" каждый день в 21:00»
**Результат:** в `habits.yaml` добавлено:
```yaml
- name: читать 30 минут
  cadence: daily
  time_of_day: "21:00"
  weight: 3
  streak: 0
  last_done: null
  adaptive: true
```

### Пример 2
**Запрос:** «какой у меня streak по привычке "тренировка"?»
**Результат:** "Тренировка: streak = 12 дней, last_done = 2026-06-17."

## Что НЕ делает
- ❌ Не создаёт привычки без явной команды пользователя.
- ❌ Не удаляет привычки — только помогает архивировать (через отдельный скилл).
- ❌ Не отправляет уведомления в Telegram сам — передаёт в `goal-checkin-notifier`.
- ❌ Не работает с привычками в прошлом (ретроспектива) — только вперёд.

## Зависимости
- skills: `goal-checkin-notifier`, `daily-plan`, `current-tasks`, `task-tracker`, `user-profile`
- tools: `read`, `write`, `edit`
- данные: `users/<user_key>/habits.yaml` (новый файл), `users/<user_key>/plans/YYYY-MM-DD.json`
