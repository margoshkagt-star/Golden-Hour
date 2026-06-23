# Pomodoro data schema

The skill is stateless beyond a small set of JSON state files plus append-only logs.

## File locations

**Golden Hour (per-user):** `users/<user_key>/pomodoro/`

- Active session: `users/<user_key>/pomodoro/session.json`
- Transition log: `users/<user_key>/pomodoro/log/YYYY-MM-DD.jsonl`
- DND log: `users/<user_key>/pomodoro/log/YYYY-MM-DD-dnd.jsonl`
- Suggestion log: `users/<user_key>/pomodoro/log/YYYY-MM-DD-suggestions.jsonl`
- Daily summary: `users/<user_key>/pomodoro/summary/YYYY-MM-DD.json`
- **Suggestion state:** `users/<user_key>/pomodoro/suggestions.json`
- Statistics: `users/<user_key>/pomodoro/stats.json`
- Pending schedule: `users/<user_key>/pomodoro/schedule-pending.json`

*(Upstream skill also documents `~/.openclaw/pomodoro/` for single-user agents — в этом воркспейсе только per-user.)*

План для lookup: `users/<user_key>/plans/YYYY-MM-DD.json` — поля `tasks[].title`, `scheduled_at`, `est_minutes`, `status`.

## Active session state

```json
{
  "schema": "openclaw.pomodoro.session.v1",
  "variant": "classic",
  "phase": "work",
  "phase_started_at": "2026-06-22T10:00:00+03:00",
  "phase_duration_minutes": 25,
  "cycles_done": 2,
  "long_break_every": 4,
  "work_minutes": 25,
  "break_minutes": 5,
  "long_break_minutes": 15,
  "started_at": "2026-06-22T10:00:00+03:00",
  "chat_id": "12345678",
  "deferred_count": 0,
  "dialog_opened": true
}
```

`phase` is one of `"work"`, `"break"`, `"long_break"`, `"stopped"`.

`variant` is one of `"classic"` (25/5), `"long"` (50/10), `"extended"` (100/20), `"short"` (15/3), or `"custom"`. For `variant: "custom"`, the `work_minutes` and `break_minutes` fields hold the user-supplied values (within bounds 1–240 / 1–60). `variant` does NOT embed the durations — read them from `work_minutes` / `break_minutes` regardless of variant.

`dialog_opened` is `false` until the first inbound message from this `chat_id` is seen, then `true` permanently for the chat.

When no session is active the file either does not exist or contains:

```json
{ "schema": "openclaw.pomodoro.session.v1", "phase": "stopped", "ended_at": "..." }
```

Writes are atomic: write to `session.json.tmp`, then rename. The tick always reads, never holds the file open.

## Transition log (one JSON object per line)

```json
{"ts": "2026-06-22T10:25:01+03:00", "from": "work", "to": "break", "cycles_done": 1, "deferred": false}
{"ts": "2026-06-22T10:30:02+03:00", "from": "break", "to": "work", "cycles_done": 1, "deferred": false}
{"ts": "2026-06-22T10:55:03+03:00", "from": "work", "to": "long_break", "cycles_done": 4, "deferred": true}
```

`deferred: true` means the notification was held back due to quiet hours and was sent at the next edge.

## Suggestion state (durable rate-limit counter)

The proactive-suggestion workflow (SKILL.md step 8) writes this file each time a suggestion is sent. The file is the source of truth for the "at most one per day" cap.

```json
{
  "schema": "openclaw.pomodoro.suggestions.v1",
  "chat_id": "12345678",
  "last_suggestion_date": "2026-06-22",
  "last_suggestion_at": "2026-06-22T14:35:00+03:00",
  "last_suggestion_converted": false,
  "total_sent_today": 1,
  "total_sent_all_time": 7
}
```

- `last_suggestion_date` is the LOCAL calendar date (`YYYY-MM-DD`) of the most recent suggestion sent to this `chat_id`. The cap is enforced by computing `today_local = current local date` and aborting if `today_local == last_suggestion_date`.
- `total_sent_today` is a redundant counter maintained for audit; the date comparison is the actual gate.
- `total_sent_all_time` is a lifetime counter, useful for tuning.
- `last_suggestion_converted` is `true` if the user started a session within 2 hours of the most recent suggestion. Cosmetic only; the cap is still spent.

