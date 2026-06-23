---
name: "pomodoro"
description: "Telegram Pomodoro technique timer with classic/long/extended/short variants and custom user-supplied durations, phase-transition notifications, automatic work-time statistics accumulation, do-not-disturb mode during active sessions, proactive once-per-day suggestions when the user falls behind on their plan, time-windowed scheduled sessions driven by the user's plan, and crash-safe session state."
---

# Pomodoro

Pomodoro technique timer delivered through Telegram. Cycles between work blocks and breaks, sends a notification at every phase transition, persists state to disk so a session survives restarts, supports classic/long/extended/short variants and user-defined custom durations, automatically accumulates the work portion of every pomodoro into a durable statistics file, stays silent on non-pomodoro topics while a session is running, — at most once a day — gently suggests trying a pomodoro when the user is behind on their plan, and can start a **scheduled session** in a time window pulled from the user's plan (with confirmation and on-the-fly editing).

## Workflow

1. **Start an immediate session** on command `/pomodoro start [variant_or_custom]`. Built-in variants:
   - `classic` (default): 25 min work / 5 min break
   - `long`: 50 min work / 10 min break
   - `extended`: 1h40m (100 min) work / 20 min break — for deep-focus blocks
   - `short`: 15 min work / 3 min break
   - `custom`: user-supplied — `/pomodoro start custom <work_min> <break_min>` (e.g. `custom 30 60`). Bounds: work 1–240 min, break 1–60 min.
   - Shorthand: `/pomodoro start <work_min>/<break_min>` is also accepted as a custom variant (e.g. `start 30/60` → work 30, break 60). Same bounds apply.
   - On invalid custom values (out of bounds, malformed, non-integer, missing), reply with the `custom-invalid` template and do not start.

   On start: verify the user has already opened a dialog with the bot (see step 7 — `telegram-warmup`). If not, send the warmup template and refuse to start. Once warmup is satisfied, write the state file `~/.openclaw/pomodoro/session.json` with `phase: "work"`, `phase_started_at: <now>`, `cycles_done: 0`, the variant's durations, and `long_break_every: 4`. Send the work-start notification. For custom variants, the `work_minutes` and `break_minutes` fields hold the custom values; `variant` is `"custom"`.

2. **Tick loop.** Every `tick_interval_seconds` (default 60) a tick reads `session.json`, computes `elapsed_ms = now - phase_started_at`. When `elapsed_ms >= phase_duration_minutes * 60_000`:
   - If current `phase` is `work`: advance to `break`, or to `long_break` when `cycles_done + 1` is a multiple of `long_break_every` (i.e. after the 4th, 8th, ... work block). Increment `cycles_done` when leaving a work block. Send the matching break notification. **Accumulate the work-portion statistics** (see step 9).
   - If current `phase` is `break` or `long_break`: advance back to `work`. Long break counts as a break for cycle purposes — the counter resets naturally on the next work block.
   - Write the new state (new `phase`, new `phase_started_at: now`, updated `cycles_done`).
   - Append a row to the per-day transition log.

   Tick mechanism: prefer the OpenClaw scheduler (cron-style) running `openclaw skill run pomodoro --action tick` once a minute while a session is active. If no scheduler integration exists, the main agent self-polls `session.json` once per minute when a session is open. Either is acceptable — the state file is the single source of truth. No runtime script is embedded.

3. **Slash commands** (parsed from incoming Telegram messages):
   - `/pomodoro start [variant]` — begin an immediate session with a built-in variant (`classic`, `long`, `extended`, `short`); if one already exists, reply "сессия уже идёт, {cycles_done} циклов" and ignore.
   - `/pomodoro start custom <work_min> <break_min>` — begin a custom-durations session. Validates against bounds (work 1–240 min, break 1–60 min). On invalid, replies with the `custom-invalid` template and does not start.
   - `/pomodoro start <work_min>/<break_min>` — shorthand for `custom <work> <break>`. Same bounds.
   - `/pomodoro schedule <from>-<to> [variant] [topic]` — see step 10. Begin a scheduled session in a time window pulled from the user's plan or given explicitly. Confirm before starting.
   - `/pomodoro schedule plan` — see step 10. Use the current/next plan block as the window. No explicit time needed.
   - `/pomodoro status` — reply with current phase, time remaining, `cycles_done`. Inline buttons `[Пропустить фазу]` `[Завершить сессию]`.
   - `/pomodoro skip` — advance the current phase immediately, send the next-phase notification. If the skipped phase was `work`, accumulate the partial-work statistics (see step 9) BEFORE advancing — actual elapsed minutes, capped at planned `work_minutes`.
   - `/pomodoro stop` — end the session: write `phase: "stopped"`, `ended_at: now`, send the session-end template with final `cycles_done` and total `work_minutes` sum. Accumulate the in-progress work block (if any) into statistics BEFORE marking stopped — same credit rule as `/pomodoro skip`.
   - `/pomodoro stats` — reply with the `stats-daily` template: today's work minutes, today's cycle count, all-time work minutes, all-time cycle count.

