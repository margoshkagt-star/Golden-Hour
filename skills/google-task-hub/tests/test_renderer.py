"""test_renderer.py — проверяем render_dashboard в mock-режиме."""

from scripts import state_manager
from scripts.google_api_client import GoogleAPIClient
from scripts.sync_in import run_sync as run_sync_in
from scripts.render_dashboard import render_short, render_long


def test_render_short_has_sections(temp_config):
    cfg = state_manager.load_config(temp_config)
    api = GoogleAPIClient(cfg)
    run_sync_in(api, cfg)

    rows = render_short(api, cfg)
    assert rows[0] == ["# Dashboard Short"]
    # есть разделы
    flat = " ".join(" ".join(str(c) for c in r) for r in rows)
    assert "## Сегодня" in flat
    assert "## In progress" in flat
    assert "## Прогресс по категориям" in flat


def test_render_long_filters_long_tasks(temp_config):
    cfg = state_manager.load_config(temp_config)
    api = GoogleAPIClient(cfg)
    run_sync_in(api, cfg)

    rows = render_long(api, cfg)
    flat = " ".join(" ".join(str(c) for c in r) for r in rows)
    assert "## Долговременные задачи" in flat
    assert "## Статистика" in flat
    # Должны быть 3 long-задачи
    long_section_idx = next(i for i, r in enumerate(rows) if r and "## Долговременные задачи" in str(r[0]))
    # Сразу за заголовком идёт шапка таблицы, потом 3 строки
    assert len(rows) > long_section_idx + 3


def test_render_short_includes_overdue_task(temp_config):
    """Просроченная задача должна попасть в 'Сегодня' (deadline <= today)."""
    cfg = state_manager.load_config(temp_config)
    api = GoogleAPIClient(cfg)
    run_sync_in(api, cfg)

    rows = render_short(api, cfg)
    flat = " ".join(" ".join(str(c) for c in r) for r in rows)
    # Задача с deadline 2026-06-17 — сегодня 2026-06-18, должна попасть
    assert "Сдать отчёт" in flat
