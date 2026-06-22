# Telegram delivery

Identical contract to `goal-checkin-notifier`. This skill uses the OpenClaw message action with `channel: "telegram"` and the same owner bot. See `../goal-checkin-notifier/references/tg-delivery.md` for the full contract: action shape, `reply_markup.inline_keyboard` translation, `capabilities.inlineButtons: "all"` requirement, and the manual curl fallback.

## callback_data convention

Format: `pomodoro:<action>` (no task id — the timer is single-instance per chat).

- `pomodoro:skip` — advance the current phase
- `pomodoro:stop` — end the session

Both arrive in the agent session as text `callback_data: pomodoro:skip` / `callback_data: pomodoro:stop`; the skill parses the prefix and dispatches.

## Example payload (work-start)

```json
{
  "action": "send",
  "channel": "telegram",
  "to": "<OWNER_TG_USER_ID>",
  "message": "помодоро Помодоро #1 • работа • 25 мин. Погнали!",
  "buttons": [
    [{"text": "Пропустить фазу", "callback_data": "pomodoro:skip"}],
    [{"text": "Завершить",        "callback_data": "pomodoro:stop"}]
  ]
}
```

## Dialog warm-up requirement

Telegram only delivers bot messages to a user who has opened a dialog with the bot (i.e. sent at least one message, typically `/start`). If a user has not done this yet, every `message action` call to them **silently fails** — no error, no delivery, no notification. The pomodoro skill must check for this on first session start:

- Track a `dialog_opened` flag in the state file.
- On the first inbound message of any kind from a given `chat_id`, flip `dialog_opened: true` (the user's message already opened the dialog server-side; no template is needed for this).
- On `/pomodoro start`, if `dialog_opened` is `false`, send the `telegram-warmup` template and refuse to start the session. The user is asked to send `/start` (or any message) and retry.

This is a Telegram-platform constraint, not a skill design choice. See SKILL.md → workflow step 7 and the `telegram-warmup` template in `message-templates.md`.
