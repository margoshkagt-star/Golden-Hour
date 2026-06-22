"""test_state_manager.py — проверяем state_manager."""

import json
from pathlib import Path

from scripts import state_manager


def test_load_config_returns_defaults_when_missing(tmp_path: Path):
    cfg = state_manager.load_config(tmp_path / "missing.json")
    assert cfg["mode"] == "mock"
    assert cfg["schema"] == state_manager.SCHEMA_VERSION
    assert "list_mappings" in cfg


def test_save_and_load_config(tmp_path: Path):
    p = tmp_path / "cfg.json"
    cfg = state_manager.load_config(p)
    cfg["mode"] = "real"
    cfg["spreadsheet_id"] = "abc123"
    state_manager.save_config(p, cfg)

    loaded = state_manager.load_config(p)
    assert loaded["mode"] == "real"
    assert loaded["spreadsheet_id"] == "abc123"


def test_load_config_merges_defaults(tmp_path: Path):
    """Если в сохранённом конфиге нет нового поля — должны подставиться дефолты."""
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"mode": "real", "spreadsheet_id": "x"}), encoding="utf-8")
    cfg = state_manager.load_config(p)
    assert cfg["mode"] == "real"
    assert cfg["spreadsheet_id"] == "x"
    # дефолтные поля подтянулись
    assert "list_mappings" in cfg
    assert cfg["sync_interval_min"] == 15


def test_is_real_mode():
    assert state_manager.is_real_mode({"mode": "real"})
    assert not state_manager.is_real_mode({"mode": "mock"})


def test_expand_path_handles_home():
    p = state_manager.expand_path("~/.openclaw/test.json")
    assert str(p).startswith(str(Path.home()))
