---
name: "setup-finalize"
description: "Завершает онбординг: спрашивает дедлайн и часов в неделю, сохраняет полный профиль, ставит setup_status=complete и запускает построение плана. Только после самооценки."
author: pending-clarification
status_source: agent-generated-2026-06-18 (per karim's directive 2026-06-16)
---

# setup-finalize

Последний шаг настройки. Собирает оставшиеся параметры, **фиксирует профиль** и **открывает рабочий режим**.

## Триггер
- После шага самооценки любой ветки:
  - olympiad → после `olympiad-self-asses`
  - exam → после `exam-self-assess`
  - topic → после `topic-self-assess`

## Логика

1. Прочитать `users/<user_key>/profile.md` (уже заполнены: name, purpose, ветка, уровень).
2. **Спросить дедлайн:**
   ```
   📅 К какому сроку готовимся?

   Напиши месяц и год (например, «июнь 2027») — или «без дедлайна», если просто учусь.
   ```
   → `deadline: YYYY-MM | null`.
3. **Спросить время:**
   ```
   ⏱️ Сколько часов в неделю реально готов уделять?

   Например: 3, 5, 10. Можно диапазон.
   ```
   → `hours_per_week: <число>`.
4. **Записать в `profile.md`:** `deadline`, `hours_per_week`, `setup_status: complete`, обновить `updated`.
5. **Показать сводку профиля** (dry-run) и подтвердить:
   ```
   ✅ Настройка готова, <name>!

   - Цель: <purpose> — <subject/topic>
   - Уровень: <level>
   - Дедлайн: <deadline>
   - Время: <hours_per_week> ч/нед

   Строю план подготовки → дальше включаются напоминания и чек-ины.
   ```
6. **Запустить `study-plan`** (явный handoff):
   - Прочитать SKILL.md `study-plan` для актуальной процедуры.
   - **Передать в study-plan:** user_key, профиль, deadline, hours_per_week.
   - study-plan создаёт `users/<user_key>/plan.md` (НЕ `plans/<slug>.md` — это path conflict, исправлено в goal-planned).
   - Если `setup_status = complete`, но `plan.md` отсутствует — **считать setup незавершённым**, показать предупреждение: «Профиль готов, но plan.md не создан. Скажи "построить план"».
7. После плана — рабочий режим доступен (`daily-plan`, `current-tasks`, `goal-checkin-notifier`, `task-tracker`).

**Handoff setup-finalize → study-plan (формализация, исправлено 2026-06-19):**
- Раньше было: «Запустить `study-plan`» — без уточнения механизма. Сломало тест #2.
- Сейчас: setup-finalize явно говорит «прочитай SKILL.md study-plan, передай параметры, дождись создания `users/<key>/plan.md`».
- Это **внутренний handoff** в рамках одной сессии (не требует sessions_spawn — main делает сам).

## Что НЕ делает
- ❌ Не ставит `setup_status: complete`, пока нет дедлайна (или явного «без дедлайна») и часов.
- ❌ Не строит план до подтверждения сводки.
- ❌ Не включает напоминания до готового плана.

## Обработка ответов
| Ответ | Реакция |
|---|---|
| «без дедлайна» / «просто учусь» | `deadline: null`, стратегия плана — равномерная |
| Размытое время («когда как») | предложить вилку: «возьмём 3 ч/нед как базу? потом подстроим» |
| «потом настрою план» | профиль сохранить как `complete`, план отложить, но предупредить: без плана напоминания молчат |

## Данные
- `users/<user_key>/profile.md` → `deadline`, `hours_per_week`, `setup_status: complete`

## Примеры заполненного `profile.md` по веткам

### Ветка `olympiad`

```markdown
# Профиль — Тестовый ВсОШ-физик

- **user_key:** test_vsosh
- **name:** "Тестовый ВсОШ-физик"
- **channel:** webchat
- **created:** 2026-06-19
- **updated:** 2026-06-19 12:05
- **setup_status:** complete

## Цель
- **purpose:** olympiad

## Параметры
- **olympiad_grade:** 10
- **olympiad_subject:** physics
- **olympiad_levels:** {"механика": "strong", "термодинамика": "strong", "электродинамика": "weak", "оптика": "weak"}
- **olympiad_level_note:** "продвинутый, но пробелы в электродинамике (цепи, Кирхгоф) и оптике"

## Дедлайн и время
- **deadline:** 2026-12
- **hours_per_week:** 15

## Заметки
- (свободные факты)
```

### Ветка `exam`

```markdown
# Профиль — Тестовый ЕГЭ-информатик

- **user_key:** test_ege
- **name:** "Тестовый ЕГЭ-информатик"
- **channel:** webchat
- **created:** 2026-06-19
- **updated:** 2026-06-19 11:56
- **setup_status:** complete

## Цель
- **purpose:** exam

## Параметры
- **exam_type:** ege
- **exam_subject:** informatics
- **exam_subject_variant:** null
- **exam_topics:** ["Информация и её кодирование", "Логика", "Алгоритмы и программирование", "Графы и деревья", "Динамическое программирование", "Базы данных и СУБД", "Компьютерные сети", "Операционные системы"]
- **exam_topic_levels:** {"Информация и её кодирование": "weak", "Логика": "medium", "Алгоритмы и программирование": "medium", "Графы и деревья": "weak", "Динамическое программирование": "weak", "Базы данных и СУБД": "zero", "Компьютерные сети": "zero", "Операционные системы": "zero"}
- **exam_topics_source:** codifier
- **exam_level_note:** "знаю Python базово, демо-варианты на 60-65"

## Дедлайн и время
- **deadline:** 2027-06
- **hours_per_week:** 10

## Заметки
- (свободные факты)
```

### Ветка `topic`

```markdown
# Профиль — Тестовый испанский

- **user_key:** test_spanish
- **name:** "Тестовый испанский"
- **channel:** webchat
- **created:** 2026-06-19
- **updated:** 2026-06-19 12:00
- **setup_status:** complete

## Цель
- **purpose:** topic

## Параметры
- **study_topic:** "испанский язык с нуля до B1"
- **study_subject:** "испанский язык"
- **study_topic_scope:** "с нуля до B1 (CEFR) за 6 месяцев, 5 ч/нед"
- **topic_level:** zero
- **topic_sublevels:** {"чтение": "zero", "письмо": "zero", "аудирование": "zero", "говорение": "zero", "произношение": "zero", "грамматика": "zero", "лексика": "zero"}
- **topic_level_note:** "никогда не учил испанский, английский B2"

## Дедлайн и время
- **deadline:** 2026-12
- **hours_per_week:** 5

## Заметки
- Занимаюсь вечером (19:00-22:00) в будни
- В выходные не занимаюсь
```

### Ветка `topic` + `проект` (project variant)

```markdown
# Профиль — Тестовый AI-todo MVP

- **user_key:** test_ai_todo
- **name:** "Тестовый AI-todo"
- **channel:** webchat
- **created:** 2026-06-19
- **updated:** 2026-06-19 12:02
- **setup_status:** complete

## Цель
- **purpose:** topic
- **study_topic_scope:** "проект — MVP AI-todo web-app"

## Параметры
- **study_topic:** "MVP AI-todo"
- **study_subject:** "fullstack web"
- **topic_sublevels:** {"react": "strong", "uiux": "medium", "backend_node": "zero", "supabase": "zero", "postgres": "weak", "llm_api": "zero", "vercel_deploy": "weak", "env_vars": "medium"}

## Дедлайн и время
- **deadline:** 2026-08
- **hours_per_week:** 8
```

## Зависимости
- После ветки самооценки.
- Перед `study-plan` и рабочим режимом.

## Где живёт реальное исполнение
**`SOUL.md` → секция «Финал настройки»** — то, что агент реально выполняет. Этот скилл — дизайн-документ.
