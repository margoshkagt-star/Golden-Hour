---
name: "pomodoro"
description: "Telegram Pomodoro technique timer: variants, notifications, DND, stats, proactive once-per-day suggestions."
---

# PROPOSAL: pomodoro

## Summary

Telegram-delivered Pomodoro technique timer for the `code-writer` agent. Cycles between work blocks and breaks, sends a notification at every phase transition, persists state to disk so a session survives restarts, supports classic/long/extended/short variants and user-defined custom durations, automatically accumulates the work portion of every pomodoro into a durable statistics file, stays silent on non-pomodoro topics while a session is running (DND), and — at most once a day — gently suggests trying a pomodoro when the user is behind on their plan.

## Files

- `SKILL.md` — frontmatter + 9-step workflow + Configuration + Output + Open contract (~134 lines).
- `references/data-schema.md` — JSON shapes for `session.json`, `suggestions.json`, `stats.json`, per-day transition log, per-day summary, per-day stats audit log, per-day DND log (~193 lines).
- `references/message-templates.md` — Telegram message text for every notification (work-start, break-start, long-break-start, session-end, status, dnd-off-topic, telegram-warmup, custom-start, custom-invalid, custom-list, plan-behind-suggestion, stats-daily) (~144 lines).
- `references/tg-delivery.md` — Telegram delivery contract, including the dialog-warmup requirement (~37 lines).
- `proposal.json` — this proposal's metadata (`schema: openclaw.skill-workshop.proposal.v1`, `kind: create`, `status: applied`).

## Capabilities

1. **Variants on demand** — `/pomodoro start classic | long | extended | short` for built-ins, `/pomodoro start custom <w> <b>` or `/pomodoro start <w>/<b>` shorthand for user-defined durations (bounds: work 1–240 min, break 1–60 min).
2. **Phase notifications** — work-start, break-start, long-break-start, session-end. Long break fires every `long_break_every` cycles (default 4) and lasts `long_break_minutes` (default 15).
3. **Inline buttons + slash commands** — `[Пропустить фазу]` and `[Завершить сессию]` on every active-phase notification; `pomodoro:skip` / `pomodoro:stop` callback_data.
4. **Crash-safe state** — atomic writes via temp+rename, drift recovery on restart, persistent across all restarts.
5. **DND during active sessions** — non-pomodoro messages during `work`/`break`/`long_break` get a one-line `dnd-off-topic` reply and are dropped. No parsing, no journal entries, no skill calls.
6. **Telegram dialog warm-up** — on first session start, refuses to start until the user has sent at least one message to the bot (Telegram silently drops messages to users who haven't opened a dialog).
7. **Proactive once-per-day suggestion** — at most one `plan-behind-suggestion` per local calendar day, hard-capped via `suggestions.json`. Suppressed during active sessions and quiet hours. Triggered by overdue tasks or low completion rate from the user's plan.
8. **Automatic work-time statistics** — every work block (full or partial) is added to `stats.json` with per-date and lifetime counters. Credit rule: `actual_elapsed_capped` by default (partial credit on skip/stop, full credit on normal completion and drift recovery). Queryable via `/pomodoro stats`.

## Open contracts (cross-skill coordination)

- **Plan-behind signal source** — the proactive-suggestion trigger reads plan state from the location defined in `goal-checkin-notifier/references/data-schema.md`. Needs confirmation from the planning-skill owner. Pomodoro tolerates the file being missing or malformed (silent skip, no error, no suggestion).
- **Statistics integration with `longterm-stats`** — three possible ownership models (read-only consumer, owner of stats file, no integration). Until decided, `pomodoro` is the canonical writer of `stats.json` and other skills read but do not write.
- **Quiet hours** — shared config with `goal-checkin-notifier`. DND is independent (bound to session phase, not the wall clock).
- **Channel identity** — same owner Telegram bot, same OpenClaw message action contract, same `inlineButtons: "all"` capability.

## Verification

All files exist, frontmatter is well-formed YAML, proposal.json parses with the required fields, and all 3 supportFiles' sha256+sizeBytes match disk. Total skill size: 565 lines (cap 1000, 57%).

## Goal

Provide a complete, production-ready Pomodoro technique timer as an OpenClaw workspace skill, with all behaviour documented (variants, statistics, DND, proactive suggestions, warm-up), all coordination points with neighbouring skills (`goal-checkin-notifier`, `longterm-stats`) marked as explicit open contracts, and no runtime script — same architecture as the existing `goal-checkin-notifier`.

## Evidence

Built incrementally across the chat session based on iterative user requirements:

- Initial ask: basic Pomodoro timer (25/5) with Telegram notifications, modelled on `goal-checkin-notifier`.
- Refinement 1: spelling fix to "помодоро" (Pomodoro, not "помидора" / tomato), and notification text changed to "время работы" / "время отдыха".
- Refinement 2: DND during active sessions (bot only replies to pomodoro commands while a session runs) + Telegram dialog warm-up (user must send `/start` once before bot messages deliver).
- Refinement 3: added `extended` variant (1h40m / 20m for deep-focus), and `custom` variant with bounds 1–240 / 1–60 for user-defined durations.
- Refinement 4: proactive once-per-day suggestion to try a pomodoro when the user falls behind on the plan, hard-capped.
- Refinement 5: replaced `🍅` (tomato emoji) with the word "помодоро" in all notification text.
- Refinement 6: automatic work-time statistics accumulation into `stats.json` with configurable credit rule.
