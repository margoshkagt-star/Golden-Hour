"""render_dashboard.py — генерация листов Dashboard Short и Dashboard Long.

Читает Sheet.Tasks и формирует:
- Dashboard Short: задачи на сегодня/неделю, прогресс по категориям
- Dashboard Long: long-задачи с прогрессом, статистика за периоды

Запуск:
    py scripts/render_dashboard.py --short
    py scripts/render_dashboard.py --long
    py scripts/render_dashboard.py --all
    py scripts/render_dashboard.py --mock
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
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


def sheet_to_dicts(rows: list[list]) -> list[dict]:
    if not rows:
        return []
    headers = rows[0]
    return [dict(zip(headers, r)) for r in rows[1:] if r]


def _s(v: Any) -> str:
    if v is None or v == "":
        return ""
    return str(v)


def _parse_dt(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def render_short(api: GoogleAPIClient, cfg: dict) -> list[list]:
    """Dashboard Short: сегодня + категории."""
    rows = sheet_to_dicts(api.sheet_get("Tasks"))
    today = datetime.now(timezone.utc).date().isoformat()

    today_tasks = [r for r in rows if r.get("status") != "done" and (
        not r.get("deadline") or (r.get("deadline") or "")[:10] <= today
    )]
    in_progress = [r for r in rows if r.get("status") == "in_progress"]

    out: list[list] = []
    out.append(["# Dashboard Short"])
    out.append([f"Обновлено: {datetime.now(timezone.utc).isoformat(timespec='seconds')}"])
    out.append([])
    out.append([f"## Сегодня ({len(today_tasks)} задач)"])
    out.append(["name", "category", "weight", "progress", "status", "deadline"])
    for r in today_tasks[:20]:
        out.append([
            _s(r.get("name")), _s(r.get("category")), _s(r.get("weight")),
            f"{_s(r.get('progress'))}%", _s(r.get("status")), _s((r.get("deadline") or "")[:10]),
        ])

    out.append([])
    out.append([f"## In progress ({len(in_progress)})"])
    out.append(["name", "weight", "progress", "category"])
    for r in in_progress[:20]:
        out.append([
            _s(r.get("name")), _s(r.get("weight")),
            f"{_s(r.get('progress'))}%", _s(r.get("category")),
        ])

    # Прогресс по категориям
    by_cat: dict[str, list[int]] = {}
    by_cat_weight: dict[str, list[int]] = {}
    for r in rows:
        cat = r.get("category") or "—"
        prog = int(r.get("progress") or 0)
        weight = int(r.get("weight") or 1)
        by_cat.setdefault(cat, []).append(prog)
        by_cat_weight.setdefault(cat, []).append(weight * prog)

    out.append([])
    out.append(["## Прогресс по категориям"])
    out.append(["category", "avg_progress", "weighted_progress", "tasks"])
    for cat in sorted(by_cat):
        progs = by_cat[cat]
        weighted = sum(by_cat_weight[cat])
        total_w = sum(int(r.get("weight") or 1) for r in rows if (r.get("category") or "—") == cat)
        out.append([
            cat,
            f"{sum(progs) / len(progs):.0f}%",
            f"{weighted / total_w:.0f}%" if total_w else "—",
            str(len(progs)),
        ])

    return out


def render_long(api: GoogleAPIClient, cfg: dict) -> list[list]:
    """Dashboard Long: long-задачи + статистика."""
    rows = sheet_to_dicts(api.sheet_get("Tasks"))
    long_rows = [r for r in rows if r.get("task_type") == "long"]

    out: list[list] = []
    out.append(["# Dashboard Long"])
    out.append([f"Обновлено: {datetime.now(timezone.utc).isoformat(timespec='seconds')}"])
    out.append([])
    out.append([f"## Долговременные задачи ({len(long_rows)})"])
    out.append(["name", "weight", "progress", "deadline", "status"])
    for r in long_rows:
        out.append([
            _s(r.get("name")), _s(r.get("weight")),
            f"{_s(r.get('progress'))}%",
            _s((r.get("deadline") or "")[:10]),
            _s(r.get("status")),
        ])

    # Статистика (вес + часы)
    out.append([])
    out.append(["## Статистика"])
    out.append(["period", "weight_done", "hours_done", "tasks_done"])
    done = [r for r in rows if r.get("status") == "done"]
    weight_done = sum(int(r.get("weight") or 1) for r in done)
    hours_done = sum(int(r.get("actual_duration") or 0) for r in done) / 60
    out.append(["all-time", str(weight_done), f"{hours_done:.1f}", str(len(done))])
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--short", action="store_true")
    p.add_argument("--long", action="store_true")
    p.add_argument("--all", action="store_true")
    p.add_argument("--mock", action="store_true")
    p.add_argument("--config", default="state/google-task-hub.json")
    args = p.parse_args()

    if not (args.short or args.long or args.all):
        args.all = True

    config_path = Path(args.config)
    cfg = state_manager.load_config(config_path)
    if args.mock:
        cfg["mode"] = "mock"

    api = GoogleAPIClient(cfg)

    if args.short or args.all:
        rows = render_short(api, cfg)
        api.sheet_set("Dashboard Short", rows)
        print(f"✅ Dashboard Short обновлён ({len(rows)} строк)")

    if args.long or args.all:
        rows = render_long(api, cfg)
        api.sheet_set("Dashboard Long", rows)
        print(f"✅ Dashboard Long обновлён ({len(rows)} строк)")


if __name__ == "__main__":
    main()
