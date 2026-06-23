---
name: "study-cards"
description: "Render engine: PNG 1080×1440 for study plans, task stats, and tables (built-in dark theme). Called by study-plan-cards and table-cards.mjs."
---

# Study Cards — render engine

**Низкоуровневый движок рендера.** Не вызывай напрямую из диалога, если пользователь просит «карточки по плану» — сначала **`study-plan-cards`** (он выберет режим, соберёт CardPlan и вызовет этот скилл).

## Роль в связке

| Скилл | Роль |
|---|---|
| **`study-plan-cards`** | Оркестратор: триггеры, источники данных, CardPlan, доставка в Telegram |
| **`study-cards`** (этот) | Движок: `render.js`, `render-stats.js`, `render-table.js` → PNG |

**Стиль:** одна встроенная тёмная тема (`lib/palette.js` → `DEFAULT_THEME = dark`). Без выбора в профиле.

```
daily-plan / study-plan / exam-topics / task-tracker
                    │
                    ▼
           study-plan-cards  ──exec──►  study-cards/render.js
                    │                   study-cards/render-stats.js
                    ▼
              cards/*.png  ──►  goal-checkin-notifier / Telegram
```

## Скрипты

### `render.js` — план (cover + недели)

```bash
node skills/study-cards/render.js \
  --source=cards/plan.json \
  --output-dir=cards/ \
  --themes=dark
```

Флаги:
- `--source=` — CardPlan JSON (default: `plan.json` рядом со скриптом)
- `--output-dir=` — куда писать PNG/HTML (default: каталог скрипта)
- `--themes=dark` — встроенная тема (default, единственная в golden-hour)
- `--no-weeks` — только обложка

Выход: `cover_dark.png`, `weekN_dark.png`

### `render-table.js` — произвольная таблица

```bash
node skills/study-cards/render-table.js \
  --source=table.json \
  --output-dir=cards/tables/ \
  --name=table-0.png
```

JSON: `{ title, subtitle?, headers[], rows[][] }`. Вызывается из `scripts/table-cards.mjs`.

### `render-stats.js` — статистика (task-tracker)

```bash
node skills/study-cards/render-stats.js \
  --source=users/<user_key>/state/tasks.yaml \
  --output-dir=cards/ \
  --themes=dark
```

Выход: `stats_cover_*`, `stats_deadlines_*`, `stats_cats_*`

## Форматы

- **CardPlan** (`plan.json`): см. `examples/plan.example.json` и раздел в `study-plan-cards/SKILL.md`
- **tasks.yaml**: см. `examples/tasks.example.yaml` — совместимо с `task-tracker`

## Требования

- Node.js **14+**
- Edge (Windows) или Chrome/Chromium — переопределить через `EDGE_BIN`

## Контракт вывода

В конце каждый скрипт печатает JSON-строку с manifest:

```json
{"kind":"plan","outputDir":"...","files":["cover_dark.png","week1_dark.png"]}
```

`study-plan-cards` использует её для сборки альбома Telegram.

## Связанные скиллы

- **`study-plan-cards`** — единственная точка входа для агента
- `study-plan`, `daily-plan`, `exam-topics` — источники CardPlan
- `task-tracker`, `longterm-stats` — источник `tasks.yaml`