4. **Inline button callbacks** (format `pomodoro:<action>`):
   - `pomodoro:skip` — same as `/pomodoro skip`.
   - `pomodoro:stop` — same as `/pomodoro stop`.
   - `pomodoro:schedule:confirm` — confirm the proposed schedule (step 10).
   - `pomodoro:schedule:edit` — ask the user for a new window.
   - `pomodoro:schedule:cancel` — cancel the schedule proposal, no session started.
   - `pomodoro:window:end` — end the session now (5 min before `window_end_at`, when `window_end_action: ask`).
   - `pomodoro:window:finish` — let the current phase finish, then stop.
   - `pomodoro:window:extend` — extend the window by 15 min, regenerate the schedule.

5. **Drift recovery.** On every tick, if `now - phase_started_at` is already past the next transition by more than one full phase, do not backfill multiple notifications — log a warning, send the appropriate next-phase notification once, and resume ticking. The timer catches up without spamming. The work-portion statistics still credit only the planned `work_minutes` for that block — no backfill multipliers, no double-counting.

6. **Do-not-disturb during an active session.** Every inbound message is filtered against `session.json.phase` before any other handling:
   - If `phase` is `stopped` (no active session) — handle normally; full chat.
   - If `phase` is one of `work`, `break`, `long_break`:
     - **Pomodoro-relevant input** (`/pomodoro …` slash command, or a `pomodoro:<action>` callback, or an inline button press from a pomodoro notification) — handle per the matching command above.
     - **Anything else** — free text, another bot's slash command, a question about a different topic (e.g. "что сегодня в работе?", "погода?", "напомни купить хлеб"), a joke, a link — reply exactly once with the `dnd-off-topic` template, then DROP the message. Do not parse it, do not call other skills, do not append to journals, do not summarise the user's question. The session is in focus mode; the user is busy; engaging would defeat the technique.
   - The DND filter runs **before** any other skill hook, every time, no exceptions. Quiet hours do not relax DND — DND applies whenever a session is active, full stop.

