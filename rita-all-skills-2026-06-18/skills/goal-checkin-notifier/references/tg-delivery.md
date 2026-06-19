# Telegram delivery

The skill sends notifications via the OpenClaw message action. The plugin target is `channel: "telegram"` (configured in `channels.telegram` of `openclaw.json`), with `dmPolicy: "allowlist"` and an explicit numeric `allowFrom` for one-owner bots.

## Sending from a skill (JS context)

The skill invokes the message action with the action shape. Example for a task ping:

```json
{
  "action": "send",
  "channel": "telegram",
  "to": "<OWNER_TG_USER_ID>",
  "message": "Пора за *Физика* 🌅\nСессия по физике\n≈60 мин\n\nКак настрой, начинаем?",
  "buttons": [
    [
      { "text": "Начинаю",     "callback_data": "goal:done:t_101" }
    ],
    [
      { "text": "Отложить 30м", "callback_data": "goal:snooze:t_101" }
    ],
    [
      { "text": "Пропустить",   "callback_data": "goal:skip:t_101" }
    ]
  ]
}
```

The action-level `buttons` field is what the openclaw message action exposes; the runtime translates it into TG's `reply_markup.inline_keyboard` at the Bot API boundary.

`capabilities.inlineButtons: "all"` must be set in `channels.telegram` for the bot to send inline keyboards (default is `allowlist`; we use `all` for personal bot convenience).

## Direct Bot API (verified format)

When sending from JS/TS or shell, the Telegram Bot API expects `reply_markup.inline_keyboard`. This is the format that always renders correctly in TG:

```json
{
  "chat_id": "<OWNER_TG_USER_ID>",
  "text": "Пора за *Физика* 🌅\nСессия по физике\n≈60 мин\n\nКак настрой, начинаем?",
  "parse_mode": "Markdown",
  "reply_markup": {
    "inline_keyboard": [
      [{"text": "Начинаю", "callback_data": "goal:done:t_101"}],
      [{"text": "Отложить 30м", "callback_data": "goal:snooze:t_101"}],
      [{"text": "Пропустить", "callback_data": "goal:skip:t_101"}]
    ]
  }
}
```

## CLI --presentation caveat

The `openclaw message send --presentation '{"buttons":[...]}'` CLI flag does **not** reliably pass inline keyboards through to TG. The CLI accepts the JSON, returns a message_id, but the resulting TG message arrives without `reply_markup`. The likely cause: `--presentation` is the "shared presentation payload" (text, context, dividers, selects) — `buttons` is a separate action-level field in the message action shape, not a presentation block.

**For manual CLI tests:** use direct Bot API calls (as above) via `curl` or a Node.js script. Spawning `cmd.exe` with the args as a proper array works; PowerShell `$var` interpolation strips the inner `"` characters and breaks the JSON, and inline `"{...}"` strings get split on `{` / `}` boundaries in some invocation paths.

**The skill itself does not hit this issue** — it runs in the OpenClaw JS runtime and invokes the message action with the action-level `buttons` field, which the runtime should translate to the correct `reply_markup.inline_keyboard` for TG.

## Manual CLI test (direct curl)

```bash
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "<OWNER_TG_USER_ID>",
    "text": "Пора за *Физика* 🌅\n...",
    "parse_mode": "Markdown",
    "reply_markup": {
      "inline_keyboard": [
        [{"text": "Начинаю", "callback_data": "goal:done:t_101"}],
        [{"text": "Отложить 30м", "callback_data": "goal:snooze:t_101"}],
        [{"text": "Пропустить", "callback_data": "goal:skip:t_101"}]
      ]
    }
  }'
```

## callback_data convention

Format: `goal:<action>:<task_id>`

- `goal:done:<task_id>` — user pressed "Готово" / "Начинаю"; set `status: "in_progress"` (treat as kickoff) or `status: "done"` (treat as completion — decide at apply time)
- `goal:snooze:<task_id>` — user pressed "Отложить 30м"; set `snoozed_until` to now + 30 min, leave `status` as is
- `goal:skip:<task_id>` — user pressed "Пропустить"; set `status: "skipped"`

When the user clicks a button, the gateway delivers a new agent message in the same session as text:

```
callback_data: goal:done:t_101
```

The skill parses the prefix and the `<action>:<task_id>` pair, then updates the plan file.

## Required OpenClaw configuration (one-time)

In `openclaw.json`:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "dmPolicy": "allowlist",
      "allowFrom": ["<OWNER_TG_USER_ID>"],
      "capabilities": {
        "inlineButtons": "all"
      },
      "botToken": {
        "source": "env",
        "provider": "default",
        "id": "TELEGRAM_BOT_TOKEN"
      }
    }
  }
}
```

The bot token goes into a `TELEGRAM_BOT_TOKEN` env var (or your own `id` name). Find your numeric TG user ID via `openclaw logs --follow` after DMing the bot, or via Bot API `getUpdates`.