Writes are atomic: `suggestions.json.tmp` → rename. If the file does not exist, treat as "no suggestion sent today" and allow the first one.

Per-day per-chat history of suggestion ATTEMPTS (not just sends) lives in `log/YYYY-MM-DD-suggestions.jsonl`:

```json
{"ts": "2026-06-22T14:30:00+03:00", "chat_id": "12345678", "fired": true, "reason": "sent", "converted_within_2h": false}
{"ts": "2026-06-22T16:00:00+03:00", "chat_id": "12345678", "fired": false, "reason": "cap_hit"}
{"ts": "2026-06-22T18:30:00+03:00", "chat_id": "12345678", "fired": false, "reason": "session_active"}
{"ts": "2026-06-22T20:00:00+03:00", "chat_id": "12345678", "fired": false, "reason": "quiet_hours"}
{"ts": "2026-06-22T22:00:00+03:00", "chat_id": "12345678", "fired": false, "reason": "plan_ok"}
```

`reason` values:

- `sent` — suggestion was sent.
- `cap_hit` — `last_suggestion_date == today`, blocked.
- `session_active` — `session.json.phase ∈ {work, break, long_break}`, blocked.
- `quiet_hours` — current local time is inside the quiet-hours window, blocked.
- `plan_ok` — the plan-behind signal did not fire (no overdue tasks, completion rate above threshold, or too early in the day), no suggestion needed.
- `disabled` — `proactive_suggestions_enabled: false`, blocked.
- `no_plan` — plan file is missing or malformed, silent skip.

## Daily summary (written at session-end)

```json
{
  "schema": "openclaw.pomodoro.summary.v1",
  "date": "2026-06-22",
  "variant": "classic",
  "cycles_completed": 6,
  "work_minutes": 150,
  "break_minutes": 25,
  "long_break_minutes": 15,
  "deferred_count": 1,
  "suggestion_sent_today": 1,
  "suggestion_converted_today": 1,
  "started_at": "2026-06-22T10:00:00+03:00",
  "ended_at": "2026-06-22T12:40:11+03:00",
  "ended_reason": "user_stopped"
}
```

`ended_reason` is one of `"user_stopped"`, `"drift_recovered"`, `"midnight_rollover"`.

The `suggestion_sent_today` / `suggestion_converted_today` fields give a quick read on whether the proactive suggestion actually helps the user.


## Statistics state (cumulative work time)

The work-time statistics file is written every time a work block ends — normal completion, partial skip, partial stop, or drift recovery. It is the durable record of how much time the user has actually spent in pomodoro work blocks, and it is the file other skills (e.g. `longterm-stats`) may READ.

File: `~/.openclaw/pomodoro/stats.json` (path configurable via `stats_file`).

```json
{
  "schema": "openclaw.pomodoro.stats.v1",
  "chat_id": "12345678",
  "total_work_minutes_all_time": 750,
  "total_cycles_all_time": 30,
  "total_work_minutes_by_date": {
    "2026-06-22": 75,
    "2026-06-21": 150,
    "2026-06-20": 25
  },
  "total_cycles_by_date": {
    "2026-06-22": 3,
    "2026-06-21": 6,
    "2026-06-20": 1
  },
  "first_credit_at": "2026-06-15T10:00:00+03:00",
  "last_credit_at": "2026-06-22T14:30:00+03:00",
  "last_updated": "2026-06-22T14:30:00+03:00"
}
```

