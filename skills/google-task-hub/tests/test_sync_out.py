"""test_sync_out.py — проверяем sync_out в mock-режиме."""

from scripts import state_manager
from scripts.google_api_client import GoogleAPIClient
from scripts.sync_in import run_sync as run_sync_in
from scripts.sync_out import run_sync as run_sync_out, format_title, format_notes


def test_format_title():
    assert format_title("Foo", "in_progress", 60) == "🔵 60% ▸ Foo"
    assert format_title("Foo", "blocked", 0) == "🚫 Foo"
    assert format_title("Foo", "overdue", 30) == "⚠️ Foo"
    assert format_title("Foo", "planned", 0) == "Foo"


def test_format_notes_long():
    assert format_notes(42, 7, 50, "long") == "id:42 | long | вес 7 | 50%"


def test_format_notes_short():
    assert format_notes(5, 3, 30, "short") == "id:5 | вес 3 | 30%"


def test_sync_out_creates_calendar_events_for_deadlines(temp_config):
    cfg = state_manager.load_config(temp_config)
    api = GoogleAPIClient(cfg)

    # 1. Сначала делаем sync_in — задачи появятся в Sheet
    run_sync_in(api, cfg)

    # 2. sync_out — задачи с deadline должны попасть в Calendar
    stats = run_sync_out(api, cfg)

    assert stats["updated"] >= 1
    assert stats["inserted"] == 0  # все уже имели google_task_id после sync_in
    assert stats["events_created"] >= 1  # хотя бы один deadline

    events = api.calendar_list()
    assert len(events) >= 1
    # Проверяем структуру
    e = events[0]
    assert "summary" in e
    assert "start" in e
    assert "description" in e
    assert "task_id:" in e["description"]


def test_sync_out_updates_title_with_emoji(temp_config):
    """Если в Sheet статус=in_progress, в Tasks title получает emoji и progress."""
    import json
    from pathlib import Path

    cfg = state_manager.load_config(temp_config)
    api = GoogleAPIClient(cfg)
    run_sync_in(api, cfg)

    # Меняем в Sheet статус одной задачи на in_progress
    rows = api.sheet_get("Tasks")
    headers = rows[0]
    gtask_idx = headers.index("google_task_id")
    name_idx = headers.index("name")
    status_idx = headers.index("status")
    progress_idx = headers.index("progress")

    for r in rows[1:]:
        if r[name_idx] == "Прочитать учебник по ML":
            r[status_idx] = "in_progress"
            r[progress_idx] = "75"
            break

    api.sheet_set("Tasks", [headers] + [r + [""] * (len(headers) - len(r)) for r in rows[1:]])

    # sync_out
    run_sync_out(api, cfg)

    # Проверяем, что в Tasks title обновился
    long_tasks = api.list_tasks("list_long_1")
    ml_task = next(t for t in long_tasks if "учебник" in t["title"])
    assert ml_task["title"].startswith("🔵")
    assert "75%" in ml_task["title"]
