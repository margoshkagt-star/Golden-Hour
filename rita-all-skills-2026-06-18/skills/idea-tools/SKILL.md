---
name: "idea-tools"
description: "Operate on ideas: source, related, find, tag, untag, tags, tasks, stats, promote."
revision: 3
revision_note: "Add op=promote for V-LU-4 fix."
author: karim
status_source: karim-handcraft
---

# idea-tools

Operate on the existing idea collection. Read-only viewing plus manual tag edits and idea-to-task conversion.

## When to use

Use when the user wants to view, search, or manage ideas.

## Operations

- `source` (id): show full text of one idea
- `related` (id): find semantically related ideas
- `find` (query): semantic search across ideas
- `tag` / `untag` (id, tag): add or remove a manual tag
- `tags`: list top tags
- `tasks` (period): show high-importance ideas
- `stats`: activity statistics
- `promote` (id, category, deadline, weight): convert an idea into a task in the task-tracker

## `promote` operation

Convert an idea into a tracked task.

Inputs:
- `id` (required): idea id
- `category` (optional, default: idea-to-task)
- `deadline` (optional)
- `weight` (optional, default: importance multiplied by 2, clamped to 1-10)

Algorithm:
1. Look up the idea record by id.
2. Refuse if not found, or if is_idea is false, or if already promoted.
3. Create a new task entry in the task-tracker with: name (first 100 chars of idea content), category, weight, deadline, status=planned, progress=0, source=idea-promote, promoted_from_idea=id.
4. Tag the original idea as `promoted` and record the new task id.
5. Return confirmation: idea #abc123 became task #42 in the tracker.

Edge cases:
- Idea not found: "Idea #X not found."
- Not an idea (is_idea=false): "This is noise, not an idea. Nothing to promote."
- Already promoted: "This idea is already task #Y. No duplicate."

## Other operations

- `source` returns: id, timestamp, author, topic, importance, tags, content.
- `find` returns top 5 matches with score and reason.
- `tag` adds a tag (sorted set).
- `tasks` filters by importance >= 4.

## File touched

- Reads and writes: `memory/notes.jsonl` (append or update lines).
- The `promote` operation additionally writes to the task-tracker store.
