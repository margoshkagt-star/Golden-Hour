# Notification templates

All messages in Russian, warm and informal — same voice as `goal-checkin-notifier`. Use TG Markdown (`*bold*`, `_italic_`).

## work-start

```
помодоро Помодоро #{N} • время работы • {work_minutes} мин. Погнали!
```

`{N}` is `cycles_done + 1`. Inline buttons: `[Пропустить фазу]` `[Завершить]`.

For custom variants, `{work_minutes}` holds the user-supplied value (e.g. 30 for `custom 30 60`).

## break-start

```
☕ Помодоро #{N} • время отдыха • {break_minutes} мин. Отдыхай!
```

Inline buttons: `[Пропустить фазу]` `[Завершить]`.

For custom variants, `{break_minutes}` holds the user-supplied value.

## long-break-start

```
🌿 Время большого отдыха • {long_break_minutes} мин. Погуляй, попей воды.
```

Inline buttons: `[Пропустить фазу]` `[Завершить]`.

## session-end

```
🏁 Сессия завершена • {N} циклов • итого {work_minutes} мин работы.
```

No buttons.

## status (reply to /pomodoro status)

```
Сейчас: *{phase_ru}* ({elapsed_min}/{duration_min} мин)
Циклов сделано: *{cycles_done}*
Вариант: {variant_display}
```

Inline buttons: `[Пропустить фазу]` `[Завершить]`.

`{phase_ru}` is `время работы` / `время отдыха` / `время большого отдыха`.

`{variant_display}` is the variant name for built-ins (`classic` / `long` / `extended` / `short`) or `custom {work_minutes}/{break_minutes}` when the user picked a custom duration (e.g. `custom 30/60`).

## skip confirmation

```
Ок, переключаюсь на *{next_phase_ru}* ({duration_min} мин).
```

Inline buttons match the next-phase template.

## Quiet-hours deferred suffix

Appended to any notification that was held back:

```
(таймшифт — отправлено в {sent_at}, попали в тихие часы)
```

## dnd-off-topic

Reply when an active session is running and the user sends anything that is not a pomodoro command. Brief, warm, does **not** engage with the message content. No buttons.

```
Сейчас идёт *{phase_ru}* (осталось ~{remaining_min} мин) — сфокусируйся, отвечу после помодоро
```

`{remaining_min}` is `ceil((phase_started_at + phase_duration_minutes*60_000 - now) / 60_000)`. Clamp to 0 if negative.

## telegram-warmup

Sent the first time the user tries to start a session but has never messaged the bot. Telegram will not deliver bot messages to a user who has not opened a dialog.

```
Привет! Чтобы я мог(ла) присылать уведомления, сначала нажми /start в этом чате. После этого /pomodoro start заработает.
```

No buttons.

## custom-start (confirmation, optional)

Sent right after `/pomodoro start custom <w> <b>` succeeds. The standard work-start template already announces the work block with the actual `{work_minutes}` value, so this template is OPTIONAL — only use it if you want a clearer explicit confirmation that the values the user typed were understood. No buttons.

```
помодоро Кастомный помодоро • работа {work_minutes} мин • отдых {break_minutes} мин. Погнали!
```

## custom-invalid

Reply when the user tries to start a custom variant with malformed or out-of-bounds values. Warm, with the valid bounds and a worked example. No buttons.

```
Кастомные тайминги: работа 1–240 мин, отдых 1–60 мин. Например: `/pomodoro start 30/60` или `/pomodoro start custom 30 60`.
```

Triggered for: missing numbers, non-integer values, work outside 1–240, break outside 1–60, work or break equal to 0, negative numbers, more than two numbers after `custom`.

## custom-list (reply to /pomodoro variants)

Optional helper if the user asks "какие есть варианты?" — list the built-ins plus the custom range.

```
Доступные варианты:
помодоро classic — 25/5
помодоро long — 50/10
помодоро extended — 100/20 (1ч40м / 20м, для глубокого фокуса)
помодоро short — 15/3
⚙️ custom — любые тайминги в пределах работа 1–240 мин, отдых 1–60 мин. Например: `/pomodoro start 30/60`.
```

## plan-behind-suggestion

Sent when the user is falling behind on their plan and the daily cap has not been hit. ONE LINE. Warm, NOT pushy, NOT a status report, NOT a list of overdue tasks. The user is free to ignore — the next suggestion will not come until tomorrow. No buttons.

```
Вижу, что план на сегодня подгоняет. Хочешь попробовать `/pomodoro start classic` — 25 минут сфокусированной работы?
```

Triggered by workflow step 8. Hard cap: at most one of these per chat per local calendar day. The wording MUST stay short and MUST NOT name specific overdue tasks, shame, or pressure. If the team wants a different tone (more playful, more formal, English), make a separate template; do not overload this one.


## stats-daily

Reply to `/pomodoro stats`. Shows today's work time, today's cycle count, and lifetime totals. Concise, two-line, no buttons.

```
📊 Сегодня: *{today_work_minutes} мин* работы, {today_cycles} циклов.
За всё время: *{total_work_minutes} мин* работы, {total_cycles} циклов.
```

`{today_work_minutes}` is the sum of credited minutes for today's date in `stats.json` (keyed by local-time `YYYY-MM-DD`). `{today_cycles}` is the number of completed work blocks today. `{total_work_minutes}` and `{total_cycles}` are the lifetime sums from the same file. If `stats.json` is missing, show zeros (the file is created on the first work-block credit, not on skill install).

If the user asks for more detail (e.g. "покажи по дням"), the skill can read `stats.json` and produce a longer breakdown — that reply is ad-hoc, not a templated notification.
