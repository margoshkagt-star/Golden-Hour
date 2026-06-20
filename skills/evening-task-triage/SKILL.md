---
name: "evening-task-triage"
description: "Triage multiple end-of-day tasks: capture, prioritize, time-estimate, persist to dated plan, fact-check external guides, schedule follow-ups."
---

# Evening Task Triage

**Use when:** the user shows up with multiple tasks in their head, a vague "I have a lot to do" feeling, or a half-finished list — typically at the end of the day, possibly tired or stressed.

**Don't use when:** the user has one specific, clear task (just do it), or it's morning energy work and they want to execute (also just do it).

## Why this skill exists

Most assistants, when faced with a chaotic multi-task situation, do one of these:

- Dive into the first task and ignore the rest.
- Interrogate with 10+ questions before starting.
- Promise to do everything tonight, deliver nothing useful.

This skill is a different shape: turn "каша в голове" into a **dated, persisted, evolvable plan** that survives the session and supports follow-ups.

## Procedure

### 1. Capture, don't interrogate

- User dumps whatever they have — bullet points, brain dump, half-sentences.
- Don't ask for completeness; trust them to add more later.
- Acknowledge each item briefly.

### 2. Group by domain (optional but useful)

- Coding, infra, content, personal, admin.
- Helps with energy budgeting and switching costs.

### 3. For each task, capture

- Title (1 line)
- "What done looks like" (1 sentence)
- Rough estimate (use ranges: 10–20 min, 60–180 min, etc.)
- Blockers / open questions
- Status: tonight / tomorrow / later / plan (not scheduled)

### 4. Identify blocking questions

- Pick 2–3 critical ones — those that prevent accurate estimation.
- Don't interrogate for every detail.
- Mark non-critical as "defer to execution".

### 5. Prioritize and order

- Quick wins first (renames, account creations, small fixes).
- Deep work in the middle (while energy is highest).
- Background / fragile work last (Docker downloads, large builds, network-heavy ops).

### 6. Persist to dated file

- `evening-plan-YYYY-MM-DD.md` in workspace.
- Structure: header (date, status, time budget), task list with metadata, blockers, notes, follow-ups.
- **Live document** — update as tasks complete or new ones appear.

### 7. Register "list on demand" command

- "Say 'list upcoming tasks' (or close variant) and I'll dump the file."
- Tiny thing, psychologically huge: user knows nothing is lost.

### 8. Create reference docs for complex topics

- `topic-guide.md` in workspace for each major topic (Docker, etc.).
- Beginner-friendly, structured, visual.
- Don't repeat in chat — point to file.

### 9. Reality-check external instructions

- If user shares a guide/instructions from another source, fact-check against:
  - Official docs (in workspace: `docs/`)
  - Actual system state (use `exec` to inspect)
- Point out errors kindly; don't pretend they're right.
- Save corrected version to a file when material.

### 10. Schedule tomorrow's follow-ups

- Use `cron` with `schedule.kind: "at"` for one-shot reminder.
- ISO timestamp with explicit timezone offset (e.g. `2026-06-16T15:30:00+03:00`).
- `sessionTarget: "main"`, `payload.kind: "systemEvent"`, friendly contextual text.
- Confirm in chat that the cron is set.

### 11. Sign off

- Acknowledge the time.
- Confirm presence tomorrow.
- Don't push for more work.

## Anti-patterns

- ❌ "Let me ask you 10 questions before we start" — pick 2–3 blockers max.
- ❌ "Sure I'll do it all tonight!" — when it's clearly too much.
- ❌ Blindly trusting instructions from other AIs / sources.
- ❌ Lecturing about the importance of planning.
- ❌ Generic "good night" without confirming the file/path/cron are in place.
- ❌ Asking "should I...?" for tiny reversible actions when defaulting is safe.
- ❌ Paternalistic "go to bed, close the laptop" tone toward adult users.

## Templates

### `evening-plan-YYYY-MM-DD.md`

```markdown
# Вечерний план · YYYY-MM-DD

**Создан:** HH:MM GMT+3
**Обновлён:** HH:MM GMT+3
**Статус:** ...
**Команда «выдай список предстоящих задач»:** активна

---

## Список задач

### N · Title
- **Что:** ...
- **Время:** X–Y мин
- **Статус:** ...
- **Когда:** ...
- **Заметки:** ...

## Блокеры и открытые вопросы
- ...

## Cron-напоминания
- ...
```

### `memory/YYYY-MM-DD.md` (raw session log)

Short, factual, captures: what happened, what was decided, observations about user, open questions for next session. Not curated — that's what `MEMORY.md` is for.

## Related

- `cron` — for one-shot and recurring reminders
- `skill_workshop` — for capturing reusable workflows
- AGENTS.md "Daily notes" — raw log conventions
- AGENTS.md "MEMORY.md" — curated long-term memory
