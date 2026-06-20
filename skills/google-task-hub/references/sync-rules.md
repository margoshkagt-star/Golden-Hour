# sync-rules.md

## Sync IN (Google Tasks → Sheet)

Запускается каждые 15 минут (cron) или вручную (`sync_in.py`).

```
1. LIST все task lists → для каждой LIST tasks
2. Сопоставить по google_task_id:
   - если completed в Tasks и progress<100 в Sheet → progress=100, status=done, closed_at=now
   - если title/notes изменились → обновить name в Sheet
   - если задача в Tasks, но нет в Sheet → INSERT (weight=1, progress=0, status=planned, task_type=short)
3. updated_at = now
```

## Sync OUT (Sheet → Google Tasks)

Запускается при `progress` / `urgent` / `day-end` / ручном обновлении.

```
1. PATCH task: title (с emoji/%), due (date part of deadline), notes, status
2. Если progress=100 → completed=true
3. Если calendar_deadline_event_id пуст и deadline есть → CREATE calendar event, записать id
4. Если checkpoints изменились → upsert calendar events для каждого КТ
5. Регенерировать Dashboard Short/Long (если были изменения)
```

## Title format в Google Tasks

| status | title в Tasks |
|--------|---------------|
| planned | `name` |
| in_progress | `🔵 60% ▸ name` |
| done | `name` (completed=true) |
| blocked | `🚫 name` |
| overdue | `⚠️ name` |

## Notes format

```
id:42  |  вес 7  |  50%
```

или для long:
```
id:42  |  long  |  вес 7  |  30%
```

## Priority конфликты

Если Sheet и Tasks оба изменились между sync — побеждает Sheet (последняя запись). Лог конфликтов в `state/sync-conflicts.jsonl` (опционально, Phase 3).
