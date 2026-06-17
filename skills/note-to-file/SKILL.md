---
name: "note-to-file"
description: "Append a structured note (author, timestamp, type, content) to memory/inbox/YYYY-MM-DD.md and memory/notes.jsonl. Use for any text/voice/idea that must persist."
status: proposal
version: "v1"
date: "2026-06-16T12:22:43.671Z"
---

# note-to-file

Persist a single note to the workspace inbox. Append-only, no overwrites, no
side effects beyond two files: a human-readable markdown file per day and a
machine-readable JSONL stream.

## When to use

Triggers — invoke this skill when the user (or an automated source, such as a
Telegram bot) wants to capture:

- A written idea, thought, or note
- A voice memo (after transcription, or as raw audio reference)
- A photo / document / link with a caption worth keeping
- Any short text that should be searchable later

Do **not** use it for: ephemeral chat, long-form articles (use a dedicated
file), secrets (never store secrets in inbox).

## Inputs

| Field        | Required | Type   | Notes                                              |
|--------------|----------|--------|----------------------------------------------------|
| `content`    | yes      | string | The text to store. Trim only, do not rewrite.      |
| `author`     | yes      | object | `{ user_id, username?, first_name?, last_name? }`  |
| `kind`       | no       | string | One of: `text`, `voice`, `photo`, `document`, `other`. Default `text`. |
| `duration`   | no       | int    | Seconds. Only meaningful for `kind=voice`.         |
| `extra`      | no       | object | Optional metadata (forwarded_from, tags, etc.)     |

## Steps

1. Resolve the workspace root: `Path(env.WORKSPACE) or
   Path(__file__).resolve().parent.parent`. Default to
   `C:\Users\Admin\.openclaw\workspace` if neither is set.
2. Ensure directories exist: `mkdir -p <workspace>/memory/inbox`.
3. Get the current local time in the user's timezone (default
   `Europe/Moscow`, +03:00). Format the timestamp as
   `YYYY-MM-DDTHH:MM:SS+03:00` (ISO-8601 with offset).
4. Build the JSONL record:
   ```json
   {
     "ts": "<iso8601>",
     "date": "YYYY-MM-DD",
     "time": "HH:MM",
     "user_id": <int>,
     "username": "<str or null>",
     "first_name": "<str or null>",
     "last_name": "<str or null>",
     "kind": "<kind>",
     "duration": <int or null>,
     "content": "<content>"
   }
   ```
5. Append the JSONL line to `<workspace>/memory/notes.jsonl` (create if
   missing). Use UTF-8, no pretty-printing, one record per line, trailing
   newline.
6. Open `<workspace>/memory/inbox/<date>.md` in append mode (UTF-8). If the
   file is new, write a header: `# Inbox YYYY-MM-DD\n\n`.
7. Write the entry as Markdown:
   ```
   ## HH:MM — <first_name [last_name]> @<username> (id <user_id>) <emoji> <kind>[ (<duration>s)]

   <content>

   ```
   Use `?` instead of `@` when the user has no username. Use the same emoji
   table as the running notes bot (💬 text, 🎙 voice, 🖼 photo, 📎 document,
   📝 other).
8. Return a short status line: `appended: YYYY-MM-DD HH:MM <kind> (<n> chars)`
   plus the absolute path of the markdown file.

## Output

- Updated `<workspace>/memory/notes.jsonl` (one new line)
- Updated or created `<workspace>/memory/inbox/YYYY-MM-DD.md`
- Echo to the caller: the status line, both file paths, and the formatted
  Markdown block as it was written (for the caller to confirm).

## Edge cases

- **Empty content**: still record, with `content=""`. Don't skip.
- **Missing user info**: fill `username`, `first_name`, `last_name` with
  `null`, label as `anon` in the Markdown block.
- **File system error**: do not retry blindly — surface the error to the
  caller and stop. The JSONL is the source of truth; if JSONL write fails,
  abort before touching the Markdown file.
- **Concurrent writes**: append-only is safe; do not lock the file.
- **Time drift**: if the system clock jumps between steps 3 and 7, use the
  earlier timestamp for both records so they stay consistent.
- **Large content (>100 KB)**: warn the caller, still write, but suggest
  splitting into a dedicated file linked from the inbox entry.

## Examples

### Plain text note
- input: `content="Надо обсудить спринт"`,
  `author={user_id: 1, username: "beatusx", first_name: "Beatus"}`
- result: appends a line to `notes.jsonl`, adds an `## 14:32 — Beatus
  @beatusx (id 1) 💬 text` block to `inbox/2026-06-16.md`.

### Voice memo
- input: `content="давай созвонимся завтра"`, `kind="voice"`,
  `duration=18`, same author
- result: `## 14:33 — Beatus @beatusx (id 1) 🎙 voice (18s)` plus the body.

## Reference implementation

The Telegram notes bot at `scripts/telegram_notes_bot.py` uses an identical
two-file pattern (`notes.jsonl` + `inbox/YYYY-MM-DD.md`) in its
`append_note()` function. Keep this skill in sync with that function if the
bot evolves.

## Files touched

- `memory/notes.jsonl` (append)
- `memory/inbox/YYYY-MM-DD.md` (append or create)
- `memory/bot-config.json` is **not** modified by this skill.