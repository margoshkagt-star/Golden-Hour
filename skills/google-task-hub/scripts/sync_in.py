"""sync_in.py — Google Tasks → Sheet (входящая синхронизация).

Алгоритм:
1. LIST task lists → для каждой LIST tasks
2. Сопоставить по google_task_id с Sheet.Tasks
3. Если completed в Tasks и progress<100 → закрыть
4. Если title/notes изменились → обновить name
5. Если задача в Tasks, но нет в Sheet → INSERT (weight=1, status=planned)

Запуск:
    py scripts/sync_in.py
    py scripts/sync_in.py --mock
"""

from __future__ import annotations

import argparse
import json
import re
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


NOTES_RE = re.compile(r"id:(\d+)(?:\s*\|\s*(long))?\s*\|\s*вес\s*(\d+)\s*\|\s*(\d+)%")


def parse_notes(notes: str) -> dict:
    """Парсит поле notes Google Tasks → поля Sheet.

    Формат: 'id:42 | long | вес 7 | 50%' или 'id:42 | вес 5 | 30%'
    """
    if not notes:
        return {}
    m = NOTES_RE.search(notes)
    if not m:
        return {}
    return {
        "task_id": int(m.group(1)),
        "task_type": "long" if m.group(2) else "short",
        "weight": int(m.group(3)),
        "progress": int(m.group(4)),
    }


def sheet_to_dicts(rows: list[list]) -> list[dict]:
    if not rows:
        return []
    headers = rows[0]
    return [dict(zip(headers, r)) for r in rows[1:] if r]


def find_existing(sheet_rows: list[dict], google_task_id: str) -> dict | None:
    for row in sheet_rows:
        if row.get("google_task_id") == google_task_id:
            return row
    return None


def task_title_status(title: str) -> str:
    """Определяем статус по title (emoji)."""
    if title.startswith("🔵"):
        return "in_progress"
    if title.startswith("🚫"):
        return "blocked"
    if title.startswith("⚠️"):
        return "overdue"
    return "planned"


def run_sync(api: GoogleAPIClient, cfg: dict) -> dict:
    sheet_rows = api.sheet_get("Tasks")
    sheet_dicts = sheet_to_dicts(sheet_rows)
    stats = {"scanned": 0, "updated": 0, "inserted": 0, "closed": 0}

    headers = sheet_rows[0] if sheet_rows else [
        "task_id", "google_task_id", "google_list_id", "name", "category",
        "weight", "deadline", "status", "progress", "actual_duration",
        "estimated_duration", "task_type", "checkpoints",
        "calendar_deadline_event_id", "closed_at", "updated_at",
    ]

    tasklists = api.list_tasklists()
    next_id = max((int(d.get("task_id") or 0) for d in sheet_dicts), default=0) + 1
    updated_rows: list[dict] = {tuple(d.get(k) for k in ("google_task_id",)): d for d in sheet_dicts if d.get("google_task_id")}

    out: list[dict] = list(sheet_dicts)

    for tl in tasklists:
        tl_id = tl["id"]
        tl_title = tl.get("title", "")
        tasks = api.list_tasks(tl_id)
        for t in tasks:
            stats["scanned"] += 1
            gtid = t["id"]
            title = t.get("title", "")
            notes = t.get("notes", "")
            existing = find_existing(sheet_dicts, gtid)
            inferred_status = task_title_status(title)
            is_completed = t.get("status") == "completed"

            if existing:
                # Update
                if is_completed and int(existing.get("progress") or 0) < 100:
                    existing["progress"] = 100
                    existing["status"] = "done"
                    existing["closed_at"] = t.get("completed") or "now"
                    stats["closed"] += 1
                if title and existing.get("name") != _strip_emoji_title(title):
                    existing["name"] = _strip_emoji_title(title)
                    stats["updated"] += 1
                # weight/progress из notes, если есть
                parsed = parse_notes(notes)
                if parsed and int(existing.get("weight") or 0) != parsed["weight"]:
                    existing["weight"] = parsed["weight"]
                    stats["updated"] += 1
            else:
                # Insert
                parsed = parse_notes(notes)
                row = {
                    "task_id": next_id,
                    "google_task_id": gtid,
                    "google_list_id": tl_id,
                    "name": _strip_emoji_title(title),
                    "category": tl_title,
                    "weight": parsed.get("weight", 1),
                    "deadline": (t.get("due") or ""),
                    "status": "done" if is_completed else inferred_status,
                    "progress": 100 if is_completed else parsed.get("progress", 0),
                    "actual_duration": "",
                    "estimated_duration": "",
                    "task_type": parsed.get("task_type", "short"),
                    "checkpoints": "",
                    "calendar_deadline_event_id": "",
                    "closed_at": t.get("completed") or "",
                    "updated_at": "now",
                }
                out.append(row)
                next_id += 1
                stats["inserted"] += 1

    # Записать обратно
    out_rows = [headers] + [[_s(r.get(h, "")) for h in headers] for r in out]
    api.sheet_set("Tasks", out_rows)
    return stats


def _strip_emoji_title(title: str) -> str:
    """Убираем префиксы '🔵 60% ▸ ', '🚫 ', '⚠️ ' из title."""
    return re.sub(r"^(🔵\s*\d+%\s*▸\s*|🚫\s*|⚠️\s*)", "", title).strip()


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
    print(f"✅ sync_in завершён. Stats: {stats}")


if __name__ == "__main__":
    main()
