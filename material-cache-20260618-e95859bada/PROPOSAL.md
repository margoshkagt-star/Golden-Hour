---
name: "material-cache"
description: "Кеш материалов в knowledge/ — не повторять research."
status: proposal
version: "v1"
date: "2026-06-18T08:40:25.834Z"
author: pending-clarification
status_source: agent-generated-2026-06-18 (per karim's request)
---

# Material Cache — material-cache

## Структура

```
knowledge/<subject>/<slug>.md    # контент с frontmatter
knowledge/<subject>/_index.md    # список slug'ов
```

## Алгоритм

1. **Lookup:** subject + topic → `knowledge/<subject>/_index.md` → hit — отдать ссылку.
2. **Miss:** `web_search` + `web_fetch` + summary.
3. **Save:** `knowledge/<subject>/<slug>.md` с frontmatter, обновить `_index.md`.
4. **Stale (>30 дней):** пометить, спросить «обновить?».
5. **Miss-кэш:** `_not-found.md` — не повторять searches.

## Связанные

- `daily-plan`, `study-plan`, `goal-planned`, `TOOLS.md` (Obsidian sync)

Подробная спецификация в `skills-library/drafts/material-cache/SKILL.md`.