- `total_work_minutes_all_time` — lifetime sum of credited work minutes.
- `total_cycles_all_time` — lifetime count of completed work blocks (one per work-phase → break transition, regardless of whether the credit was partial or full).
- `total_work_minutes_by_date` — keyed by local-time `YYYY-MM-DD`. The `today` lookup uses the same local date as the suggestions cap. Entries are never deleted; the per-date map grows indefinitely (pruning is an external concern, not the pomodoro skill's job).
- `total_cycles_by_date` — same shape, cycle counts per local date.
- `first_credit_at` / `last_credit_at` — ISO-8601 timestamps, useful for debugging and for "you started tracking N days ago" UI.
- `last_updated` — timestamp of the most recent write.

### Credit rules (workflow step 9)

| Exit condition | Credit for the work block |
|---|---|
| Normal completion (`elapsed >= planned work_minutes`) | `planned work_minutes` |
| `/pomodoro skip` mid-work | `min(planned work_minutes, ceil((now - phase_started_at) / 60_000))` |
| `/pomodoro stop` mid-work | same as skip |
| Drift recovery (multiple phases late) | `planned work_minutes` (one block, no backfill) |

The `stats_credit_on_skip` config controls the skip/stop rule:
- `actual_elapsed_capped` (default) — partial credit for actual elapsed time, capped at planned.
- `planned_full` — always credit the planned amount, even on skip.
- `none` — no credit on skip, only on full completion.

Drift recovery always uses `planned_full` regardless of `stats_credit_on_skip` — the work block was not "skipped" by the user, it was completed without a tick firing in time.

### Per-day stats audit log

Every credit is also appended to `log/YYYY-MM-DD-stats.jsonl`:

```json
{"ts": "2026-06-22T10:25:01+03:00", "chat_id": "12345678", "variant": "classic", "credited_minutes": 25, "planned_minutes": 25, "elapsed_minutes": 25, "reason": "completed"}
{"ts": "2026-06-22T11:00:00+03:00", "chat_id": "12345678", "variant": "classic", "credited_minutes": 12, "planned_minutes": 25, "elapsed_minutes": 12, "reason": "skipped_partial"}
```

`reason` values: `completed`, `skipped_partial`, `stopped_partial`, `drift_recovered`. The audit log is append-only and is the source of truth if `stats.json` ever needs to be reconstructed (e.g. after corruption or a roll-back).

### Other skills reading this file

`pomodoro` is the canonical WRITER of `stats.json`. Other skills (`longterm-stats`, dashboards, etc.) should READ but should not WRITE — concurrent writes from multiple skills will corrupt the per-date maps. If a consumer needs to add its own counters, it should maintain a separate file and merge at display time.


## Scheduled session state (extends `session.json`)

When a session is started via the scheduled-session flow (SKILL.md step 10), the active state file gets additional fields. The fields are absent (or `null`) for immediate sessions started via `/pomodoro start`.

```json
{
  "schema": "openclaw.pomodoro.session.v1",
  "mode": "scheduled",
  "variant": "classic",
  "phase": "work",
  "phase_started_at": "2026-06-22T15:00:00+03:00",
  "phase_duration_minutes": 25,
  "scheduled_blocks": [
    { "phase": "work",      "start_at": "2026-06-22T15:00:00+03:00", "duration_minutes": 25 },
    { "phase": "break",     "start_at": "2026-06-22T15:25:00+03:00", "duration_minutes": 5 },
    { "phase": "work",      "start_at": "2026-06-22T15:30:00+03:00", "duration_minutes": 25 },
    { "phase": "break",     "start_at": "2026-06-22T15:55:00+03:00", "duration_minutes": 5 },
    { "phase": "work",      "start_at": "2026-06-22T16:00:00+03:00", "duration_minutes": 25 },
    { "phase": "break",     "start_at": "2026-06-22T16:25:00+03:00", "duration_minutes": 5 },
    { "phase": "work",      "start_at": "2026-06-22T16:30:00+03:00", "duration_minutes": 25 },
    { "phase": "break",     "start_at": "2026-06-22T16:55:00+03:00", "duration_minutes": 5 }
  ],
  "scheduled_block_index": 0,
  "window_start_at": "2026-06-22T15:00:00+03:00",
  "window_end_at": "2026-06-22T17:00:00+03:00",
  "window_topic": "физика",
  "window_source": "plan",
  "cycles_done": 0,
  "long_break_every": 4,
  "work_minutes": 25,
  "break_minutes": 5,
  "long_break_minutes": 15,
  "started_at": "2026-06-22T15:00:00+03:00",
  "chat_id": "12345678",
  "deferred_count": 0,
  "dialog_opened": true
}
```

- `mode` is `"scheduled"` for time-windowed sessions, `null` or absent for immediate sessions.
- `scheduled_blocks` is the full frozen sequence generated at confirmation time. The tick loop reads this array and uses `scheduled_block_index` to know which block is current. When the current block ends, `scheduled_block_index` advances. When the index reaches the end of the array AND `now >= window_end_at`, the session ends with `ended_reason: "window_complete"`.
- `window_start_at` and `window_end_at` are ISO-8601 timestamps defining the user's window. The session may not extend past `window_end_at` (unless `window_end_action: finish_phase` is set and the current block is in progress).
- `window_topic` is the plan task name (or user-provided free text).
- `window_source` is `"plan"` if the window came from the plan lookup, `"user"` if the user provided it explicitly, `"duration"` if the user used the `2h` shorthand.
- The tick loop logic for scheduled sessions is: read `scheduled_blocks[scheduled_block_index]`, compute `elapsed = now - block.start_at`, when `elapsed >= block.duration_minutes * 60_000`, advance to `scheduled_blocks[scheduled_block_index + 1]` and write the new state.

### Drift recovery for scheduled sessions

If a tick is missed and `now` is past multiple block boundaries:
- If `now >= window_end_at` — end the session cleanly.
- Otherwise, advance `scheduled_block_index` to the latest block whose `start_at + duration_minutes * 60_000 <= now`.
- Do NOT run blocks whose `start_at` is in the past (they are silently dropped).
- Stats credit the planned work minutes for the block that was active when the missed-tick gap was detected (no backfill).

## Pending schedule proposal (transient state)

When the user requests a scheduled session, the skill generates a proposal and holds it in a transient state file until the user confirms, edits, or cancels. The proposal auto-expires.

File: `~/.openclaw/pomodoro/schedule-pending.json`

```json
{
  "schema": "openclaw.pomodoro.schedule-pending.v1",
  "chat_id": "12345678",
  "proposal_id": "prop-2026-06-22T15:00:00-abc123",
  "created_at": "2026-06-22T14:55:00+03:00",
  "expires_at": "2026-06-22T15:25:00+03:00",
  "window_start_at": "2026-06-22T15:00:00+03:00",
  "window_end_at": "2026-06-22T17:00:00+03:00",
  "window_topic": "физика",
  "window_source": "plan",
  "variant": "classic",
  "scheduled_blocks": [
    { "phase": "work",  "start_at": "...", "duration_minutes": 25 },
    { "phase": "break", "start_at": "...", "duration_minutes": 5 }
  ]
}
```

- `proposal_id` is a unique ID used in inline button callback_data and in the audit log.
- `expires_at` = `created_at + schedule_proposal_ttl_minutes`. After this, the proposal is silently dropped — no session starts.
- Only one pending proposal per `chat_id` is allowed. If the user requests another `/pomodoro schedule` while a proposal is pending, the previous proposal is replaced (the old one is logged as `superseded` in the schedule log).
- The proposal is deleted when: (a) the user confirms (the proposal's data is copied into `session.json` and the file is removed); (b) the user cancels (file is removed, `schedule-cancelled` template sent); (c) the proposal expires (file is removed silently).

## Per-day schedule audit log

One row per schedule proposal and confirmation, appended to `log/YYYY-MM-DD-schedule.jsonl`:

```json
{"ts": "2026-06-22T14:55:00+03:00", "chat_id": "12345678", "proposal_id": "prop-...", "event": "proposed", "variant": "classic", "window_start": "15:00", "window_end": "17:00", "topic": "физика", "window_source": "plan", "block_count": 8}
{"ts": "2026-06-22T14:56:00+03:00", "chat_id": "12345678", "proposal_id": "prop-...", "event": "confirmed"}
{"ts": "2026-06-22T14:57:00+03:00", "chat_id": "12345678", "proposal_id": "prop-...", "event": "cancelled", "reason": "user"}
{"ts": "2026-06-22T15:00:00+03:00", "chat_id": "12345678", "proposal_id": "prop-...", "event": "superseded"}
{"ts": "2026-06-22T15:25:00+03:00", "chat_id": "12345678", "proposal_id": "prop-...", "event": "expired"}
```

`event` values: `proposed`, `confirmed`, `cancelled`, `superseded`, `expired`. This log is the source of truth for "did the user see the proposal", "did they confirm", "did the proposal ever get started late" — useful for tuning the suggestion flow.