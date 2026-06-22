"""state_manager.py — управление конфигом и runtime state.

Конфиг: state/google-task-hub.json
Runtime: state/runtime/ (создаётся при первом sync, не коммитится)
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "openclaw.google-task-hub.config.v1"

DEFAULT_CONFIG: dict[str, Any] = {
    "schema": SCHEMA_VERSION,
    "mode": "mock",  # mock | real
    "spreadsheet_id": None,
    "task_list_id": None,
    "calendar_id": "primary",
    "list_mappings": {
        "short": {"category": None, "task_list_id": None},
        "long": {"task_list_id": None},
    },
    "scopes": [
        "https://www.googleapis.com/auth/tasks",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/calendar.events",
    ],
    "credentials_path": "~/.openclaw/credentials/google/client_secret.json",
    "token_path": "~/.openclaw/credentials/google/token.json",
    "mock_dir": "skills/google-task-hub/tests/fixtures/mock_store",
    "sync_interval_min": 15,
    "dashboard": {
        "short_sheet_name": "Dashboard Short",
        "long_sheet_name": "Dashboard Long",
        "checkpointlog_sheet_name": "CheckpointLog",
        "dailylog_sheet_name": "DailyLog",
    },
}


def expand_path(p: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(p))).resolve()


def load_config(config_path: str | Path) -> dict[str, Any]:
    """Загрузить конфиг или вернуть дефолтный."""
    p = expand_path(config_path)
    if not p.exists():
        return deepcopy(DEFAULT_CONFIG)
    with p.open(encoding="utf-8") as f:
        cfg = json.load(f)
    # Мерж дефолтов (если в конфиге пропущены новые поля)
    merged = deepcopy(DEFAULT_CONFIG)
    merged.update(cfg)
    return merged


def save_config(config_path: str | Path, cfg: dict[str, Any]) -> None:
    p = expand_path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def is_real_mode(cfg: dict[str, Any]) -> bool:
    return cfg.get("mode") == "real"


def get_credentials_path(cfg: dict[str, Any]) -> Path:
    return expand_path(cfg["credentials_path"])


def get_token_path(cfg: dict[str, Any]) -> Path:
    return expand_path(cfg["token_path"])


def get_mock_dir(cfg: dict[str, Any]) -> Path:
    return expand_path(cfg["mock_dir"])
