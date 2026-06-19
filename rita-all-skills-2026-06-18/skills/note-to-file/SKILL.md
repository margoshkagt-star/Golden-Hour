---
name: "note-to-file"
description: "Append note (text/voice/photo/task/idea) to memory/inbox/YYYY-MM-DD.md and notes.jsonl. kind=task → route to task-triage."
revision: 2
revision_note: "Добавлен kind=task: маршрутизация в task-triage + запись в state/tasks.yaml (closes V-LU-7)."
author: karim
status_source: karim-handcraft
---

# note-to-file

Persist a single note to the workspace inbox. Append-only, no overwrites, no
side effects beyond two files: a human-readable markdown file per day and a
machine-readable JSONL stream. **NEW:** `kind=task` маршрутизирует в task-triage + state/tasks.yaml.

## When to use

Triggers — invoke this skill when the user (or an automated source, such as a
Telegram bot) wants to capture:

- A written idea, thought, or note (`kind=text` или `kind=idea`)
- A voice memo (after transcription, or as raw audio reference) (`kind=voice`)
- A photo / document / link with a caption worth keeping (`kind=photo` / `kind=document`)
- **A task that should be tracked** (`kind=task` — маршрутизация в task-triage)
- Any short text that should be searchable later

Do **not** use it for: ephemeral chat, long-form articles (use a dedicated
file), secrets (never store secrets in inbox).

## Inputs

| Field        | Required | Type   | Notes                                              |
|--------------|----------|--------|----------------------------------------------------|
| `content`    | yes      | string | The text to store. Trim only, do not rewrite.      |
| `author`     | yes      | object | `{ user_id, username?, first_name?, last_name? }`  |
| `kind`       | no       | string | **NEW: `text` / `idea` / `task` / `voice` / `photo` / `document` / `other`**. Default `text`. |
| `duration`   | no       | int    | Seconds. Only meaningful for `kind=voice`.         |
| `extra`      | no       | object | Optional metadata (forwarded_from, tags, etc.)     |
| `importance` | for kind=idea | int | 1-5, по умолчанию 3. Игнорируется для других kind. |
| `deadline`   | for kind=task | ISO date | Дедлайн для задачи. Optional, default null.   |
| `weight`     | for kind=task | int | Вес 1-10. Default = важность из контекста.    |

### Маршрутизация по `kind`

| `kind` | Что делает |
|---|---|
| `text` | Просто записать в jsonl + md (старое поведение) |
| `idea` | Записать в jsonl + md с `is_idea=true, importance=<int>` (чтобы idea-tools / show-ideas подхватили) |
| **`task`** | **Записать в jsonl + md как обычную заметку + вызвать `task-triage` для декомпозиции + записать результат в `state/tasks.yaml`** |
| `voice` | Как text + duration в md-блоке |
| `photo` / `document` | Как text + emoji маркер |
| `other` | Fallback |

**`kind=task` (главное нововведение):**
1. Записать в `notes.jsonl` и `inbox/<date>.md` как обычную заметку (kind=task в extra).
2. Вызвать `task-triage` с входом: `{title: <content>, deadline: <deadline>, weight: <weight>, no_decompose: <true если user попросил просто записать>}`.
3. `task-triage` сделает декомпозицию (если сложно), capability assessment, и добавит записи в `state/tasks.yaml`.
4. Вернуть юзеру сводку: «Задача записана + N подзадач в task-tracker'е».

## Steps

1. Resolve the workspace root: `Path(env.WORKSPACE) or
   Path(__file__).resolve().parent.parent`. Default to
   `C:\Users\Tikho\.openclaw\workspace` (исправлено с Admin на Tikho) if neither is set.
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
     "is_idea": <bool, true если kind=idea>,
     "importance": <int 1-5, только для kind=idea>,
     "content": "<content>"
   }
   ```
5. **Если `kind=task`** — после записи в JSONL вызвать `task-triage`:
   - Сформировать вход: `{title: <content>, deadline: <deadline>, weight: <weight>, no_decompose: <true если явный no_decompose из extra>}`.
   - Передать управление `task-triage` (он сам создаст записи в `state/tasks.yaml`).
   - Вернуть результат task-triage вместе со status note-to-file.
6. Append the JSONL line to `<workspace>/memory/notes.jsonl` (create if
   missing). Use UTF-8, no pretty-printing, one record per line, trailing
   newline.
7. Open `<workspace>/memory/inbox/<date>.md` in append mode (UTF-8). If the
   file is new, write a header: `# Inbox YYYY-MM-DD

`.
8. Write the entry as Markdown:
   ```
   ## HH:MM — <first_name [last_name]> @<username> (id <user_id>) <emoji> <kind>[ (<duration>s)]

   <content>

   ```
   Use `?` instead of `@` when the user has no username. Use the same emoji
   table as the running notes bot (💬 text, 🎙 voice, 🖼 photo, 📎 document, ✅ task, 💡 idea, 📝 other).
9. Return a short status line: `appended: YYYY-MM-DD HH:MM <kind> (<n> chars)`
   plus the absolute path of the markdown file. **Если `kind=task`** — добавить сводку от task-triage.

## Output

- Updated `<workspace>/memory/notes.jsonl` (one new line)
- Updated or created `<workspace>/memory/inbox/YYYY-MM-DD.md`
- **NEW:** при `kind=task` — обновлён `state/tasks.yaml` через task-triage
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
- **`kind=task` + task-triage fail**: запись в JSONL сохраняется, но в `state/tasks.yaml` задача НЕ появляется. Сообщить юзеру: «Заметка сохранена, но в tracker не попала — попробуй ещё раз или запиши вручную через task-tracker».

## Examples

### Plain text note
- input: `content="Надо обсудить спринт"`, `kind="text"`,
  `author={user_id: 1, username: "beatusx", first_name: "Beatus"}`
- result: appends a line to `notes.jsonl`, adds an `## 14:32 — Beatus
  @beatusx (id 1) 💬 text` block to `inbox/2026-06-16.md`.

### Voice memo
- input: `content="давай созвонимся завтра"`, `kind="voice"`,
  `duration=18`, same author
- result: `## 14:33 — Beatus @beatusx (id 1) 🎙 voice (18s)` plus the body.

### ⭐ Idea (NEW)
- input: `content="Нужно попробовать дыхание 3:3 на пробежке"`, `kind="idea"`, `importance=3`
- result: `## 14:34 — Beatus @beatusx (id 1) 💡 idea` + is_idea=true, importance=3 в JSONL → idea-tools может подхватить.

### ⭐⭐ Task (NEW, главное)
- input: `content="Купить молоко и яйца"`, `kind="task"`, `weight=3`
- result:
  - JSONL: kind=task, обычная запись
  - md: `## 14:35 — Beatus @beatusx (id 1) ✅ task` блок
  - task-triage: вход (title="Купить молоко и яйца", weight=3) → capability 🟡 (покупка = физическая) → запись в state/tasks.yaml со status=planned
  - возврат: «Задача записана + добавлена в task-tracker (#42, вес 3, статус planned)»

## Reference implementation

The Telegram notes bot at `scripts/telegram_notes_bot.py` uses an identical
two-file pattern (`notes.jsonl` + `inbox/YYYY-MM-DD.md`) in its
`append_note()` function. For `kind=task`, additionally calls
`task_triage_for_note()`. Keep this skill in sync with that function if the bot evolves.

## Files touched

- `memory/notes.jsonl` (append)
- `memory/inbox/YYYY-MM-DD.md` (append or create)
- **`state/tasks.yaml` (NEW, через task-triage при `kind=task`)**
- `memory/bot-config.json` is **not** modified by this skill.
