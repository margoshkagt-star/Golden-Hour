# State storage

The skill persists state across two files under the workspace. Both files include a `schema_version` and `skill_name` for cross-skill discoverability and compatibility.

## File locations

- `users/<user_key>/focus/sessions.json` — current and historical sessions
- `users/<user_key>/focus/stats.json` — 5-window stats (24h, week, month, year, all)

## Schema versioning

Both files include:

- `schema_version` — current is `1`
- `skill_name` — `"focus-timer"` (so other skills can identify the producer of a file in a shared directory)

If a breaking change is needed:

1. Bump `schema_version` to `2`
2. v1 readers refuse to write v2 files (read-only fallback)
3. v2 readers convert v1 files on load and write v2
4. Document the migration in `references/statistics.md` and `references/state-storage.md`

## `sessions.json` schema (v1)

```json
{
  "schema_version": 1,
  "skill_name": "focus-timer",
  "current": {
    "session_id": "s_20260617_1430",
    "task_id": "t_phys",
    "goal_id": "g_physics",
    "task_title": "Сессия по физике",
    "started_at": "2026-06-17T14:30:00+03:00",
    "paused_at": null,
    "accumulated_seconds": 0,
    "planned_duration_minutes": 60
  },
  "history": [
    {
      "session_id": "s_20260616_2115",
      "task_id": "t_mvp_doc",
      "goal_id": "g_mvp",
      "task_title": "Написать ТЗ для планировщика",
      "started_at": "2026-06-16T21:15:00+03:00",
      "ended_at": "2026-06-16T22:05:00+03:00",
      "duration_minutes": 50,
      "planned_duration_minutes": 50,
      "end_reason": "user_stop"
    }
  ]
}
```

## `stats.json` schema (v1)

See `references/statistics.md` for the full schema and cross-skill contract.

## `end_reason` values (in `sessions.json`)

- `user_stop` — user pressed `стоп` manually (time is logged, but task NOT marked done)
- `timer_expiry_confirmed` — timer expired AND user pressed `[Засчитать]`
- `timer_expiry_continued` — timer expired, user pressed `[Ещё!]`, this entry is the finished segment
- `gateway_restart` — active session was interrupted by a gateway restart (treat as paused)

## Backward compatibility

- **Adding fields** to existing JSON objects: backward-compatible. v1 readers ignore unknown fields.
- **Adding new values to `end_reason`**: backward-compatible. v1 readers log as "unknown" but don't crash.
- **Removing fields**: BREAKING. Bump `schema_version` and provide migration.
- **Renaming fields**: BREAKING. Bump `schema_version` and provide migration.
- **Changing field types**: BREAKING. Bump `schema_version` and provide migration.

## Atomic writes

Both files use temp-file + rename for writes to avoid corruption if the gateway restarts mid-write.

## Cleanup

`history` in `sessions.json` older than 90 days can be pruned; the skill should not retain more than 500 historical sessions in active state. Sessions for recurring tasks (like daily physics) accumulate in history — each is a separate entry.

Stats are NEVER pruned from `stats.json` — the `all` window accumulates indefinitely.

## Cross-skill access (sessions.json)

Other skills can READ `sessions.json` freely. The contract is identical to `stats.json` (see `references/statistics.md`).
