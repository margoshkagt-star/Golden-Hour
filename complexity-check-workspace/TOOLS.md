# TOOLS.md — Complexity Check Notes

## What you have

In your `tools.allow` (per `openclaw.json`):
- `read` — listed, but you don't use it; task is in your context
- `web_search` — listed, but you don't use it; you'd just add latency
- `web_fetch` — listed, but you don't use it; same

In your `tools.deny`:
- everything else, including `write`, `edit`, `apply_patch`, `exec`, `process`, `message`, `cron`, `sessions_*`, `image_*`, `music_*`, `video_*`, `skill_workshop`, `update_*`, `create_*`, `get_*`

## What this means in practice

You can NOT do anything. The only output you can produce is text in your final assistant message. That text MUST be the JSON verdict object, and nothing else.

If you find yourself trying to call a tool, you are wrong. Stop. Return the verdict.

## Subagent template

The auditor role and the JSON schema live at:
`~/.openclaw/workspace-code/agents/complexity-check.md`

The parent pastes that template into the spawn call. You don't read it yourself — it was already part of your spawn prompt.
