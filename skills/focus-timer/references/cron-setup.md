# Cron setup for stats resets

> **Многопользовательский режим:** глобальные cron-сбросы ниже опциональны. В нашей схеме у каждого пользователя свой `users/<user_key>/focus/stats.json`, и сброс окон делается **self-healing** при следующем чтении/сессии (см. `SKILL.md` → Self-healing). Cron имеет смысл только для одного владельца или если по нему итерироваться по всем папкам `users/*`.

The focus-timer skill needs 4 cron jobs to reset the 4 windows at their boundaries. These are agentTurn crons that read `users/<user_key>/focus/stats.json` and zero out the appropriate window.

## Crons

```bash
# Daily at 00:00 local — reset 24h window
openclaw cron add \
  --name "stats-reset-24h" \
  --schedule "0 0 * * *" \
  --tz "Europe/Moscow" \
  --payload '{
    "kind": "agentTurn",
    "message": "Stats reset for 24h window. Update users/<user_key>/focus/stats.json: set windows.24h.period_start to today 00:00 local, zero out windows.24h.by_task and windows.24h.by_goal. Preserve schema_version and skill_name. Save atomically (temp file + rename). Reply in this chat with exactly one line: \"stats 24h reset\". No extra commentary, no follow-up questions."
  }'

# Monday at 00:00 local — reset week window
openclaw cron add \
  --name "stats-reset-week" \
  --schedule "0 0 * * 1" \
  --tz "Europe/Moscow" \
  --payload '{
    "kind": "agentTurn",
    "message": "Stats reset for week window. Update users/<user_key>/focus/stats.json: set windows.week.period_start to this Monday 00:00 local, zero out windows.week.by_task and windows.week.by_goal. Preserve schema_version and skill_name. Save atomically (temp file + rename). Reply in this chat with exactly one line: \"stats week reset\". No extra commentary, no follow-up questions."
  }'

# 1st of month at 00:00 local — reset month window
openclaw cron add \
  --name "stats-reset-month" \
  --schedule "0 0 1 * *" \
  --tz "Europe/Moscow" \
  --payload '{
    "kind": "agentTurn",
    "message": "Stats reset for month window. Update users/<user_key>/focus/stats.json: set windows.month.period_start to the 1st of this month 00:00 local, zero out windows.month.by_task and windows.month.by_goal. Preserve schema_version and skill_name. Save atomically (temp file + rename). Reply in this chat with exactly one line: \"stats month reset\". No extra commentary, no follow-up questions."
  }'

# Jan 1 at 00:00 local — reset year window
openclaw cron add \
  --name "stats-reset-year" \
  --schedule "0 0 1 1 *" \
  --tz "Europe/Moscow" \
  --payload '{
    "kind": "agentTurn",
    "message": "Stats reset for year window. Update users/<user_key>/focus/stats.json: set windows.year.period_start to Jan 1 00:00 local, zero out windows.year.by_task and windows.year.by_goal. Preserve schema_version and skill_name. Save atomically (temp file + rename). Reply in this chat with exactly one line: \"stats year reset\". No extra commentary, no follow-up questions."
  }'
```

## Note on `all` window

`all` is never reset — its counters accumulate indefinitely. No cron needed.

## Time zone

All reset crons use the user's local time zone. Set `tz` to the appropriate IANA name (e.g., `Europe/Moscow`).

## Schema preservation

The reset operations must preserve `schema_version` and `skill_name` at the root of `stats.json`. The cron messages above explicitly say "Preserve schema_version and skill_name" — this ensures the v1 schema stays consistent across resets.
