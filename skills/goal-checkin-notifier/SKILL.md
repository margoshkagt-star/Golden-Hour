---
name: "goal-checkin-notifier"
description: "Telegram goal reminders and check-ins: morning brief, weighted task pings, evening review, anti-spam throttling."
---

# Goal Check-in Notifier

Sends reminders and check-ins to a Telegram bot for the user's daily/weekly goals. Consumes the plan produced by the planning skill, prioritizes by goal weight, throttles to avoid spam.

## Workflow

1. **Load plan** for today from the location defined in `references/data-schema.md`. If empty — no notifications, exit silently.
2. **Generate schedule**:
   - Morning brief at `morning_brief_time` (default 09:00 local) — overview of today's goals and tasks.
   - Active task pings at each task's `scheduled_at`, capped at `max_pings_per_day` (default 3). If more tasks than the cap, pick by `goal_weight` desc, then by `scheduled_at` asc. Lower-weight tasks are dropped, not delayed.
   - Evening check-in at `evening_checkin_time` (default 21:00 local) — "как прошёл день?"
3. **Apply quiet hours** (default 23:00–08:00): shift any ping inside the window to the nearest edge.
4. **Send via the openclaw message action** (channel: `telegram`) using phrasings from `references/message-templates.md` and the `callback_data` convention from `references/tg-delivery.md`.
5. **Handle responses**:
   - Inline button clicks arrive in the agent session as `callback_data: goal:<action>:<task_id>`. Update task `status` (and `snoozed_until` for snooze) in the plan file accordingly.
   - Free text → log to the daily journal, let the user keep talking.
6. **Escalation** for evening check-in: if no response in 30 min, one retry. If still nothing, log "day not reviewed" and stop for the day.

## Team task notifications (`team-tasks`)

When `team-tasks.mjs` returns `notifications` with `recipients[]`, deliver each `message` to the corresponding user's Telegram chat via the same message action. Respect `exclude_user_key` if present (don't ping the actor twice). Team notifications are **not** throttled by `max_pings_per_day` — they are event-driven (invite, take, submit, approve, etc.).

## Configuration

- `morning_brief_time` — default `09:00`
- `evening_checkin_time` — default `21:00`
- `quiet_hours_start` — default `23:00`
- `quiet_hours_end` — default `08:00`
- `max_pings_per_day` — default `3`
- `telegram_chat_id` — required

## Output

- Updated plan file with task `status` and `snoozed_until` fields.
- Daily log at `users/<user_key>/plans/YYYY-MM-DD-log.md` (what was sent and what was answered).

## Open contract with the team

- Plan file location and guaranteed fields — `references/data-schema.md` is the proposed shape; confirm with the planning-skill owner.
- Whether status updates from this skill need to flow back to the goals skill, or the plan file is the single source of truth.

(Telegram delivery contract — bot identity, user ID, message action shape, callback_data format — is resolved; see `references/tg-delivery.md`.)
