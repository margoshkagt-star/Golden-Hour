---
name: "study-plan-cards"
description: "Orchestrator for visual study cards: picks source (plan/state/topics/full), builds CardPlan, delegates to study-cards engine, sends Telegram album."
---

# study-plan-cards — orchestrator

**Точка входа для агента.** Превращает план/статистику/темы в PNG-альбом. Сам не рисует — делегирует рендер в **`study-cards`**.

## Связка с study-cards

| Шаг | Кто | Что |
|---|---|---|
| 1 | `study-plan-cards` | Определить режим, собрать/найти CardPlan или путь к `tasks.yaml` |
| 2 | `study-plan-cards` | `exec node skills/study-plan-cards/scripts/render.js --mode=...` |
| 3 | `study-cards` | `render.js` или `render-stats.js` → PNG в `--output-dir` |
| 4 | `study-plan-cards` | `message(send, attachments=[...])` альбомом (≤10) |

```
┌─────────────────────────────────────────────────────────────┐
│  study-plan-cards (SKILL — логика агента)                   │
│  • триггеры, CardPlan, выбор режима                         │
│  • scripts/render.js — thin orchestrator                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ exec
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  study-cards (render engine)                                │
│  • render.js        → cover + weekN (из plan.json)         │
│  • render-stats.js  → stats_* (из tasks.yaml)              │
└──────────────────────────┬──────────────────────────────────┘
                           │ PNG
                           ▼
              goal-checkin-notifier / Telegram / note-to-file
```

## Триггеры

- «сделай карточки по плану», «расписание в картинках»
- «/cards», «/plan-cards»
- «карточка прогресса», «статистика картинками»
- «раскидай темы по неделям в карточки»
- «план + прогресс картинками» → режим `full`

## Режимы

| `--mode` | Источник | Движок study-cards | Когда |
|---|---|---|---|
| `from-plan-file` | `cards/plan.json` или `--source=` | `render.js` | Готовый CardPlan от `study-plan` / `daily-plan` |
| `from-topics` | CardPlan из `exam-topics` + `profile.md` | `render.js` | Агент собрал JSON из `exam_topics[]`, положил в `cards/plan.json` |
| `from-state` | `state/tasks.yaml` | `render-stats.js` | Прогресс, дедлайны, категории |
| `full` | plan + tasks | оба скрипта | «Всё сразу»: обложка плана + недели + статистика |

## CLI (оркестратор)

```bash
# План из JSON
node skills/study-plan-cards/scripts/render.js \
  --mode=from-plan-file --source=cards/plan.json --output-dir=cards/ --themes=dark

# Статистика из трекера
node skills/study-plan-cards/scripts/render.js \
  --mode=from-state --source=users/<user_key>/state/tasks.yaml --output-dir=cards/

# Темы → сначала агент пишет CardPlan, потом:
node skills/study-plan-cards/scripts/render.js \
  --mode=from-topics --source=cards/plan.json --output-dir=cards/

# План + статистика в одну папку
node skills/study-plan-cards/scripts/render.js \
  --mode=full \
  --plan-source=cards/plan.json \
  --stats-source=users/<user_key>/state/tasks.yaml \
  --output-dir=cards/ --themes=dark
```

Общие флаги: `--output-dir=` (default: `cards/`), `--themes=light,dark`, `--no-weeks` (только cover, plan-режимы).

## CardPlan (единый формат между скиллами)

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

Схема общая для `study-plan-cards` (сборка) и `study-cards/render.js` (рендер). Пример: `study-cards/examples/plan.example.json`.

## Workflow для агента

1. **Распознать запрос** → выбрать `--mode`
2. **Подготовить данные**:
   - `from-plan-file`: скопировать/сгенерировать `cards/plan.json`
   - `from-topics`: прочитать `profile.md` → `exam_topics[]` → собрать CardPlan → `cards/plan.json`
   - `from-state`: путь к `tasks.yaml` (ничего конвертировать не нужно)
   - `full`: CardPlan + `tasks.yaml`
3. **Рендер**: `exec("node skills/study-plan-cards/scripts/render.js --mode=... --output-dir=cards/")`
4. **Собрать альбом** из `cards/*_dark.png`:
   - `full`: `cover_dark` → `week1_dark`… → `stats_cover_dark` → `stats_deadlines_dark` → `stats_cats_dark`
   - ≤ 10 файлов; если больше — два альбома (план отдельно, stats отдельно)
5. **Отправить**: `message(action="send", attachments=[...])`
6. **Опционально**: `note-to-file`, `longterm-stats` (Obsidian), `goal-checkin-notifier` (утренний бриф)

## Стыковка с другими скиллами

### ↑ Вход

| Скилл | Что подхватываем | Режим |
|---|---|---|
| `study-plan` | `users/<user_key>/plan.md` → CardPlan | `from-plan-file` |
| `daily-plan` | `plans/YYYY-MM-DD.json` → недельный CardPlan | `from-plan-file` |
| `exam-topics` | `profile.md` → `exam_topics[]` | `from-topics` |
| `task-tracker` | `state/tasks.yaml` | `from-state` или `full` |
| `longterm-stats` | сводка → в обложку stats | `from-state` |
| `goal-materials` | счётчик материалов в topic-строках | `from-topics` |

### ↓ Выход

| Скилл | Что отдаём |
|---|---|
| `goal-checkin-notifier` | PNG-альбом в Telegram |
| `daily-study-checkin` | карточка недели/дня |
| `longterm-stats` | `progress_*.png` |
| `note-to-file` | PNG в `memory/YYYY-MM-DD.md` |

## Цепочка (happy path)

```
profile.md + exam-topics ──► CardPlan (cards/plan.json)
daily-plan / study-plan ────┘
                                    │
                                    ▼
                          study-plan-cards (mode)
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
         study-cards/render.js          study-cards/render-stats.js
                    │                               │
                    └─────────── cards/*.png ───────┘
                                    │
                    goal-checkin-notifier → Telegram
```

## Lessons learned

- Не дублировать рендер — только `study-cards/`; orchestrator в `study-plan-cards/scripts/render.js`
- Edge headless: уникальный `--user-data-dir` на каждый скриншот
- Кириллица: HTML+Edge, не AI image-gen
- Telegram: альбом ≤ 10 фото

## Таблицы в Telegram (`table-cards`)

Любая markdown-таблица в ответе → **не текстом**, а PNG через тот же движок `study-cards`:

```bash
node scripts/table-cards.mjs --user <user_key> --title "План на сегодня" --text "| col | ..."
```

## См. также

- **`study-cards/SKILL.md`** — CLI движка, форматы, manifest JSON
- **`study-cards/README.md`** — установка standalone, палитры, примеры
