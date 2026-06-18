# Statistics (5 time windows)

The focus-timer skill tracks per-task and per-goal time across 5 time windows. These are the user's "5 variables" — each is a stored counter that aggregates session time and resets at its period boundary.

## Schema versioning

`users/<user_key>/focus/stats.json` includes:

- `schema_version` — current is `1`
- `skill_name` — `"focus-timer"` (so other skills can identify the file in a shared directory)

Both fields are stable. v1 readers continue to work on v1 files. Breaking changes bump `schema_version` and the v1 reader refuses to write v2 files (read-only fallback). See "Backward compatibility" at the bottom of this file.

## Windows

| Name | Aliases | Period definition | Reset trigger |
|---|---|---|---|
| `24h` | `сегодня`, `today`, `day` | Sessions ended today (local 00:00 → 23:59) | 00:00 each day |
| `week` | `неделя`, `week` | Sessions ended in current ISO week (Mon→Sun) | 00:00 each Monday |
| `month` | `месяц`, `month` | Sessions ended in current calendar month | 00:00 on 1st of month |
| `year` | `год`, `year` | Sessions ended in current calendar year | 00:00 on Jan 1 |
| `all` | `всё`, `all`, `всегда` | All sessions ever | **never** |

## File location

`users/<user_key>/focus/stats.json`

## Schema (v1)

```json
{
  "schema_version": 1,
  "skill_name": "focus-timer",
  "windows": {
    "24h": {
      "period_start": "2026-06-17T00:00:00+03:00",
      "by_task": {
        "t_phys": { "minutes": 5, "sessions": 1 }
      },
      "by_goal": {
        "g_physics": { "minutes": 5, "sessions": 1 }
      }
    },
    "week": {
      "period_start": "2026-06-15T00:00:00+03:00",
      "by_task": { "t_phys": { "minutes": 5, "sessions": 1 } },
      "by_goal": { "g_physics": { "minutes": 5, "sessions": 1 } }
    },
    "month": {
      "period_start": "2026-06-01T00:00:00+03:00",
      "by_task": { "t_phys": { "minutes": 5, "sessions": 1 } },
      "by_goal": { "g_physics": { "minutes": 5, "sessions": 1 } }
    },
    "year": {
      "period_start": "2026-01-01T00:00:00+03:00",
      "by_task": { "t_phys": { "minutes": 5, "sessions": 1 } },
      "by_goal": { "g_physics": { "minutes": 5, "sessions": 1 } }
    },
    "all": {
      "by_task": { "t_phys": { "minutes": 5, "sessions": 1 } },
      "by_goal": { "g_physics": { "minutes": 5, "sessions": 1 } }
    }
  }
}
```

## Update on session end

When a session ends, the skill:

1. For each of the 4 reset windows (`24h`, `week`, `month`, `year`):
   - If `session.ended_at >= window.period_start` → increment `by_task[task_id]` and `by_goal[goal_id]` by `session.duration_minutes` and `1`
   - If `session.ended_at < window.period_start` → window has expired; do not increment (next session or stats query will trigger self-healing)
2. For `all` window: always increment

## Reset at boundaries (cron-driven)

Each reset window is zeroed by a cron at its boundary. Cron definitions are in `references/cron-setup.md`. The `all` window has no reset cron.

## Self-healing

If a reset cron is missed (e.g., gateway was down at 00:00):

- **Next session end:** the session's `ended_at` will be in the new period; the skill detects the stale `period_start` and recomputes the window from `users/<user_key>/focus/sessions.json.history` (filtering sessions to the current period) before incrementing.
- **Next stats query:** similar — stale `period_start` triggers a recompute.

This keeps stats accurate even after a missed reset.

---

## Cross-skill contract

Other skills (e.g., weekly-review, goal-progress, smart-planner) can interact with `users/<user_key>/focus/stats.json` and `users/<user_key>/focus/sessions.json` under these rules.

### ✅ Other skills MAY

- **Read** `stats.json` and `sessions.json` at any time (read-only)
- Use the values for their own reports, summaries, planning, etc.
- Compute their own derived metrics (per-day, per-weekday, per-time-of-day, etc.) by iterating `sessions.json.history`
- Use the `skill_name` field to identify the producer of a file
- Check `schema_version` to know which fields are guaranteed

### ❌ Other skills MUST NOT

