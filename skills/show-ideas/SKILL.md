---
name: "show-ideas"
description: "Read memory/notes.jsonl (only is_idea=true) and return a full LLM-clustered report (themes, links, priorities, authors, open Qs) for a given period."
status: proposal
version: "v3"
date: "2026-06-16T22:53:10.782Z"
---

# show-ideas (alias: info)

Read the workspace inbox (`memory/notes.jsonl`), keep only entries marked
`is_idea=true`, and return a full considered digest built by the LLM.

This skill backs the bot's `/info` command. The bot is intentionally minimal:
this is its only owner-facing action.

## When to use

Triggers — invoke this skill when the user (or a bot) wants a real digest of
what's been collected:

- "Покажи все идеи"
- "Что у нас накопилось за неделю?"
- `/info` or `/info today` from the Telegram notes bot
- "Сделай дайджест"
- A weekly review request

Do **not** use it for: full export (use a file dump), substring search,
tag/untag operations, or live tailing the inbox.

## Inputs

| Field    | Required | Type | Notes                                                       |
|----------|----------|------|-------------------------------------------------------------|
| `period` | no       | str  | `today` \| `week` (last 7d, default) \| `month` (last 30d) \| `all`. |

There is **no** `include_noise` flag in this revision — noise (tests,
greetings) is excluded by design.

## Steps

1. Resolve workspace: `Path(env.WORKSPACE) or default
   C:\Users\Admin\.openclaw\workspace`. Open `memory/notes.jsonl` in read
   mode. If the file does not exist, return an empty result with a notice.
2. Parse each line as JSON. Skip malformed lines and log a warning.
3. Filter by `period` (cutoff by `date`).
4. Keep only records where `is_idea == True`. Records without the field
   (legacy) are kept — fail-open.
5. Sort by `ts` descending. Truncate to 120 records (the LLM prompt budget).
6. Format a compact per-record listing for the LLM:
   ```
   - 2026-06-16 16:30 @maria [юридические] !4: Подготовить оферту...
   ```
7. Call MiniMax-M3 chat completions
   (`https://api.minimax.io/v1/chat/completions`, model `MiniMax-M3`,
   `max_tokens=1800`, `temperature=0.3`) with a system prompt instructing
   the model to act as an analyst that produces a Russian-language Markdown
   digest. Strip the `<think>...</think>` block from the response.
8. The LLM must return a report with these sections (omit any that have no
   content):
   1. **Краткое резюме** (2–4 строки) — общий смысл идей за период.
   2. **Тематические кластеры** (3–7 штук) с дословными цитатами,
      автором и датой. Если идей мало (<5), плоский список.
   3. **Связи и противоречия** — перекликающиеся или спорящие заметки.
   4. **Топ-3 приоритета** — что разобрать первым, с обоснованием.
   5. **Сводка по авторам** — кто сколько заметок и в каких темах.
   6. **Открытые вопросы** — что уточнить у автора.
9. If the LLM call fails, return a deterministic fallback: a simple list
   grouped by author, header prefixed with "[без LLM]".
10. Split the final text into Telegram-sized chunks (≤ 3800 chars).
    Plain text rendering — escape `<`, `>`, `&` so user content cannot break
    HTML parse mode.

## Output

- A dict:
  ```python
  {
    "header": "💡 Идеи: <period> (<n>)",
    "chunks": ["<chunk 1>", "<chunk 2>", ...],
    "total": <int>,
    "authors": <int>,
    "days": <int>,
    "period": "<period>",
    "llm_used": <bool>,
  }
  ```
- Caller renders `chunks` sequentially to the user.

## Edge cases

- **Empty result**: single chunk "💡 За выбранный период идей нет."
- **LLM returns no content / network error**: fall back to a flat list
  grouped by author. Mark `llm_used=False` in the output dict.
- **Single huge record (>1500 chars)**: truncate to 500 chars in the LLM
  prompt; full text still searchable via grep on `memory/notes.jsonl`.
- **Malformed JSONL line**: log a warning, skip the line.
- **Concurrent appends**: a record may appear twice or be missing; the
  inbox is append-only and not transactional.

## Examples

### Default: week
- input: `period="week"`
- output: a Russian Markdown report with the six sections above.

### Today only
- input: `period="today"`
- output: small report, often just the resume + 1 cluster.

### All time, fallback
- input: `period="all"` with MiniMax-M3 unreachable
- output: flat list grouped by author, header "[без LLM]".

## Reference implementation

`scripts/telegram_notes_bot.py → cmd_info` calls
`build_ideas_report(records, period)` which:

1. Loads records via `_load_records()`.
2. Filters with `_filter_records(period)`.
3. Drops `is_idea=false` (the only filter — no other toggles).
4. Calls `_llm_chat()` to get the report.
5. Falls back to a flat list on error.
6. Chunks the output via `_split_for_tg()`.
7. Sends chunks via `message.answer(chunk)`.

## Files touched

- Reads: `memory/notes.jsonl`
- Reads: `memory/bot-config.json` (digest settings, not modified)
- Writes: nothing