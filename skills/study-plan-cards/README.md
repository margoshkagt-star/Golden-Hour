# study-plan-cards

> Оркестратор PNG-карточек (1080×1440) для учебных планов и статистики. Точка входа для агента в [Golden Hour](https://github.com/margoshkagt-star/Golden-Hour).

Рендер делегируется в соседний скилл **`study-cards`** (`skills/study-cards/`).

![cover](examples/cover_dark.png)

## Структура

```
skills/study-plan-cards/
├── SKILL.md              # логика агента, триггеры, режимы
├── scripts/render.js     # thin orchestrator → study-cards
├── examples/
│   ├── plan.json         # демо CardPlan (ЕГЭ математика)
│   ├── cover_dark.png    # обложка
│   ├── week1_dark.png …  # недельные таблицы
│   ├── tasks.example.yaml
│   └── …
├── README.md
├── proposal.json
└── LICENSE
```

## Быстрый старт

```bash
cd skills/study-plan-cards

# План → PNG (dark)
npm run plan

# Статистика из tasks.yaml
npm run stats

# План + статистика
npm run full
```

Или напрямую:

```bash
node scripts/render.js \
  --mode=from-plan-file \
  --source=examples/plan.json \
  --output-dir=examples \
  --themes=dark
```

**Требования:** Node.js 14+, Microsoft Edge или Chrome (headless).

## Режимы

| `--mode` | Источник | Движок |
|---|---|---|
| `from-plan-file` | `plan.json` | `study-cards/render.js` |
| `from-topics` | CardPlan от exam-topics | `study-cards/render.js` |
| `from-state` | `tasks.yaml` | `study-cards/render-stats.js` |
| `full` | plan + tasks | оба скрипта |

## CardPlan

Единый JSON-формат между скиллами. См. `examples/plan.json` и `SKILL.md`.

## См. также

- [`../study-cards/`](../study-cards/) — render engine
- [`SKILL.md`](SKILL.md) — полная документация для агента