- **Write** to `stats.json` (only `focus-timer` writes; concurrent writes from other skills will corrupt counters)
- **Mutate** `period_start` (this is the focus-timer's internal state)
- **Delete or prune** entries from `sessions.json.history` (the focus-timer manages its own cleanup)
- **Assume `period_start` is always accurate** — it can be stale if a reset cron was missed. For guaranteed-fresh boundaries, compute your own cutoff (`now - 24h`, etc.) and filter `sessions.json.history` directly

### 📋 Stable fields in `stats.json` (safe to depend on in v1.x)

- `schema_version` — integer
- `skill_name` — string
- `windows.<name>.period_start` — ISO-8601 timestamp string (only for `24h`, `week`, `month`, `year`; `all` has no `period_start`)
- `windows.<name>.by_task` — `{ task_id: { minutes: int, sessions: int } }`
- `windows.<name>.by_goal` — `{ goal_id: { minutes: int, sessions: int } }`

### ⚙️ Internal fields (may change without notice)

- Any field not listed above
- File location (path is stable, but can be relocated by config)

### Backward compatibility

If the schema needs to change in a non-backward-compatible way:

1. Bump `schema_version` (v1 → v2)
2. v1 readers continue to work on v1 files (read-only fallback when reading v2)
3. v2 readers convert v1 files on load and write v2
4. New fields can be added in minor versions without bumping (v1.0 → v1.1)
5. Document the migration here

This way, adding `schema_version: 1` to existing files is forward-compatible: v1 readers continue to work, future v2 readers know what they're getting.

---

## Example queries for other skills

### Weekly review skill

Read week-level stats and the corresponding plan:

```python
import json
from pathlib import Path
from datetime import datetime

# Read focus-timer stats
stats = json.loads(Path('users/<user_key>/focus/stats.json').read_text())

# Verify schema before reading
assert stats['schema_version'] == 1, f"Unsupported stats schema: {stats['schema_version']}"
assert stats['skill_name'] == 'focus-timer'

# Week stats
week_start = stats['windows']['week']['period_start']
goal_minutes = stats['windows']['week']['by_goal']

# Read this week's plan
monday_date = datetime.fromisoformat(week_start).date()
plan = json.loads(Path(f'users/<user_key>/plans/{monday_date.isoformat()}.json').read_text())

# Build report
for goal in plan['goals']:
    goal_id = goal['id']
    minutes_done = goal_minutes.get(goal_id, {}).get('minutes', 0)
    print(f"{goal['title']}: {minutes_done} min this week")
```

### Goal progress skill

For a specific goal, show time spent in each window:

```python
goal_id = 'g_physics'
for window_name in ['24h', 'week', 'month', 'year', 'all']:
    minutes = stats['windows'][window_name]['by_goal'].get(goal_id, {}).get('minutes', 0)
    sessions = stats['windows'][window_name]['by_goal'].get(goal_id, {}).get('sessions', 0)
    print(f"{window_name}: {minutes} min ({sessions} sessions)")
```

### Smart planner skill

Use historical session durations to suggest `est_minutes` for new tasks:

```python
# For a new task, find similar past tasks by substring match
sessions = json.loads(Path('users/<user_key>/focus/sessions.json').read_text())
new_task_title = 'Решить задачи по алгебре'
keyword = new_task_title.split()[0]
similar = [s for s in sessions['history'] if keyword in s['task_title']]
if similar:
    avg = sum(s['duration_minutes'] for s in similar) / len(similar)
    print(f"Suggested est_minutes: {avg:.0f}")
else:
    print("No similar past tasks; default to 60 min")
```

### Self-healing for other skills (when they need accurate boundaries)

If you need a guaranteed-fresh boundary (not relying on `period_start` which can be stale):

```python
from datetime import datetime, timedelta

sessions = json.loads(Path('users/<user_key>/focus/sessions.json').read_text())
now = datetime.now()
week_start = now - timedelta(days=now.weekday())  # Monday 00:00
week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

week_minutes = sum(
    s['duration_minutes']
    for s in sessions['history']
    if s.get('ended_at') and datetime.fromisoformat(s['ended_at']) >= week_start
)
print(f"This week so far: {week_minutes} min")
```

This is more robust than reading `period_start` directly.

---

## Output format

When user asks for stats, reply with a structured message.

### All windows summary

```
📊 Статистика фокус-сессий

За 24 часа: 5 мин (1 сессия)
За неделю: 5 мин (1 сессия)
За месяц: 5 мин (1 сессия)
За год: 5 мин (1 сессия)
За всё время: 5 мин (1 сессия)

Топ задач за всё время:
1. Подготовка по физике — 5 мин (1 сессия)
```

### Specific window

```
📊 Статистика за неделю

Всего: 5 мин (1 сессия)

По задачам:
1. Подготовка по физике — 5 мин (1 сессия)

По целям:
1. Подготовка к физике — 5 мин (1 сессия)
```

### Specific goal (across all windows)

```
📊 Статистика по цели "Подготовка к физике"

За 24 часа: 5 мин
За неделю: 5 мин
За месяц: 5 мин
За год: 5 мин
За всё время: 5 мин
```

## Time zone

All "today/this week/etc." boundaries are in the user's local time zone (from `agents.defaults` config or environment).

## Implementation note

The skill stores counters for fast lookups. Self-healing on the next session or stats query ensures correctness even after missed resets.
