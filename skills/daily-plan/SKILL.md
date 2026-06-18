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
1. Прочитать `users/<user_key>/profile.md` (цель, уровни, `hours_per_week`, `deadline`, `priorities`, `difficulty`, `daily_load`) и `users/<user_key>/plan.md` (текущая неделя макро-плана). **Требует `setup_status: complete`** — иначе вести в настройку.
2. **Оценить кандидатов** через `task-weighting`: для каждой темы/задачи на сегодня посчитать `eff_priority` (важность + дедлайн + слабость) и `eff_difficulty` (сложность + уровень). Взять бюджет дня `D_max` из `daily_load`.
3. **Собрать день** через `daily-balancer`:
   - важные темы — вперёд и больше минут;
   - суммарная `eff_difficulty` блоков ≤ `D_max` (день не перегружен);
   - тяжёлые блоки (≥4) — в утро, средние — днём, лёгкие (≤2) — вечером;
   - не более одного блока сложности 5; между двумя тяжёлыми — лёгкий; что не влезло — перенести.
4. Сохранить в `users/<user_key>/plans/YYYY-MM-DD.json` (UTF-8, pretty JSON). В каждую задачу писать `weight` и `difficulty`.
5. Подтвердить с балансом: `План на сегодня: M задач, ~H ч, нагрузка <Σdiff>/<D_max>. Приоритет: <важная тема>.`

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
      "weight": 5,
      "difficulty": 4,
      "status": "planned",
      "snoozed_until": null
    }
  ],
  "load": { "sum_difficulty": 8, "budget": 9 }
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

## Распределение задач по времени (через `daily-balancer`)
- **Утро (10:00)** — самые тяжёлые блоки (сложность ≥4) / новая теория (свежая голова)
- **День (14:00)** — средние (3) / задачи / практика
- **Вечер (18:00)** — лёгкие (≤2) / повторение / карточки / тест

## Если профиля нет / `setup_status ≠ complete`
- Не создавать план. Сказать: «Сначала закончим настройку» → вести в онбординг через `session-start`.

## Данные
- Читает: `users/<user_key>/profile.md` (вкл. `priorities`, `difficulty`, `daily_load`), `users/<user_key>/plan.md`
- Пишет: `users/<user_key>/plans/YYYY-MM-DD.json` (задачи с `weight`/`difficulty` + `load`)

## Зависимости
- После `setup-finalize` + `study-plan` (`setup_status: complete`)
- Использует `task-weighting` (оценка) и `daily-balancer` (сборка дня)
- Перед `goal-checkin-notifier`

## Где живёт реальное исполнение

**`SOUL.md` → секция «После onboarding»** — это то, что агент реально выполняет. Этот скилл — **дизайн-документ** для справки и эволюции.
