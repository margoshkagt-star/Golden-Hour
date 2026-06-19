---
name: "daily-plan"
description: "Генерирует users/<user_key>/plans/YYYY-MM-DD.json из профиля и макро-плана пользователя. Без дневного плана goal-checkin-notifier молчит. Требует setup_status=complete."
author: pending-clarification
status_source: agent-generated-2026-06-18 (per karim's directive 2026-06-16)
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
   - Для каждого subject создать `goal` с `weight` (1-5, согласовано с `goal-planned` и `task-tracker`)
   - Создать 2-4 задачи на сегодня (по `daily_hours / 7` ≈ часов в день)
   - **Распределить по времени с учётом `profile.notes`:**
     - Прочитать `profile.notes` (напр. «обычно занимаюсь вечером», «утром до школы», «после работы 19-22»)
     - Распарсить паттерны: «утром» / «днём» / «вечером» / «в выходные» / конкретные часы
     - Если паттерны найдены — адаптировать слоты: напр. «вечером» → 19:00 / 20:00 / 21:00
     - Если паттернов нет — fallback на стандартные слоты: morning (10:00), afternoon (14:00), evening (18:00)
   - **Weekend mode:** если в `profile.notes` указано «5 дней × N ч, 2 дня × 0» или найден паттерн «выходные отдыхаю» — на выходные генерировать **облегчённый план** (0-1 задача, ≤ 30 мин) или **light plan** (1-2 лёгкие задачи на повторение)
   - **Topic sublevels priority:** если в `profile.topic_sublevels` есть подпункты с `zero`/`weak` — приоритизировать задачи по ним (больше задач на слабые подпункты)
3. Сохранить в `users/<user_key>/plans/YYYY-MM-DD.json` (UTF-8, pretty JSON)
   - Поле `user_id` = `<user_key>` (НЕ `"u_local"` — это был хардкод, исправлено)
   - Дополнительно поле `user_key: <user_key>` (явное, для парсинга goal-checkin-notifier)
   - Поле `goal_slug` в каждом goal (связь с `users/<key>/plan.md`)
4. Подтвердить: `План на сегодня создан: N целей, M задач, ~H ч.`

## Структура плана

```json
{
  "date": "YYYY-MM-DD",
  "user_id": "<user_key>",
  "user_key": "<user_key>",
  "goals": [
    {
      "id": "g_<purpose>_<subject>",
      "goal_slug": "<goal-slug>",
      "title": "...",
      "weight": 5,
      "deadline": "YYYY-MM-DD",
      "weak_subtopics": ["subtopic1", "subtopic2"],
      "level": "weak"
    }
  ],
  "tasks": [
    {
      "id": "t_NNN",
      "goal_id": "g_<purpose>_<subject>",
      "title": "...",
      "scheduled_at": "YYYY-MM-DDTHH:MM:SS+03:00",
      "est_minutes": 60,
      "status": "planned",
      "snoozed_until": null,
      "priority": "high|medium|low",
      "subtopic": "<если из topic_sublevels>"
    }
  ],
  "meta": {
    "timezone": "Europe/Moscow",
    "weekend_mode": false,
    "total_minutes": 130,
    "language": "ru"
  }
}
```

**Изменения от старой версии:**
- `user_id: "u_local"` → `user_id: <user_key>` (НЕ хардкод)
- `goal_id: "g_<subject>"` → `g_<purpose>_<subject>` (избегает коллизий при multi-goal)
- Добавлено поле `user_key` (явное, для парсинга)
- Добавлено `goal_slug` в goal (связь с `users/<key>/plan.md`)
- Добавлено `weak_subtopics` + `level` в goal (для goal-checkin-notifier)
- Добавлены `priority` + `subtopic` в task
- Добавлена `meta` (timezone, weekend_mode, total_minutes, language)

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

**Приоритет — из `profile.notes`.** Стандартные слоты — fallback.

### Чтение `profile.notes` на временные предпочтения

| Паттерн в `notes` | Интерпретация | Слоты |
|---|---|---|
| `«утром»`, `«до обеда»`, `«до работы»` | Утренний хронотип | 07:00 / 09:00 / 11:00 |
| `«вечером»`, `«после работы»`, `«19-22»` | Вечерний хронотип | 19:00 / 20:00 / 21:00 |
| `«в выходные»`, `«по субботам»` | Субботне-воскресный режим | 11:00 / 15:00 / 19:00 |
| `«5 дней × N, 2 дня × 0»` | Будни | 18:00 / 20:00 / 22:00 (вс) / 0 в выходные |
| Конкретные часы (напр. `«в 19:30»`) | Точное время | использовать как первое окно |
| Пусто / нет паттернов | Fallback | 10:00 / 14:00 / 18:00 |

### Стандартное распределение (fallback)
- **Утро (10:00)** — теория / новая тема (когда свежая голова)
- **День (14:00)** — задачи / практика
- **Вечер (18:00)** — повторение / карточки / тест

### Weekend mode
- Если в `notes` упомянуты выходные как off → `weekend_mode: true` в JSON → 0 задач в плане (или 1 light задача ≤ 30 мин)
- Если в `notes` упомянуты выходные как on → полный план по обычным слотам
- Если не упомянуто → fallback: считать Сб/Вс как обычные дни (дневной бюджет / 7)

## Topic sublevels priority
При наличии `profile.topic_sublevels` с разными уровнями:
- Задачи на подпункты с `zero`/`weak` — **первые в очереди** + `priority: high`
- Задачи на `medium` — `priority: medium`
- Задачи на `strong`/`expert` — `priority: low` (или вообще не включать в план, если бюджет мал)

## Алгоритм ротации sublevels (при N>3 и бюджете <1 ч/день)

Если `profile.topic_sublevels` содержит > 3 подпунктов с уровнями `zero`/`weak` И `daily_hours < 1.0`:
- **Спиральный алгоритм** (покрывает все подпункты, повторяет слабые чаще):

| День недели (N от 1) | Покрытие | Пример (4 sublevels, 5 дней/нед) |
|---|---|---|
| 1 | 1, 2 | sub1 + sub2 |
| 2 | 3, 4 | sub3 + sub4 |
| 3 | 1, 2 (повторение) | sub1 + sub2 (review) |
| 4 | 3, 4 (повторение) | sub3 + sub4 (review) |
| 5 | 1, 3 (mix) | sub1 + sub3 (mix) |
| 6 (выходной) | — | — или 1 light review |
| 7 (выходной) | — | — |

**Параметры алгоритма:**
- `N_sublevels` = количество подпунктов с `zero`/`weak`
- `pairs_per_day` = `floor(daily_hours_minutes / 30)` (по 30 мин на подпункт)
- `review_cadence` = каждые 2-3 дня (для слабых подпунктов)
- Если `daily_hours < 30 мин` → только 1 подпункт в день, без пар

**Запись в `plan.md` секции «Понедельный скелет» (если это новая генерация):**
```markdown
## Ротация sublevels (день 1..7)
- День 1: <sub1>, <sub2>
- День 2: <sub3>, <sub4>
- День 3: <sub1> (review), <sub2> (review)
- ...
```

**Почему спираль, а не линейный перебор:**
- Линейный: день 1 — sub1, день 2 — sub2, ..., день 7 — sub7. Забываем sub1 на неделю. Слабые подпункты не повторяются.
- Спиральный: чередуем новые + повторения. Кривая забывания Эббингауза компенсируется.

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
