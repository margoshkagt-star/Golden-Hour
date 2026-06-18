# Storage schema

## Frontmatter (каждый материал)

```yaml
---
id: m_<8chars>
goal_id: g_<...>
type: problem | theory | link | file | note
tags: [тег1, тег2]
status: new | working | stuck | understood | archived
source: user | web_search
source_url: <url>
file_path: <path>
created_at: <ISO8601>
updated_at: <ISO8601>
status_history:
  - { status: new, at: <ISO8601> }
  - { status: working, at: <ISO8601> }
---
```

## index.json

```json
{
  "schema_version": 1,
  "by_id": {
    "m_a1b2c3d4": {
      "goal_id": "g_ege_math_profile",
      "type": "problem",
      "tags": ["параметры"],
      "status": "new",
      "path": "users/<user_key>/materials/g_ege_math_profile/problems/2026-06-18_parametry.md",
      "created_at": "2026-06-18T11:59:00+03:00",
      "updated_at": "2026-06-18T11:59:00+03:00"
    }
  }
}
```

Всё хранится в папке пользователя: `users/<user_key>/materials/index.json`. Перестраивается командой «пересобери индекс материалов».

## Отражение в прогрессе

При смене статуса материала на `understood` / `stuck` / `archived` дописывается строка в `users/<user_key>/progress.md`:

```
- HH:MM  ✓ [goal_id] m_<id> → understood
- HH:MM  ❌ [goal_id] m_<id> → stuck
- HH:MM  🗑 [goal_id] m_<id> → archived
```

(Отдельного глобального inbox больше нет — всё личное, в папке пользователя.)