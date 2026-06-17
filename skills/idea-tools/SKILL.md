---
name: "idea-tools"
description: "Operate on collected ideas: get full text by id, find semantic relations, semantic search, manage tags, view tasks, statistics. Read-only except tag mutation."
status: proposal
version: "v1"
date: "2026-06-16T17:07:11.999Z"
---

# idea-tools

Operate on the existing idea collection (`memory/notes.jsonl`). Read-only
viewing plus two small mutations: add/remove manual tags.

## When to use

Triggers — invoke this skill when the user (or a bot) wants to work with
already-collected ideas:

- "Покажи полный текст этой идеи"
- "Какие идеи связаны с этой?"
- "Найди идеи про X" (semantic, not substring)
- "Это важно / это задача / помечай как hot"
- "Какие у меня сейчас задачи?"
- "Сколько идей за неделю и от кого?"

Do **not** use it for: ingesting new notes (use `note-to-file`).

## Inputs

| Field      | Required | Type | Notes                                                |
|------------|----------|------|------------------------------------------------------|
| `op`       | yes      | str  | `source` \| `related` \| `find` \| `tag` \| `untag` \| `tags` \| `tasks` \| `stats` |
| `id`       | for source/related/tag/untag | str | 10-char record id (e.g. `aaa111bb22`) |
| `query`    | for find | str  | Free-text query (semantic, not substring)            |
| `tag`      | for tag/untag | str | Lowercase tag without `#` prefix                |
| `period`   | for tasks | str  | `today` \| `week` \| `month` \| `all` (default `week`) |
| `limit`    | no       | int  | Max hits (default 5 for find, 3 for related, 50 for tasks) |

## Steps (per op)

### `source` — full text
1. Load `memory/notes.jsonl`, find the record by `id`.
2. Return a single block: id, timestamp, author, topic, importance, tags,
   full content. Truncate only above 4000 chars.

### `related` — semantic neighbours
1. Load all `is_idea=true` records (limit 80). Exclude the target.
2. Build a compact per-record listing: `id | date time @author: summary`.
3. Call MiniMax-M3 chat completions with a system prompt: pick up to 3
   candidates semantically related to the target. Strip
   `<think>...</think>`. Parse JSON `{related: [{id, reason}]}`.
4. Return: target id + list of `{id, reason, snippet}`.

### `find` — semantic search
1. Load all `is_idea=true` records (limit 120).
2. Call MiniMax-M3 with a system prompt: select up to 5 best matches for
   the query. Parse JSON `{hits: [{id, score 1..5, reason}]}`.
3. Return: query + list of `{id, score, reason, snippet}`.

### `tag` / `untag` — manual tags
1. Load the record by `id`.
2. If `tag`: append if not already present, set `tags = sorted(set)`.
3. If `untag`: remove the tag, keep others, set `tags = sorted(set)`.
4. Rewrite the matching JSONL line in place (re-read whole file, replace
   that one line, write back). Use UTF-8.
5. Return: confirmation with the new tag set.

### `tags` — overview
1. Tally all auto-`topic` values and all manual `tags` across
   `is_idea=true` records.
2. Return two sorted lists (most frequent first, top 15 each).

### `tasks` — high-importance only
1. Filter `is_idea=true` AND `importance >= 4`.
2. Sort by `(-importance, ts)`. Apply `period` cutoff by `date`.
3. Return up to 50 items: id, importance, author, date, time, snippet.

### `stats` — activity statistics
1. Tally total records, ideas, noise, by author, by day, by kind, by
   topic. Top 10 authors, last 7 days.
2. Return a single block with sections.

## Output

- Each op returns a dict `{op, chunks, total, ok}` where `chunks` is a
  list of strings ready to render (Telegram HTML, ≤ 3800 chars each).
- Tag/untag additionally returns `record` (the updated record).

## Edge cases

- **Missing id**: return a single chunk "Заметка с id #X не найдена."
- **No matching ideas**: return a single chunk "Ничего не нашлось."
- **LLM returns no JSON / garbage**: log warning, fall back to substring
  search for `find`/`related`, otherwise return a one-line notice.
- **JSONL line malformed**: log warning, skip the line.
- **Concurrent rewrite during tag/untag**: read-modify-write is racy but
  acceptable (rare on Telegram); on `json.JSONDecodeError` mid-write,
  abort and re-read the original file.

## Examples

### `source`
- input: `op="source", id="ccc333"`
- output: `💡 #ccc333 — 2026-06-16 18:00 @maria · CI/CD !5 🏷hot\n<content>`

### `find`
- input: `op="find", query="юридические документы"`
- output: top 5 ideas whose summary is semantically related.

### `tag`
- input: `op="tag", id="aaa111", tag="q3"`
- output: `Готово: #aaa111 → 🏷q3`

## Reference implementation

`scripts/telegram_notes_bot.py` exposes all 8 ops as command handlers
(`cmd_source`, `cmd_related`, `cmd_find`, `cmd_tag`, `cmd_untag`,
`cmd_tags`, `cmd_tasks`, `cmd_stats`). They all share `_load_records()`,
`_by_id()`, `_format_record()`, `_save_record_tags()`.

## Files touched

- Reads: `memory/notes.jsonl` (for all ops)
- Writes: `memory/notes.jsonl` (only for `tag` and `untag`)
- Writes: nothing else