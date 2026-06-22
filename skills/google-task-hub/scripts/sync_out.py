"""sync_out.py — Sheet → Google Tasks (исходящая синхронизация).

Алгоритм:
1. Прочитать Sheet.Tasks
2. Для каждой строки с google_task_id:
   - PATCH task: title (с emoji/%), notes, status
   - Если status=done и нет completed → completed=true
   - Если есть deadline и нет calendar event → CREATE event
3. Для строк без google_task_id (новые) → INSERT task

Запуск:
    py scripts/sync_out.py
    py scripts/sync_out.py --mock
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# Windows cp1251: включить UTF-8 для emoji в print
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import state_manager
from scripts.google_api_client import GoogleAPIClient


def format_title(name: str, status: str, progress: int) -> str:
    """Title для Google Tasks по статусу и прогрессу."""
    if status == "in_progress":
        return f"🔵 {progress}% ▸ {name}"
    if status == "blocked":
        return f"🚫 {name}"
    if status == "overdue":
        return f"⚠️ {name}"
    return name


def format_notes(task_id: int, weight: int, progress: int, task_type: str) -> str:
    if task_type == "long":
        return f"id:{task_id} | long | вес {weight} | {progress}%"
    return f"id:{task_id} | вес {weight} | {progress}%"


def run_sync(api: GoogleAPIClient, cfg: dict) -> dict:
    sheet_rows = api.sheet_get("Tasks")
    if not sheet_rows:
        print("Sheet.Tasks пуст, нечего синхронизировать.")
        return {"updated": 0, "inserted": 0, "events_created": 0}

    headers = sheet_rows[0]
    rows = [dict(zip(headers, r)) for r in sheet_rows[1:] if r]
    stats = {"updated": 0, "inserted": 0, "events_created": 0}

    long_list_id = (cfg.get("list_mappings") or {}).get("long", {}).get("task_list_id") or cfg.get("task_list_id")
    short_list_id = (cfg.get("list_mappings") or {}).get("short", {}).get("task_list_id") or cfg.get("task_list_id")

    for r in rows:
        task_id = r.get("task_id")
        name = r.get("name") or ""
        status = r.get("status") or "planned"
        progress = int(r.get("progress") or 0)
        weight = int(r.get("weight") or 1)
        task_type = r.get("task_type") or "short"
        deadline = r.get("deadline") or ""
        gtask_id = r.get("google_task_id")
        glist_id = r.get("google_list_id")
        cal_id = r.get("calendar_deadline_event_id")

        if not name:
            continue

        target_list = long_list_id if task_type == "long" else (glist_id or short_list_id)
        if not target_list:
            print(f"  ⚠ task_id={task_id}: нет list_id, пропуск")
            continue

        title = format_title(name, status, progress)
        notes = format_notes(int(task_id or 0), weight, progress, task_type)
        body = {"title": title, "notes": notes}
        if deadline:
            body["due"] = deadline

        if status == "done":
            body["status"] = "completed"
        else:
            body["status"] = "needsAction"

        try:
            if gtask_id:
                api.patch_task(target_list, gtask_id, body)
                stats["updated"] += 1
            else:
                inserted = api.insert_task(target_list, body)
                r["google_task_id"] = inserted["id"]
                r["google_list_id"] = target_list
                stats["inserted"] += 1
        except Exception as e:
            print(f"  ⚠ task_id={task_id}: {e}")

        # Calendar event для дедлайна
        if deadline and not cal_id and status != "done":
            try:
                event = api.calendar_insert({
                    "summary": f"⚠️ Дедлайн: {name}",
                    "start": {"dateTime": deadline, "timeZone": "Europe/Moscow"},
                    "end": {"dateTime": deadline, "timeZone": "Europe/Moscow"},
                    "description": f"task_id:{task_id}",
                })
                r["calendar_deadline_event_id"] = event["id"]
                stats["events_created"] += 1
            except Exception as e:
                print(f"  ⚠ task_id={task_id} (event): {e}")

    # Записать обновлённые google_task_id обратно
    api.sheet_set("Tasks", [headers] + [[_s(r.get(h, "")) for h in headers] for r in rows])
    return stats


def _s(v: Any) -> str:
    if v is None or v == "":
        return ""
    return str(v)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true")
    p.add_argument("--config", default="state/google-task-hub.json")
    args = p.parse_args()

    config_path = Path(args.config)
    cfg = state_manager.load_config(config_path)
    if args.mock:
        cfg["mode"] = "mock"

    api = GoogleAPIClient(cfg)
    stats = run_sync(api, cfg)
    print(f"✅ sync_out завершён. Stats: {stats}")


if __name__ == "__main__":
    main()