7. **Telegram dialog warm-up.** Telegram only delivers bot messages to a user who has opened a dialog with the bot (i.e. sent at least one message to the bot, typically `/start`). If the user has not done this yet, every `message action` call to them silently fails — no error, no delivery, no notification. To prevent the user from starting a pomodoro and then never receiving the work-start / break-start pings, the skill tracks a `dialog_opened` flag:
   - On the first inbound message of any kind, the skill flips `dialog_opened: true` in the state file (no template needed — the user's `/start` or any other message already opened the dialog server-side).
   - On `/pomodoro start`, if `dialog_opened` is `false` AND no inbound message has ever been seen from this `telegram_chat_id`, send the `telegram-warmup` template and refuse to start. The user is asked to send `/start` (or any message) and retry.
   - After the first inbound message, `dialog_opened` is `true` and the warmup check passes. All subsequent `message action` calls deliver normally.
   - This flag is stored in the state file and is never reset to `false` for the same `chat_id`.

8. **Proactive suggestion when the plan is behind (rate-limited).** The skill may send a single, low-pressure nudge to try a pomodoro when the user appears to be falling behind on their plan. This is the ONLY outbound messaging the skill does that is not driven by an active session or a direct user command. The rules are strict:
   - **Hard cap: at most ONE suggestion per local calendar day per `chat_id`.** This is a hard limit, not a soft preference. A suggestion sent today blocks any further suggestion until 00:00 local time tomorrow. The cap is enforced in `~/.openclaw/pomodoro/suggestions.json` (see `references/data-schema.md` → "Suggestion state"). The check is `today > last_suggestion_date` in local time.
   - **Trigger: plan-behind signal.** The skill reads plan state from the location agreed with the planning-skill owner (see "Open contract → Plan-behind signal source"). A "plan is behind" condition is any of: (a) at least one task scheduled for today is overdue by more than `plan_behind_overdue_minutes` (default 60) and not `done`; (b) overall completion rate for today's tasks is below `plan_behind_completion_threshold` (default 0.4) and it is past `plan_behind_check_after` (default 14:00 local). If no plan file exists, the trigger is silently skipped — the user simply hasn't set up a plan, no error, no suggestion.
   - **Never during an active session.** Suggestions are suppressed when `session.json.phase ∈ {work, break, long_break}`. DND protects the active focus.
   - **Never in quiet hours.** Suggestions are not sent inside the quiet-hours window; the next check outside the window may fire.
   - **Quoting is fine, name-dropping isn't.** The suggestion template (`plan-behind-suggestion`) MAY mention the day or general theme (e.g. "план на сегодня отстаёт"). It MUST NOT shame, list specific missed tasks, or pressure. It's a nudge, not a status report.
   - **Cap is a cap, not a quota.** If the user has been suggested today, the skill does NOT suggest again even if the user falls further behind or starts a session and stops early. The day is spent.
   - **When a suggestion converts.** If the user runs `/pomodoro start …` within 2 hours of receiving the suggestion, the suggestion is recorded as `converted: true` in the daily summary log (cosmetic — does not un-spend the cap).
   - **Opt-out.** Set `proactive_suggestions_enabled: false` to never receive a suggestion. The cap state is still maintained for audit.

9. **Work-time statistics accumulation.** Every time the user finishes (or partially skips) a work block, the work portion is added to a durable statistics file. The credit rule:
   - **Normal completion (work phase ends because `elapsed >= phase_duration_minutes`).** Credit = the planned `work_minutes` for the active variant. The work block is treated as fully done.
   - **Skip mid-phase (`/pomodoro skip` while in `work`).** Credit = `min(planned work_minutes, ceil((now - phase_started_at) / 60_000))`. Partial credit for partial work, capped at the planned amount.
   - **Stop mid-phase (`/pomodoro stop` while in `work`).** Same rule as skip — credit partial work.
   - **Drift recovery past multiple phases.** Credit only the planned `work_minutes` for the work block that was active when drift recovery fired. No backfill, no multipliers.
   - The credit is computed at the moment of the transition, BEFORE the new phase is written, so the credit is always tied to a specific work block (no double-counting if the tick loop fires twice for any reason).
   - Stats are written to `~/.openclaw/pomodoro/stats.json` (see `references/data-schema.md` → "Statistics state"). Atomic write via `stats.json.tmp` → rename.
   - The default `stats_file` path can be overridden to point at a shared statistics file used by other skills (see "Open contract → Statistics integration").
   - When `stats_enabled: false`, the entire read/write is skipped — the work-portion data is silently dropped.
   - The stats file is queryable via the `/pomodoro stats` command (uses the `stats-daily` template).

10. **Scheduled session (time-windowed pomodoro from the plan).** The user can ask to work in a time window (e.g. "поработаем с 15 до 17", "помодоро на 2 часа", or just "поработаем"), and the skill will:
    - Find a time window — from the user's plan (default) or from the user's explicit input.
    - Generate a sequence of (work, break, work, break, ...) blocks that fits the window, using the chosen variant.
    - **Ask the user to confirm or edit** the proposed schedule BEFORE starting. The user always sees the schedule and gets a chance to change it.
    - On confirmation, start a "scheduled" session that runs the blocks in order and auto-ends at the window boundary.

    **Triggering the flow**:
    - **Explicit command** — `/pomodoro schedule <from>-<to> [variant] [topic]` (e.g. `/pomodoro schedule 15:00-17:00 long физика`).
    - **Explicit command, duration shorthand** — `/pomodoro schedule 2h [variant] [topic]` (start now, end in 2 hours).
    - **Explicit command, plan-driven** — `/pomodoro schedule plan [variant]`. The skill reads the current/next plan block and uses it as the window. No explicit time needed.
    - **Implicit intent** — if `auto_schedule_from_plan: true` (default), free-text utterances like "поработаем", "давай поработаем", "помодоро на 2 часа" are routed by the agent to step 10. The intent is a soft heuristic; the confirmation step prevents accidental starts.
    - **No active session gate** — the flow is only entered when no session is active. If `session.json.phase ∈ {work, break, long_break}`, the DND filter applies; implicit intent is suppressed, explicit commands get a "сессия уже идёт" reply.

    **Plan lookup** (when window not given explicitly):
    - Read today's plan from the location agreed with the planning-skill owner (see "Open contract → Plan-behind signal source" — same file as step 8).
    - Find the **current** block: a task with `now >= scheduled_at AND now < scheduled_at + duration` and `status != done`. Use its `[scheduled_at, scheduled_at + duration]` as the window. Use its `name` as the topic.
    - If no current block, find the **next** block: smallest `scheduled_at > now` and `status != done`. Use `[scheduled_at, scheduled_at + duration]`. Topic = its `name`.
    - If no block at all, send `schedule-no-plan` template and ask the user to specify a window explicitly.
    - The plan file is read-only; pomodoro never modifies it.

    **Schedule generation** (deterministic, fits the window exactly):
    - The window is **the plan block's exact boundaries**: `[plan.scheduled_at, plan.scheduled_at + duration]`. The session covers this entire span, regardless of when the user is asking. Drift recovery handles late starts. The header in the schedule-proposal shows the actual window (which equals the plan block).
    - Given a window `[from, to]` and a variant, compute the sequence of (work, break, work, break, ...) blocks. Each block is a `(start_at, duration_minutes, phase)` tuple. **The last block ends at or before `to`; the schedule's total span equals the window's span** — no gap, no overshoot, no early end.
    - The variant's `work_minutes` and `break_minutes` (or `long_break_minutes` every `long_break_every` cycles) drive the sequence. Default `long_break_every = 4`.
    - **The trailing-break rule (the bug fix):** a break that ends at exactly `to` IS included — it is not 'past' the window. Use `block_end <= to`, never `block_end < to` for the inclusion check. The last element of the schedule is whatever block (work or break) lands on `to`. This means a 2-hour window with `classic` (25/5) produces **4 work + 4 short breaks** (the last break ends at exactly 17:00), not 4 work + 3 short breaks (which would end at 16:55 with a 5-min gap).
    - **Long break strategy** (configured by `scheduled_long_break_strategy`):
      - `shrink` (default) — if a long break would exceed the window, shrink it so the session still ends exactly at `to`.
      - `drop` — replace the long break with a short break; the long break is skipped.
      - `keep_and_truncate` — keep the long break at full duration, shorten the preceding work block to make room.
    - **Last block label** — the '(shortened)' suffix is shown ONLY when the block's actual duration is strictly less than the variant's planned duration for that block type (e.g. a 3-min break when `variant.break_minutes = 5`). A break at full `variant.break_minutes` is NOT labeled as shortened, even if it is the trailing block.
    - **Worked example** — for the plan block 15:00–17:00 with `classic` (25/5, no long break in 2h):
      - Work 1: 15:00–15:25 (25 min)
      - Break 1: 15:25–15:30 (5 min)
      - Work 2: 15:30–15:55 (25 min)
      - Break 2: 15:55–16:00 (5 min)
      - Work 3: 16:00–16:25 (25 min)
      - Break 3: 16:25–16:30 (5 min)
      - Work 4: 16:30–16:55 (25 min)
      - Break 4: 16:55–17:00 (5 min) — last block, no '(shortened)' label
      - Total: 4 work (100 min) + 4 short breaks (20 min) = 120 min. Last block ends at `to`. OK
    - **Window too small** — if the window can't accommodate at least one work block of `schedule_min_work_minutes` (default 5 min), send `schedule-too-short` template and do not start.
    - **Window too short for chosen variant** — if the window is smaller than the variant's minimum cycle (e.g. `classic` needs 30 min for one full cycle), suggest a shorter variant in the error reply.
    - The full sequence is written to `scheduled_blocks` in the state file at confirmation time. Subsequent ticks read this sequence; they do NOT regenerate it.

    **Confirmation flow** (the user always sees and approves the schedule before it starts):
    - On `/pomodoro schedule` (any form), reply with the `schedule-proposal` template: time window, topic (if from plan), full sequence of (start time, phase, duration) lines, totals (work minutes, break minutes, cycles).
    - Inline buttons: `[Подтвердить] [Изменить] [Отмена]`. callback_data: `pomodoro:schedule:confirm`, `pomodoro:schedule:edit`, `pomodoro:schedule:cancel`.
    - If the user clicks `Изменить` (or types "изменить" / "поменяй"), reply asking for the new window. The user can give a new time range, a new duration, or a new variant. Regenerate the schedule and re-confirm.
    - If the user clicks `Подтвердить` (or types "да" / "ок" / "погнали" / "go"), start the session.
    - If the user clicks `Отмена` (or types "отмена" / "нет"), reply with `schedule-cancelled` template, do not start.
    - The proposal is held in a transient state file `~/.openclaw/pomodoro/schedule-pending.json` (auto-expires after `schedule_proposal_ttl_minutes`, default 30). If the user doesn't respond, the proposal is silently dropped — no session starts.

    **Session shape (scheduled mode)**:
    - The state file's `mode` field is `"scheduled"`. (Immediate sessions have `mode: null` or absent.)
    - `scheduled_blocks`: array of `{phase: "work" | "break" | "long_break", start_at: ISO-8601, duration_minutes: int}` — the full frozen schedule.
    - `window_end_at`: ISO-8601 timestamp — the end of the user's window. The session auto-stops when the tick reaches this.
    - `window_topic`: free text, defaults to the plan task name.
    - The tick loop reads `scheduled_blocks` to know which block is current. When `now >= current_block.start_at + current_block.duration_minutes * 60_000`, it transitions to the next block in the array.
    - When the last block in `scheduled_blocks` ends AND `now >= window_end_at`, the session ends cleanly: send `window-end` template, write `phase: "stopped"`, `ended_at: now`, `ended_reason: "window_complete"`. Stats are accumulated for all completed work blocks; partial credit for an in-progress work block at window end.
    - Drift recovery for scheduled sessions: if a tick is missed and the current block has fully elapsed, advance to the next block. Do NOT run blocks whose `start_at` is in the past (they are silently skipped). Stats still credit the planned work minutes for the active block.
    - The user can `/pomodoro skip` (advance to the next block in the sequence, credit partial work) or `/pomodoro stop` (end the session early, all blocks from "current" onward are dropped, stats credit the completed work).
    - Quiet hours: phase transitions inside the window still advance on schedule, but notifications are deferred to the next edge (same rule as immediate sessions).
    - DND: applies to scheduled sessions identically — non-pomodoro messages during `work`/`break`/`long_break` are dropped with the `dnd-off-topic` template.

    **`window_end_action`** (configured):
    - `stop` (default) — when the window ends, stop the session cleanly. The session does not extend.
    - `finish_phase` — let the current block complete before stopping. The session may overshoot the window by up to one full block duration.
    - `ask` — 5 minutes before `window_end_at`, send `window-end-soon` template with buttons `[Завершить] [Дать дойти] [Продлить]`. `Продлить` adds 15 min to `window_end_at` and regenerates the remaining schedule.

    **Intent recognition is agent-side, not skill-side.** The skill describes what a "schedule request" looks like (proposed template, the lookup logic, the confirmation flow). The agent decides which user utterances count as schedule requests. False positives are mitigated by the explicit confirmation step — the user always sees and approves the schedule.


## Configuration

- `variants` — `classic` (25/5), `long` (50/10), `extended` (100/20), `short` (15/3). Default: `classic`. `custom` is accepted at start time, not a named variant in this list.
- `long_break_every` — default `4` cycles.
- `long_break_minutes` — default `15`.
- `tick_interval_seconds` — default `60`.
- `quiet_hours_start` / `quiet_hours_end` — default `23:00` / `08:00`. When a phase transition would fire inside quiet hours, the state advances on schedule but the notification is deferred to the next edge; the log row gets `deferred: true`. DND is independent of quiet hours. Suggestions are also suppressed in this window. Scheduled sessions also respect quiet hours for notifications (but the session itself continues to advance).
- `telegram_chat_id` — required. Same owner bot as `goal-checkin-notifier`.
- `dnd_during_session` — default `true`. When true, the workflow step 6 filter is active. Set to `false` only if you want the bot to keep chatting on other topics while a pomodoro runs (not recommended — defeats the technique).
- `dnd_off_topic_template` — default `dnd-off-topic` (see `references/message-templates.md`).
- `telegram_warmup_template` — default `telegram-warmup` (see `references/message-templates.md`).
- `custom_work_min_minutes` — default `1`. Lower bound for custom work block.
- `custom_work_max_minutes` — default `240` (4 hours). Upper bound for custom work block.
- `custom_break_min_minutes` — default `1`. Lower bound for custom break.
- `custom_break_max_minutes` — default `60` (1 hour). Upper bound for custom break.
- `proactive_suggestions_enabled` — default `true`. When `false`, the workflow step 8 trigger is fully disabled. The cap state is still maintained for audit.
- `suggestion_max_per_day` — default `1`. **Hard cap** on suggestions per chat per local calendar day. Setting this above `1` violates the user-facing contract — keep it at `1` unless the team explicitly approves a higher cadence.
- `plan_behind_check_interval_minutes` — default `120` (2 hours). How often the proactive-suggestion check runs. The check is also triggered opportunistically on inbound messages that are not DND-suppressed.
- `plan_behind_overdue_minutes` — default `60`. A task scheduled for today and not `done` after this many minutes past its `scheduled_at` counts as overdue.
- `plan_behind_completion_threshold` — default `0.4`. If today's completion rate is below this and it is past `plan_behind_check_after`, the plan is considered behind.
- `plan_behind_check_after` — default `14:00` local. The completion-rate check is only evaluated after this time; earlier in the day it's too early to call the day "behind".
- `plan_behind_signal_source` — location of the plan file (default: the location agreed with the planning-skill owner, e.g. `~/.openclaw/plans/YYYY-MM-DD.json` — see Open contract).
- `stats_enabled` — default `true`. When `false`, the workflow step 9 statistics accumulation is fully disabled. The `/pomodoro stats` command still works and reads the (unchanging) stats file.
- `stats_file` — default `~/.openclaw/pomodoro/stats.json`. Override to point at a shared file if other skills (e.g. `longterm-stats`) need to read or write to the same statistics.
- `stats_credit_on_skip` — default `actual_elapsed_capped`. One of: `actual_elapsed_capped` (credit min(planned, elapsed) — recommended), `planned_full` (always credit the planned amount, even on skip — strict), `none` (no credit on skip, only on full completion). Drift recovery always uses `planned_full` regardless.

- `auto_schedule_from_plan` — default `true`. When true, the agent routes implicit intent ("поработаем", "помодоро на 2 часа", etc.) to the scheduled-session flow (step 10). When false, the user must use the explicit `/pomodoro schedule` command.
- `scheduled_long_break_strategy` — default `shrink`. One of: `shrink` (shrink the long break to fit the window), `drop` (replace with a short break, no long break), `keep_and_truncate` (keep long break, shorten preceding work block).
- `schedule_min_work_minutes` — default `5`. Minimum work block duration in a scheduled session. If the window can't accommodate at least this many minutes of work, the `schedule-too-short` template is sent.
- `schedule_topic_from_plan` — default `true`. When true, the topic is pulled from the plan task name. When false, the topic is empty or user-provided.
- `window_end_action` — default `stop`. One of: `stop` (end at window end), `finish_phase` (let current block finish), `ask` (send `window-end-soon` 5 min before end with buttons).
- `schedule_proposal_ttl_minutes` — default `30`. How long a pending schedule proposal stays valid. After this, the proposal is silently dropped.


## Output

- Active state: `~/.openclaw/pomodoro/session.json` (atomic write via temp + rename). Fields now include `dialog_opened: bool`, `mode: "scheduled" | null`, `scheduled_blocks: [...]`, `window_end_at: ISO-8601`, `window_topic: string`.
- Per-day transition log: `~/.openclaw/pomodoro/log/YYYY-MM-DD.jsonl` (one JSON object per line: `ts`, `from`, `to`, `cycles_done`, `deferred`).
- Per-day summary: `~/.openclaw/pomodoro/summary/YYYY-MM-DD.json` written at session-end with totals (cycles, work_minutes, break_minutes, long_break_minutes, deferred_count).
- Per-day DND log: `~/.openclaw/pomodoro/log/YYYY-MM-DD-dnd.jsonl` — one row per suppressed off-topic message (`ts`, `chat_id`, `message_kind`, `first_60_chars`). Used to spot abuse or misconfiguration, not surfaced to the user.
- Suggestion state: `~/.openclaw/pomodoro/suggestions.json` — durable counter for the once-per-day suggestion cap (see `references/data-schema.md` → "Suggestion state"). Written atomically each time a suggestion is sent.
- Per-day suggestion log: `~/.openclaw/pomodoro/log/YYYY-MM-DD-suggestions.jsonl` — one row per suggestion attempt (`ts`, `chat_id`, `fired: bool`, `reason: "cap_hit" | "session_active" | "quiet_hours" | "plan_ok" | "sent" | "disabled"`, `converted_within_2h: bool`). Used for audit and tuning the trigger thresholds.
- Statistics: `~/.openclaw/pomodoro/stats.json` — cumulative work time + per-date breakdown (see `references/data-schema.md` → "Statistics state"). Written atomically every time a work block ends (normal, skip, or stop). This is the file other skills (e.g. `longterm-stats`) may read.
- Per-day stats log: `~/.openclaw/pomodoro/log/YYYY-MM-DD-stats.jsonl` — one row per work-block credit (`ts`, `chat_id`, `variant`, `credited_minutes`, `planned_minutes`, `elapsed_minutes`, `reason: "completed" | "skipped_partial" | "stopped_partial" | "drift_recovered"`). Used for audit and credit-rule tuning.
- **Pending schedule proposal: `~/.openclaw/pomodoro/schedule-pending.json`** — transient state for the in-flight confirmation. Auto-expires after `schedule_proposal_ttl_minutes`.
- Per-day schedule log: `~/.openclaw/pomodoro/log/YYYY-MM-DD-schedule.jsonl` — one row per schedule proposal and confirmation (`ts`, `chat_id`, `proposed_blocks`, `confirmed: bool`, `topic`, `used_window_from_plan: bool`).


## Open contract

- **Tick scheduling.** The exact tick mechanism (OpenClaw scheduler trigger vs main-agent self-poll) is open — confirm with the platform team. Either is acceptable; `session.json` is the source of truth in both cases.
- **Quiet hours coordination.** Both `pomodoro` and `goal-checkin-notifier` use the same quiet-hours window. They share the configuration; if `goal-checkin-notifier` introduces per-goal overrides later, this skill should consume the same shared setting. DND is independent — it is bound to session phase, not the wall clock. Suggestions are also quiet-hours-suppressed. Scheduled sessions respect quiet hours for notifications only; the session itself continues to advance on schedule.
- **Channel identity.** Same owner Telegram bot as `goal-checkin-notifier` (`channels.telegram.allowFrom` + `capabilities.inlineButtons: "all"`). Message action contract is identical — see `references/tg-delivery.md`. The dialog-warmup requirement is a Telegram-platform constraint, not a skill choice; see `references/tg-delivery.md` and workflow step 7.
- **DND scope.** DND covers ALL non-pomodoro skill invocations: weather, plans, journaling, goal check-ins, fact lookups, chitchat. While a session is active, the only thing the bot does is pomodoro. Confirm with the team that this matches the desired product behaviour before turning it on in production.
- **Variant list.** Built-in: `classic` (25/5), `long` (50/10), `extended` (100/20), `short` (15/3). Custom accepted via `custom <w> <b>` or `<w>/<b>` shorthand with bounds 1–240 / 1–60 min. If the team wants additional named custom profiles (e.g. "deep-work 90/15", "study 45/15"), they can be added as new built-in variants; the current list is intentionally minimal so the user can pick anything via `custom`.
- **Plan-behind signal source.** The proactive-suggestion trigger (step 8) and the scheduled-session plan lookup (step 10) both read plan state from the location defined in `goal-checkin-notifier/references/data-schema.md` (or whatever the planning-skill owner ultimately agrees on). The exact path and field shape are open — confirm with the planning-skill owner. The pomodoro skill must tolerate the file being missing or malformed (silent skip, no error, no suggestion, no schedule).
- **Plan task shape (assumed).** Step 10 reads tasks with at least these fields: `name` (string, used as the topic), `scheduled_at` (ISO-8601 local or UTC), `duration` (minutes), `status` (one of `pending` | `in_progress` | `done` | `skipped`). If the actual plan file uses different field names, the lookup in step 10 must be updated to match — confirm with the planning-skill owner.
- **Suggestion cap is per-chat, not global.** `suggestions.json` tracks cap state per `chat_id`. There is no cross-channel aggregation. If the user has the bot in multiple chats, each chat is capped independently. Confirm whether a global cap is needed.
- **No cross-skill suggestion dedup.** If another skill (e.g. `goal-checkin-notifier`) also nudges the user about focus / pomodoro, the total noise could exceed 1/day. The 1/day cap is enforced by `pomodoro` locally and is unaware of other skills' suggestions. If the team wants global dedup, it must be coordinated at a higher level (e.g. a shared "nudges" state file).
- **Proactive vs reactive trigger.** The scheduled check (every `plan_behind_check_interval_minutes`) and the opportunistic inbound check (on any non-DND-suppressed user message) both feed the same cap. They never run concurrently in a way that could double-fire, because the cap is read-then-write and the next check after a send will see `last_suggestion_date == today` and abort.
- **Statistics integration.** The work-time statistics file (`stats.json`, see workflow step 9) is written by `pomodoro` and may be read by other skills. The default location is `~/.openclaw/pomodoro/stats.json`. The `longterm-stats` skill is the most likely consumer — confirm with the `longterm-stats` owner:
  - Does `longterm-stats` want to **read** the pomodoro stats and merge them into its own cumulative counters? → keep the default location; `longterm-stats` reads on its own cadence.
  - Does `longterm-stats` want to **own** the statistics file, and `pomodoro` should write into it? → set `stats_file` to point at `longterm-stats`'s canonical location. Schema must match.
  - Does `longterm-stats` not care about pomodoro-credited minutes? → no action, the file is skill-internal.
  Until this is decided, the default (`~/.openclaw/pomodoro/stats.json`) is the source of truth and the schema is documented in `references/data-schema.md` → "Statistics state". Other skills may READ but should not WRITE.
- **Stats file is per-chat, not global.** `stats.json` tracks per-`chat_id` counters. If the user has the bot in multiple chats, each chat's work time is tracked independently. Confirm whether a global counter is needed.
- **Credit rule is local.** The credit rule (default `actual_elapsed_capped`) is a pomodoro-skill decision. If the team wants a unified rule across all time-tracking skills, it must be defined in a shared config.
- **Intent recognition for scheduled sessions is agent-side.** Step 10 describes the schedule flow (lookup, generate, propose, confirm) but does NOT define which user utterances trigger it. The agent decides. The skill provides the templates (`schedule-proposal`, `schedule-custom`, `schedule-too-short`, `schedule-no-plan`, `schedule-cancelled`); the agent maps free-text to the flow. False positives are mitigated by the explicit confirmation step.
- **`focus-timer` skill overlap.** The user's workspace also has a `focus-timer` skill (separate Pomodoro-style timer with duration picker, praise-on-complete, 5-window stats). Both skills can coexist — they use different state files and different commands (`/pomodoro …` vs `/focus …` / timer-picker callbacks). The agent should pick one based on user intent. If the team wants them merged, that's a separate refactor.

---

## Golden Hour — исполнение

- **Только при `setup_status: complete`.**
- **Скрипт:** `node scripts/pomodoro.mjs <cmd> --user <user_key>` — детерминированная логика; агент читает JSON (`message`, `buttons`, `notifications`) и шлёт в Telegram.
- **Хранилище:** `users/<user_key>/pomodoro/` (не `~/.openclaw/pomodoro/`).
- **План:** `users/<user_key>/plans/YYYY-MM-DD.json` — `title`, `scheduled_at`, `est_minutes`, `status`.
- **Тик (переходы фаз):** `node scripts/pomodoro-tick.mjs` на heartbeat/cron (~1 мин).
- **DND:** перед любым ответом — `node scripts/pomodoro.mjs route --user <key> --text "<сообщение>"`; при `dnd: true` — только шаблон DND, другие скиллы не вызывать.
- **Связь с `focus-timer`:** помодоро — циклы работа/перерыв; focus-timer — одна задача из плана с похвалой. Пользователь выбирает сам.

| Команда пользователя | Скрипт |
|---|---|
| `/pomodoro start classic` | `pomodoro.mjs start --variant classic` |
| `/pomodoro start 30/60` | `pomodoro.mjs start --shorthand 30/60` |
| `/pomodoro schedule plan` | `pomodoro.mjs schedule --plan true` |
| `/pomodoro status/skip/stop/stats` | `pomodoro.mjs status/skip/stop/stats` |
| «поработаем» / «помодоро» | `schedule --plan true` или уточнить окно |
| callback `pomodoro:skip` | `skip` |
| callback `pomodoro:schedule:confirm` | `schedule-confirm` |
