# team-tasks — data schema

All timestamps: **UTC ISO-8601** with `+00:00` suffix.

## `data/teams/<team_id>/meta.json`

```json
{
  "team_id": "team-a1b2c3d4",
  "goal": "Собрать Q&A сайт к 1 сентября",
  "owner_user_key": "tg-5649925712",
  "owner_telegram_id": 5649925712,
  "created_at": "2026-06-17T15:00:00+00:00"
}
```

## `members.json`

```json
{
  "members": [
    {
      "user_key": "tg-5649925712",
      "telegram_id": 5649925712,
      "username": "@alice",
      "role": "owner",
      "joined_at": "2026-06-17T15:00:00+00:00"
    },
    {
      "user_key": "tg-999888777",
      "telegram_id": 999888777,
      "username": "@bob",
      "role": "member",
      "joined_at": "2026-06-18T10:00:00+00:00"
    }
  ]
}
```

- `user_key` — primary identity (`tg-<telegram_id>`)
- `telegram_id` — immutable key for matching invites
- `username` — display only, may change

## `invites.json`

```json
{
  "invites": [
    {
      "invite_code": "a1b2c3d4",
      "created_by": "tg-5649925712",
      "target_telegram_id": 999888777,
      "target_username": "@bob",
      "created_at": "2026-06-17T15:00:00+00:00",
      "expires_at": "2026-06-22T15:00:00+00:00",
      "status": "pending"
    }
  ]
}
```

`status`: `pending` | `accepted` | `expired`

TTL: **5 days** from `created_at` (UTC).

## `tasks.json`

```json
{
  "tasks": [
    {
      "id": "task-001",
      "title": "Верстка главной",
      "description": "",
      "status": "in_progress",
      "assignee_user_key": "tg-999888777",
      "assignee_telegram_id": 999888777,
      "created_by": "tg-5649925712",
      "created_at": "2026-06-17T16:00:00+00:00",
      "deadline": "2026-06-27T15:00:00+00:00",
      "submit_at": null,
      "submit_note": null,
      "approved_at": null,
      "blocked_reason": null
    }
  ],
  "next_id": 2
}
```

`status`: `planned` | `in_progress` | `awaiting_review` | `done` | `blocked`

`display_status` (computed, not stored): adds `overdue` when deadline passed and status ∉ {done, awaiting_review}.

## `users/<user_key>/teams.json`

```json
{
  "teams": [
    {
      "team_id": "team-a1b2c3d4",
      "role": "owner",
      "joined_at": "2026-06-17T15:00:00+00:00"
    }
  ]
}
```

## `notifications.log` (append-only, owner read)

One JSON object per line:

```json
{"at":"2026-06-17T16:05:00+00:00","type":"task_taken","task_id":"task-001","by":"tg-999888777"}
```
