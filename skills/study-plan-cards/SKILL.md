---
name: "study-plan-cards"
description: "Визуальный слой учебного плана: cover + недельные карточки в PNG (light/dark). 3 режима: from-plan-file, from-state, from-topics. Рендер: HTML+Edge headless через cards/render.js."
---

# study-plan-cards

Превращает структурированный план в набор визуальных карточек — **обложка + по одной на каждую неделю/блок**, лайт и тёмная темы. Удобно для отправки в мессенджер, печати, шаринга. Mobile-формат 1080×1440.

## Триггеры
- «сделай карточки по плану», «расписание в картинках»
- «/cards», «/plan-cards»
- «карточка прогресса», «карточка за неделю»
- «раскидай темы по неделям в карточки»

## Что делает

1. **Определить источник** — один из трёх режимов:
   - `from-plan-file` — `cards/plan.json` или `plans/<period>.json` (от `daily-plan`)
   - `from-state` — `state/tasks.yaml` (от `task-tracker`/`longterm-stats`)
   - `from-topics` — `users/<user_key>/profile.md` → `exam_topics[]` (от `exam-topics`)
2. **Запустить рендер** через `scripts/render.js`:
   ```bash
   node skills/study-plan-cards/scripts/render.js \
        --mode=<mode> [--source=<path>] [--themes=light,dark] [--output-dir=cards/]
   ```
3. **Получить PNG-альбом** в `cards/*.png` (cover + week1..N в каждой теме).
4. **Отправить** в текущий чат через `message(action="send", attachments=[...])`.
5. **Опционально**:
   - `note-to-file` → прикрепить PNG в `memory/YYYY-MM-DD.md`
   - `task-tracker`/`longterm-stats` → сохранить в Obsidian дашборд

## Структура CardPlan (единый внутренний формат)

```json
{
  "cover": {
    "title": "...", "subtitle": "...", "target": "...",
    "date_from": "DD.MM", "date_to": "DD.MM", "deadline": "DD.MM.YYYY",
    "days_total": 26, "hours_per_day": 3, "hours_total": 78,
    "footer": "..."
  },
  "weeks": [
    {
      "label": "НЕДЕЛЯ 1", "title": "22–28 июня",
      "subtitle": "Производная + Уравнения", "footer": "...",
      "days": [
        { "date": "22.06", "weekday": "Пн", "task": "№12", "topic": "..." }
      ]
    }
  ]
}
```

## Стыковка с другими скиллами

### ↑ Вход (от кого берём)

| Скилл | Что подхватываем |
|---|---|
| `daily-plan` | `users/<user_key>/plans/YYYY-MM-DD.json` — цели+задачи на сегодня. Для недельной карточки — собираем за 7 дней или берём `cards/plan.json`. |
| `study-plan` | `users/<user_key>/plan.md` — учебный план пользователя. |
| `task-tracker` | `state/tasks.yaml` → `tasks[]`. Фильтр `task_type=long` или `deadline > today+7д`. |
| `longterm-stats` | Сводный `period_progress_weight/hours` → в обложку как «сколько сделано». |
| `exam-topics` | `users/<user_key>/profile.md` → `exam_topics[]` + `exam_subject`, `deadline`, `daily_hours`. |
| `goal-materials` | `materials/<goal_id>/` → подсказка «📚 материалов: N» в строках карточки. |

### ↓ Выход (кому отдаём)

| Скилл | Что отдаём |
|---|---|
| `goal-checkin-notifier` | PNG-альбом → Telegram как morning brief |
| `daily-study-checkin` | Карточка дня/недели для отчёта |
| `task-tracker` | `progress_<period>.png` → Obsidian дашборд |
| `longterm-stats` | Недельная/месячная карточка как отчёт |
| `note-to-file` | PNG → `memory/YYYY-MM-DD.md` |
| `focus-timer` | Обложка с дедлайном (TODO v2 — кнопки) |

### Цепочка (happy path)

```
profile.md (exam_topics) ──┐
                           ├─► daily-plan ──► plans/*.json ──┐
plan.md (учебный план) ────┘                                  │
                                                              ▼
                                                study-plan-cards
                                                          │
                                              ┌───────────┼───────────┐
                                              ▼           ▼           ▼
profile.md (topics) ──► exam-topics ───┐   node render.js (zero deps, HTML+Edge headless)
state/tasks.yaml ──► task-tracker ─────┤           │
                                          ▼           ▼
                                  cards/*.png (альбом)
                                          │
                ┌─────────────────────────┼─────────────────────────┐
                ▼                         ▼                         ▼
   goal-checkin-notifier            note-to-file            longterm-stats
                │                         │                         │
                ▼                         ▼                         ▼
            Telegram              memory/YYYY-MM-DD.md           Obsidian
```

## Зависимости

- **`scripts/render.js`** — Node.js, zero deps, лежит рядом.
- **Edge или Chrome** на хосте:
  - Windows: `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`
  - Прочие ОС: `/usr/bin/google-chrome` или `chromium` (через ENV `EDGE_BIN`)
- **Node 14+**

## CLI

```bash
# Из готового CardPlan JSON
node skills/study-plan-cards/scripts/render.js --mode=from-plan-file --source=cards/plan.json

# Из state/tasks.yaml (прогресс-карточки)
node skills/study-plan-cards/scripts/render.js --mode=from-state --source=state/tasks.yaml --themes=light,dark

# Из exam_topics в profile.md
node skills/study-plan-cards/scripts/render.js --mode=from-topics --themes=dark

# Только обложка
node skills/study-plan-cards/scripts/render.js --mode=from-plan-file --no-weeks

# Кастомная палитра (переопределить первую)
node skills/study-plan-cards/scripts/render.js --palette='#FF6B6B,#FFE3E3,#2C2C2C'
```

## Палитры (зашиты в render.js)

1. **зелёная** — `#2E7D32` / `#E8F5E9`, dark `#4CAF50` / `#0E1A12`
2. **оранжевая** — `#E65100` / `#FFF3E0`, dark `#FF9800` / `#1F140A`
3. **сиреневая** — `#6A1B9A` / `#F3E5F5`, dark `#BA68C8` / `#170F1F`
4. **синяя** — `#1565C0` / `#E3F2FD`, dark `#64B5F6` / `#0E1626`

Если недель > 4 — палитры повторяются по кругу.

## Workflow для агента

1. Получить запрос на карточки → определить режим (по источнику)
2. Положить/обновить `cards/plan.json` (или передать `--source=...`)
3. `exec("node skills/study-plan-cards/scripts/render.js --mode=...")` → `cards/*.png`
4. `message(action="send", attachments=[...])` альбомом в текущий чат
5. Опц.: `note-to-file` / `task-tracker` / `longterm-stats`

## Lessons learned

- Edge headless требует **уникальный `--user-data-dir`** на каждый вызов — иначе второй и далее процессы падают.
- AI image-gen (`minimax/image-01`) ломает кириллицу → для русского текста использовать HTML+Edge headless.
- Telegram принимает альбомы до 10 фото одним сообщением через `attachments[]`.

## Адаптации (TODO v2)
- [ ] Темы через ENV (`THEME=dark`)
- [ ] Альбомная ориентация для печати
- [ ] Кнопки в Telegram (`[Начать день]`, `[Открыть задачи]`)
- [ ] QR-код на обложке (ссылка на Notion/Obsidian)
- [ ] Локализация `en` / `ru`
- [ ] Шрифты из Google Fonts
