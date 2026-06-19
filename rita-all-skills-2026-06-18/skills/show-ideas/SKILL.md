---
name: "show-ideas"
description: "Read ideas, return LLM-clustered report. Hint to promote top ideas."
revision: 2
revision_note: "Add promote hint for V-LU-11 fix."
author: karim
status_source: karim-handcraft
---

# show-ideas (alias: info)

Read the workspace ideas collection, filter by is_idea=true, and return an LLM-clustered digest.

## When to use

Use when the user wants a digest of collected ideas.

## Input

- `period` (optional): today / week (default) / month / all

## Steps

1. Open the ideas file. If missing, return empty.
2. Parse each line as JSON. Skip malformed.
3. Filter by period.
4. Keep only is_idea=true.
5. NEW: filter out ideas that already have the `promoted` tag.
6. Sort by timestamp descending. Truncate to 120 records.
7. Format a compact listing for the LLM prompt.
8. Call the configured LLM to produce a Russian-language Markdown digest.
9. The LLM must return sections: brief summary, thematic clusters, links and contradictions, top-3 priorities, authors summary, open questions.
10. NEW: for each of the top-3 priorities, append the hint: "👉 Промоть в задачу: промоть #<id>"
11. If the LLM call fails, fall back to a flat list grouped by author.
12. Split the final text into chunks (under 3800 chars each).
13. NEW: if some ideas in the period are already promoted, append a note: "💡 За период промоучено в задачи: N."

## Output

- A dict with header, chunks, total, authors, days, period, llm_used, promoted_count.

## Edge cases

- Empty result: "No ideas for the selected period."
- LLM unreachable: flat list grouped by author, header prefixed with [no LLM].
- All top ideas already promoted: return a chunk indicating that and the promoted count.

## ⭐ Связь с idea-tools (op=promote)

When the user says "промоть #abc123" (or "make this idea a task"):
1. Call idea-tools with op=promote, id=abc123.
2. idea-tools creates a task entry and tags the note as promoted.
3. Return confirmation: "Idea #abc123 became task #42 in the task-tracker."

In subsequent show-ideas calls, this idea is filtered out and will not appear in top-3.

## File touched

- Reads: `memory/notes.jsonl`
- Writes: nothing
