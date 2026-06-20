"""test_sync_in.py — проверяем sync_in в mock-режиме."""

from scripts import state_manager
from scripts.google_api_client import GoogleAPIClient
from scripts.sync_in import run_sync, parse_notes, task_title_status, _strip_emoji_title


def test_parse_notes_long():
    parsed = parse_notes("id:42 | long | вес 7 | 50%")
    assert parsed == {"task_id": 42, "task_type": "long", "weight": 7, "progress": 50}


def test_parse_notes_short():
    parsed = parse_notes("id:5 | вес 3 | 30%")
    assert parsed == {"task_id": 5, "task_type": "short", "weight": 3, "progress": 30}


def test_parse_notes_empty():
    assert parse_notes("") == {}
    assert parse_notes("мусор без полей") == {}


def test_task_title_status():
    assert task_title_status("🔵 60% ▸ foo") == "in_progress"
    assert task_title_status("🚫 foo") == "blocked"
    assert task_title_status("⚠️ foo") == "overdue"
    assert task_title_status("foo") == "planned"


def test_strip_emoji_title():
    assert _strip_emoji_title("🔵 30% ▸ Подготовить проект") == "Подготовить проект"
    assert _strip_emoji_title("🚫 Задача") == "Задача"
    assert _strip_emoji_title("⚠️ Срочное") == "Срочное"
    assert _strip_emoji_title("Обычное название") == "Обычное название"


def test_sync_in_inserts_tasks_from_mock(temp_config):
    cfg = state_manager.load_config(temp_config)
    api = GoogleAPIClient(cfg)

    # Sheet пуст (только заголовок)
    rows = api.sheet_get("Tasks")
    assert len(rows) == 1  # только заголовок

    stats = run_sync(api, cfg)
    assert stats["scanned"] == 7  # 3 long + 4 short
    assert stats["inserted"] == 7
    assert stats["updated"] == 0
    assert stats["closed"] == 0

    # Проверяем, что Sheet заполнен
    rows = api.sheet_get("Tasks")
    assert len(rows) == 1 + 7  # заголовок + 7 задач
    headers = rows[0]
    name_idx = headers.index("name")
    type_idx = headers.index("task_type")
    progress_idx = headers.index("progress")

    names = [r[name_idx] for r in rows[1:]]
    assert "Подготовить проект Golden-Hour" in names  # emoji снято
    types = [r[type_idx] for r in rows[1:]]
    assert types.count("long") == 3
    assert types.count("short") == 4


def test_sync_in_idempotent(temp_config):
    """Повторный sync не должен дублировать задачи."""
    cfg = state_manager.load_config(temp_config)
    api = GoogleAPIClient(cfg)
    run_sync(api, cfg)  # первый раз
    stats2 = run_sync(api, cfg)  # второй раз

    assert stats2["inserted"] == 0
    assert stats2["updated"] == 0

    rows = api.sheet_get("Tasks")
    assert len(rows) == 1 + 7


def test_sync_in_closes_completed(temp_config):
    """Если в Tasks задача completed, а в Sheet progress<100 — закрыть."""
    import json
    from pathlib import Path

    # Помечаем одну задачу в mock как completed
    mock_dir = Path(cfg_path := temp_config).parent / "mock_store"
    long_list = mock_dir / "tasks" / "list_long_1.json"
    data = json.loads(long_list.read_text(encoding="utf-8"))
    data["items"][0]["status"] = "completed"
    data["items"][0]["completed"] = "2026-06-18T10:00:00Z"
    long_list.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg = state_manager.load_config(temp_config)
    api = GoogleAPIClient(cfg)
    run_sync(api, cfg)

    # Найти эту задачу в Sheet и проверить
    rows = api.sheet_get("Tasks")
    headers = rows[0]
    gtask_idx = headers.index("google_task_id")
    progress_idx = headers.index("progress")
    status_idx = headers.index("status")

    for r in rows[1:]:
        if r[gtask_idx] == "task_1_list_long_1":
            assert r[progress_idx] == "100"
            assert r[status_idx] == "done"
            break
    else:
        raise AssertionError("Task not found in Sheet")
