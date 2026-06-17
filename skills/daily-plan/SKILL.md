---
name: "daily-plan"
description: "Генерирует users/<user_key>/plans/YYYY-MM-DD.json из профиля и макро-плана пользователя. Без дневного плана goal-checkin-notifier молчит. Требует setup_status=complete."
---

# daily-plan

## Цель
Сгенерировать план на сегодня из профиля и макро-плана пользователя. Файл `users/<user_key>/plans/YYYY-MM-DD.json` нужен `goal-checkin-notifier`, чтобы тот слал morning brief, task pings и evening check-in.

## Триггер
- **Авто:** после завершения цепочки onboarding (имя → purpose → ветка → самооценка)
- **Вручную:** «спланируй день» / «создай план» / «обнови план»

## Логика
1. Прочитать `users/<user_key>/profile.md` (цель, уровни, `hours_per_week`, `deadline`) и `users/<user_key>/plan.md` (текущая неделя макро-плана). **Требует `setup_status: complete`** — иначе вести в настройку.
2. Сгенерировать структуру:
   - Для каждого subject создать `goal` с `weight` (1-5)
   - Создать 2-4 задачи на сегодня (по `daily_hours / 7` ≈ часов в день)
   - Распределить по времени: morning (10:00), afternoon (14:00), evening (18:00)
3. Сохранить в `users/<user_key>/plans/YYYY-MM-DD.json` (UTF-8, pretty JSON)
4. Подтвердить: `План на сегодня создан: N целей, M задач, ~H ч.`

## Структура плана

```json
{
  "date": "YYYY-MM-DD",
  "user_id": "u_local",
  "goals": [
    {
      "id": "g_<subject>",
      "title": "...",
      "weight": 5,
      "deadline": "YYYY-MM-DD"
    }
  ],
  "tasks": [
    {
      "id": "t_NNN",
      "goal_id": "g_<subject>",
      "title": "...",
      "scheduled_at": "YYYY-MM-DDTHH:MM:SS+03:00",
      "est_minutes": 60,
      "status": "planned",
      "snoozed_until": null
    }
  ]
}
```

## Адаптация под `purpose`

### `purpose = olympiad`
- Цели по `olympiad_subject`
- Задачи: повторить теорию (60 мин) + решить 5-10 задач (60 мин) по слабым темам из `olympiad_level`

### `purpose = exam`
- Цели по `exam_subjects`
- Задачи: тема из `exam_topics` со слабым уровнем (`zero` / `weak`) — теория + задачи
- Если `exam_subject_variant = profile` — больше задач повышенной сложности

### `purpose = topic`
- Цель по `study_topic`
- Задачи: подпункты из `topic_sublevels` со слабым уровнем

## Распределение задач по времени
- **Утро (10:00)** — теория / новая тема (когда свежая голова)
- **День (14:00)** — задачи / практика
- **Вечер (18:00)** — повторение / карточки / тест

## Если профиля нет / `setup_status ≠ complete`
- Не создавать план. Сказать: «Сначала закончим настройку» → вести в онбординг через `session-start`.

## Данные
- Читает: `users/<user_key>/profile.md`, `users/<user_key>/plan.md`
- Пишет: `users/<user_key>/plans/YYYY-MM-DD.json`

## Зависимости
- После `setup-finalize` + `study-plan` (`setup_status: complete`)
- Перед `goal-checkin-notifier`

## Где живёт реальное исполнение

**`SOUL.md` → секция «После onboarding»** — это то, что агент реально выполняет. Этот скилл — **дизайн-документ** для справки и эволюции.
