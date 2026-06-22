"""auth_setup.py — OAuth setup + создание Spreadsheet/Task list.

Запуск:
    py scripts/auth_setup.py                 # interactive, требует client_secret.json
    py scripts/auth_setup.py --mock          # mock-режим (без credentials)
    py scripts/auth_setup.py --create-only   # только создать assets, без auth

Создаёт:
    - Spreadsheet «Golden Hour Tasks» с листами Tasks / Dashboard Short / Dashboard Long / CheckpointLog / DailyLog
    - Task list «Golden Hour» (если list_mappings пустые)
    - Записывает IDs в state/google-task-hub.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows cp1251: включить UTF-8 для emoji в print
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# чтобы импортировать scripts.* при запуске из любой директории
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import state_manager


SHEET_HEADERS = [
    "task_id", "google_task_id", "google_list_id", "name", "category",
    "weight", "deadline", "status", "progress", "actual_duration",
    "estimated_duration", "task_type", "checkpoints",
    "calendar_deadline_event_id", "closed_at", "updated_at",
]


def make_default_spreadsheet_rows() -> dict[str, list[list]]:
    """Структура пустой таблицы с заголовками."""
    tasks_header = [SHEET_HEADERS]
    dashboard_short = [
        ["# Dashboard Short"],
        [],
        ["## Сегодня"],
        # строки добавятся render_dashboard.py
    ]
    dashboard_long = [
        ["# Dashboard Long"],
        [],
        ["## Долговременные задачи"],
    ]
    return {
        "Tasks": tasks_header,
        "Dashboard Short": dashboard_short,
        "Dashboard Long": dashboard_long,
        "CheckpointLog": [["timestamp", "task_id", "target_progress", "actual_progress", "status"]],
        "DailyLog": [["date", "tasks_done", "hours_spent", "weight_done", "top_categories"]],
    }


def setup_mock(cfg: dict, config_path: Path) -> dict:
    """Создать mock-assets в state/runtime/mock_store/ (НЕ в tests/fixtures)."""
    runtime_dir = state_manager.expand_path("state/runtime/mock_store")
    cfg["mock_dir"] = str(runtime_dir)
    print(f"[mock] Создаю мок-активы в {runtime_dir}")
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "tasks").mkdir(parents=True, exist_ok=True)
    mock_dir = runtime_dir

    sheets = make_default_spreadsheet_rows()
    (mock_dir / "spreadsheet.json").write_text(
        json.dumps({"sheets": sheets}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Task lists
    (mock_dir / "tasklists.json").write_text(
        json.dumps({"items": [
            {"id": "list_long_1", "title": "Долговременные задачи"},
            {"id": "list_short_1", "title": "Work"},
        ]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # Демо-задачи
    tasks_long = {
        "items": [
            {"id": "task_1_list_long_1", "title": "Подготовить проект Golden-Hour", "notes": "id:1 | long | вес 8 | 30%",
             "status": "needsAction", "due": "2026-09-01T00:00:00Z"},
            {"id": "task_2_list_long_1", "title": "Сдать ЕГЭ по информатике", "notes": "id:2 | long | вес 10 | 0%",
             "status": "needsAction", "due": "2027-06-20T00:00:00Z"},
        ],
    }
    (mock_dir / "tasks" / "list_long_1.json").write_text(
        json.dumps(tasks_long, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    tasks_short = {
        "items": [
            {"id": "task_1_list_short_1", "title": "Сделать домашку по физике", "notes": "id:3 | вес 5 | 0%",
             "status": "needsAction", "due": "2026-06-20T00:00:00Z"},
            {"id": "task_2_list_short_1", "title": "Пробежка 5 км", "notes": "id:4 | вес 2 | 50%",
             "status": "needsAction", "due": "2026-06-18T20:00:00Z"},
        ],
    }
    (mock_dir / "tasks" / "list_short_1.json").write_text(
        json.dumps(tasks_short, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    # Calendar
    (mock_dir / "calendar_events.json").write_text(
        json.dumps({"items": []}, ensure_ascii=False, indent=2), encoding="utf-8",
    )

    # Обновить конфиг
    cfg["spreadsheet_id"] = "mock_spreadsheet_1"
    cfg["task_list_id"] = "list_long_1"
    cfg["list_mappings"]["long"]["task_list_id"] = "list_long_1"
    cfg["list_mappings"]["short"]["category"] = "Work"
    cfg["list_mappings"]["short"]["task_list_id"] = "list_short_1"
    state_manager.save_config(config_path, cfg)
    print(f"[mock] Конфиг обновлён: {config_path}")
    return cfg


def setup_real(cfg: dict, config_path: Path) -> dict:
    """Реальный setup: OAuth, создание Spreadsheet + Task list."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds_path = state_manager.get_credentials_path(cfg)
    token_path = state_manager.get_token_path(cfg)
    if not creds_path.exists():
        print(f"❌ client_secret.json не найден: {creds_path}")
        print("Скачай OAuth client (Desktop app) из Google Cloud Console и положи сюда.")
        sys.exit(1)

    print(f"[real] OAuth flow с {creds_path}")
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), cfg["scopes"])
    creds = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"[real] Token сохранён: {token_path}")

    # Spreadsheet
    print("[real] Создаю Spreadsheet «Golden Hour Tasks»…")
    sheets_service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    spreadsheet = {
        "properties": {"title": "Golden Hour Tasks"},
        "sheets": [
            {"properties": {"title": name}} for name in [
                "Tasks", "Dashboard Short", "Dashboard Long", "CheckpointLog", "DailyLog",
            ]
        ],
    }
    ss = sheets_service.spreadsheets().create(body=spreadsheet, fields="spreadsheetId").execute()
    cfg["spreadsheet_id"] = ss["spreadsheetId"]
    print(f"[real] Spreadsheet ID: {ss['spreadsheetId']}")

    # Заголовки в Tasks
    sheets_service.spreadsheets().values().update(
        spreadsheetId=cfg["spreadsheet_id"],
        range="Tasks!A1:P1",
        valueInputOption="RAW",
        body={"values": [SHEET_HEADERS]},
    ).execute()

    # Task list
    print("[real] Создаю Task list «Golden Hour»…")
    tasks_service = build("tasks", "v1", credentials=creds, cache_discovery=False)
    tl = tasks_service.tasklists().insert(body={"title": "Golden Hour"}).execute()
    cfg["task_list_id"] = tl["id"]
    cfg["list_mappings"]["long"]["task_list_id"] = tl["id"]
    print(f"[real] Task list ID: {tl['id']}")

    state_manager.save_config(config_path, cfg)
    return cfg


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true", help="использовать mock-режим")
    p.add_argument("--config", default="state/google-task-hub.json", help="путь к конфигу")
    args = p.parse_args()

    config_path = Path(args.config)
    cfg = state_manager.load_config(config_path)

    if args.mock or cfg.get("mode") == "mock":
        cfg["mode"] = "mock"
        cfg = setup_mock(cfg, config_path)
    else:
        cfg = setup_real(cfg, config_path)

    print("\n✅ Setup завершён.")
    print(f"   mode: {cfg['mode']}")
    print(f"   spreadsheet_id: {cfg.get('spreadsheet_id')}")
    print(f"   task_list_id: {cfg.get('task_list_id')}")


if __name__ == "__main__":
    main()
