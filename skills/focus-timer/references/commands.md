# User commands

All commands work in TG DM with the bot. They are case-insensitive and can be in Russian or English.

| Command | Aliases | Action |
|---|---|---|
| `начать [duration] [task_title]` | `старт [duration]`, `start`, `/timer start` | Start a session. Duration can be explicit, Russian word, or omitted (then show selection prompt). Task can be specified by short title or omitted (most recent active). |
| `стоп` | `stop`, `хватит`, `/timer stop` | Stop the current session manually. Logs time but does NOT mark task as done. |
| `пауза` | `pause`, `/timer pause` | Pause the current session. |
| `продолжить` | `resume`, `/timer resume` | Resume a paused session. |
| `статус` | `status`, `/timer status` | Reply with elapsed time, current task. |
| `статистика` | `стата`, `stats`, `/timer stats` | Show all 5 windows with totals and top tasks. |
| `статистика <window>` | see below | Show details for a specific window. |
| `статистика <goal_keyword>` | — | Show stats for a specific goal across all 5 windows. |
| `/timer help` | `помощь` | List all commands. |

## Duration parsing

| Input | Minutes | Source |
|---|---|---|
| `час`, `60`, `1ч`, `1 час` | 60 | preset `час` |
| `пара`, `45`, `45м` | 45 | preset `пара` |
| `30м`, `30`, `30 мин` | 30 | preset `30м` |
| `полчаса` | 30 | custom |
| `1.5ч`, `1ч 30м`, `1 час 30 мин`, `90`, `90м` | 90 | custom |
| `2ч`, `2 часа`, `120` | 120 | custom |
| `25с`, `25 секунд` | 0 (rounded to 1 min) | custom — sub-minute not useful for tracking |

Aliases are case-insensitive. Whitespace is flexible.

## "Начинаю" button flow (from goal-checkin-notifier)

When user clicks "Начинаю" in a task ping, the focus-timer sends a duration selection prompt:

```
Сколько хочешь заниматься над *{task_title}*?
```

With inline buttons:

| Button | Action |
|---|---|
| `[⏱ час (60)]` | Start session with 60 min |
| `[⏱ пара (45)]` | Start session with 45 min |
| `[⏱ 30м (30)]` | Start session with 30 min |
| `[⏱ своё]` | Ask user for custom duration in free text |

User picks (button click or text reply) → session starts.

## End-of-session flow (praise + options, when timer expires)

When `planned_duration_minutes` is reached:

```
Молодец! 🎉 Занимался *{task_title}* {minutes} мин. Что дальше?
```

Inline buttons:

| Button | Action |
|---|---|
| `[Засчитать]` | Mark `task.status = "done"`, append `time_spent_minutes`, log to history, **update stats counters (all 5 windows)**, end session |
| `[Ещё!]` | Log finished segment to history with `end_reason: timer_expiry_continued`, show duration selection for new session |

**No mid-session notifications** during the active session. The skill is silent between start and the end-of-session prompt.

## Recurring daily tasks

For tasks that appear in the plan daily (recurring in the planning skill), each session is independent:

- A new session starts fresh each day
- The user picks duration again each time (no implicit carry-over)
- All sessions go to `users/<user_key>/focus/sessions.json.history`
- Statistics from history and stats.json aggregate these

## Ambiguity resolution

If multiple tasks match `task_title` in "начать {title}", the skill asks the user to disambiguate by listing the matches.

If no task matches, the skill offers the top 3 active tasks by weight.
