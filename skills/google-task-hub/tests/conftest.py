"""conftest.py — pytest fixtures для google-task-hub.

Делает:
- SKILL_DIR: путь к навыку
- MOCK_DIR: путь к mock_store
- temp_config: временный конфиг с mode=mock
- reset_mock_store: чистит mock_store перед каждым тестом
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
MOCK_STORE_SRC = SKILL_DIR / "tests" / "fixtures" / "mock_store"

sys.path.insert(0, str(SKILL_DIR))


@pytest.fixture
def skill_dir() -> Path:
    return SKILL_DIR


@pytest.fixture
def mock_dir(tmp_path: Path) -> Path:
    """Копия mock_store в tmp_path, чтобы тесты не портили общий."""
    dest = tmp_path / "mock_store"
    shutil.copytree(MOCK_STORE_SRC, dest)
    return dest


@pytest.fixture
def temp_config(tmp_path: Path, mock_dir: Path) -> Path:
    """Временный конфиг, указывающий на копию mock_store."""
    cfg = {
        "schema": "openclaw.google-task-hub.config.v1",
        "mode": "mock",
        "spreadsheet_id": "mock_spreadsheet_1",
        "task_list_id": "list_long_1",
        "calendar_id": "primary",
        "list_mappings": {
            "short": {"category": "Work", "task_list_id": "list_short_1"},
            "long": {"task_list_id": "list_long_1"},
        },
        "scopes": [
            "https://www.googleapis.com/auth/tasks",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/calendar.events",
        ],
        "credentials_path": str(tmp_path / "client_secret.json"),
        "token_path": str(tmp_path / "token.json"),
        "mock_dir": str(mock_dir),
        "sync_interval_min": 15,
        "dashboard": {
            "short_sheet_name": "Dashboard Short",
            "long_sheet_name": "Dashboard Long",
            "checkpointlog_sheet_name": "CheckpointLog",
            "dailylog_sheet_name": "DailyLog",
        },
    }
    p = tmp_path / "google-task-hub.json"
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
