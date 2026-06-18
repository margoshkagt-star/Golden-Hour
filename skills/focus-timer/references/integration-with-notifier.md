# Integration with goal-checkin-notifier

The two skills work together for the "Начинаю" button flow and the end-of-session state sync.

## Flow: "Начинаю" button (duration selection, not auto-start)

1. `goal-checkin-notifier` sends a task ping with the button "Начинаю" (callback_data: `goal:done:<task_id>`). **No time estimate in the message.**
2. User clicks the button in TG
3. OpenClaw gateway delivers the callback to the agent session as text: `callback_data: goal:done:<task_id>`
4. `goal-checkin-notifier` skill processes the callback, updates plan file's `task.status = "in_progress"`
5. **`focus-timer` skill processes the same callback**, sends a duration selection prompt (NOT auto-starting):
   ```
   Сколько хочешь заниматься над *{task_title}*?
   [⏱ час (60)] [⏱ пара (45)] [⏱ 30м (30)] [⏱ своё]
   ```
6. User picks duration (button click → `callback_data: timer:duration:<N>:`) or text ("30" / "час" / etc.)
7. `focus-timer` starts the session with the chosen duration, sends confirmation: "Запустил таймер на *{task_title}* 🦊 ⏱ {duration} мин"

## Flow: end-of-session (praise + "[Засчитать]")

1. `focus-timer`'s planned duration is reached
2. Bot sends: "Молодец! 🎉 Занимался *{task_title}* {minutes} мин. Что дальше?" with buttons `[Засчитать]` and `[Ещё!]`
3. User clicks `[Засчитать]` (callback: `timer:done:<task_id>`)
4. `focus-timer` writes `task.status = "done"` to the plan file
5. `focus-timer` updates `users/<user_key>/focus/stats.json` (increments all 5 windows for this session)
6. `goal-checkin-notifier` should:
   - Skip pings for this task for the rest of the day (it's done)
   - Not include it in evening check-in's "remaining tasks" list

## Callback handling precedence

The agent dispatches callbacks based on prefix:

| Prefix | Handler |
|---|---|
| `goal:done:` | notifier updates status, focus-timer shows duration prompt |
| `goal:snooze:` | notifier sets `snoozed_until` |
| `goal:skip:` | notifier sets `status: "skipped"` |
| `timer:duration:<N>:` | focus-timer starts session with N minutes |
| `timer:custom:` | focus-timer asks for free-text duration |
| `timer:done:` | focus-timer marks task done + updates stats |
| `timer:more:` | focus-timer shows duration prompt for new session |
| `timer:stats:` | focus-timer shows stats summary |

## Why two skills

`goal-checkin-notifier` is concerned with the **plan state** (status updates, journal entries).
`focus-timer` is concerned with the **time-state** (session start, elapsed, log, stats).

Keeping them separate means:
- User can pause/track time without changing plan status
- User can mark a task done without timing it (e.g., quick task)
- Either skill can be disabled independently
