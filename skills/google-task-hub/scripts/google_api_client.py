"""google_api_client.py — единая обёртка над Google API с mock-режимом.

В режиме `real` — работает через google-api-python-client.
В режиме `mock` — читает/пишет JSON-файлы в mock_store/.

API-интерфейс стабильный в обоих режимах, поэтому sync_in/sync_out
не знают, в каком режиме они работают.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import state_manager


# ---------- Mock backend ----------

class MockBackend:
    """Имитация Google Tasks/Sheets/Calendar API через JSON-store."""

    def __init__(self, mock_dir: Path):
        self.mock_dir = mock_dir
        self.tasks_dir = mock_dir / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_files()

    def _ensure_files(self) -> None:
        if not (self.mock_dir / "tasklists.json").exists():
            self._write_json("tasklists.json", {"items": [
                {"id": "list_long_1", "title": "Долговременные задачи"},
                {"id": "list_short_1", "title": "Work"},
            ]})
        if not (self.mock_dir / "spreadsheet.json").exists():
            self._write_json("spreadsheet.json", {"sheets": {}})
        if not (self.mock_dir / "calendar_events.json").exists():
            self._write_json("calendar_events.json", {"items": []})
        # создать пустые файлы списков, если их нет
        for lst in self._read_json("tasklists.json").get("items", []):
            p = self.tasks_dir / f"{lst['id']}.json"
            if not p.exists():
                self._write_json(p, {"items": []})

    def _read_json(self, name: str | Path) -> Any:
        p = self.mock_dir / name if isinstance(name, str) else name
        with p.open(encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, name: str | Path, data: Any) -> None:
        p = self.mock_dir / name if isinstance(name, str) else name
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ----- Tasks -----

    def list_tasklists(self) -> list[dict]:
        return self._read_json("tasklists.json").get("items", [])

    def list_tasks(self, tasklist_id: str) -> list[dict]:
        path = self.tasks_dir / f"{tasklist_id}.json"
        if not path.exists():
            return []
        return self._read_json(path).get("items", [])

    def patch_task(self, tasklist_id: str, task_id: str, body: dict) -> dict:
        path = self.tasks_dir / f"{tasklist_id}.json"
        data = self._read_json(path)
        for i, t in enumerate(data["items"]):
            if t["id"] == task_id:
                data["items"][i].update(body)
                self._write_json(path, data)
                return data["items"][i]
        raise KeyError(f"Task {task_id} not found in {tasklist_id}")

    def insert_task(self, tasklist_id: str, body: dict) -> dict:
        path = self.tasks_dir / f"{tasklist_id}.json"
        data = self._read_json(path)
        # простой инкремент id
        new_id = f"task_{len(data['items']) + 1}_{tasklist_id}"
        task = {"id": new_id, **body}
        data["items"].append(task)
        self._write_json(path, data)
        return task

    # ----- Sheets -----

    def sheet_get(self, sheet_name: str, range_: str = "A:Z") -> list[list]:
        sheets = self._read_json("spreadsheet.json").get("sheets", {})
        rows = sheets.get(sheet_name, [])
        return rows

    def sheet_set(self, sheet_name: str, rows: list[list]) -> None:
        sheets = self._read_json("spreadsheet.json")
        sheets.setdefault("sheets", {})[sheet_name] = rows
        self._write_json("spreadsheet.json", sheets)

    def sheet_append(self, sheet_name: str, row: list) -> None:
        sheets = self._read_json("spreadsheet.json")
        sheets.setdefault("sheets", {}).setdefault(sheet_name, []).append(row)
        self._write_json("spreadsheet.json", sheets)

    # ----- Calendar -----

    def calendar_list(self) -> list[dict]:
        return self._read_json("calendar_events.json").get("items", [])

    def calendar_insert(self, body: dict) -> dict:
        events = self._read_json("calendar_events.json")
        eid = f"evt_{len(events['items']) + 1}"
        event = {"id": eid, **body}
        events["items"].append(event)
        self._write_json("calendar_events.json", events)
        return event


# ---------- Real backend ----------

class RealBackend:
    """Реальный Google API через google-api-python-client."""

    SCOPES_TASKS = "https://www.googleapis.com/auth/tasks"
    SCOPES_SHEETS = "https://www.googleapis.com/auth/spreadsheets"
    SCOPES_CALENDAR = "https://www.googleapis.com/auth/calendar.events"

    def __init__(self, cfg: dict):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        self._build = build
        self._Credentials = Credentials
        self._Request = Request
        self._InstalledAppFlow = InstalledAppFlow

        creds_path = state_manager.get_credentials_path(cfg)
        token_path = state_manager.get_token_path(cfg)

        scopes = cfg.get("scopes") or [
            self.SCOPES_TASKS, self.SCOPES_SHEETS, self.SCOPES_CALENDAR,
        ]

        creds = None
        if token_path.exists():
            creds = self._Credentials.from_authorized_user_file(str(token_path), scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(self._Request())
            else:
                if not creds_path.exists():
                    raise FileNotFoundError(
                        f"client_secret.json не найден: {creds_path}. "
                        "Запусти auth_setup.py или положи файл вручную."
                    )
                flow = self._InstalledAppFlow.from_client_secrets_file(str(creds_path), scopes)
                creds = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")

        self.tasks_service = self._build("tasks", "v1", credentials=creds, cache_discovery=False)
        self.sheets_service = self._build("sheets", "v4", credentials=creds, cache_discovery=False)
        self.calendar_service = self._build("calendar", "v3", credentials=creds, cache_discovery=False)
        self.calendar_id = cfg.get("calendar_id", "primary")
        self.spreadsheet_id = cfg.get("spreadsheet_id")

    def list_tasklists(self) -> list[dict]:
        result = self.tasks_service.tasklists().list().execute()
        return result.get("items", [])

    def list_tasks(self, tasklist_id: str) -> list[dict]:
        result = self.tasks_service.tasks().list(tasklist=tasklist_id, showCompleted=True).execute()
        return result.get("items", [])

    def patch_task(self, tasklist_id: str, task_id: str, body: dict) -> dict:
        return self.tasks_service.tasks().patch(tasklist=tasklist_id, task=task_id, body=body).execute()

    def insert_task(self, tasklist_id: str, body: dict) -> dict:
        return self.tasks_service.tasks().insert(tasklist=tasklist_id, body=body).execute()

    def sheet_get(self, sheet_name: str, range_: str = "A:Z") -> list[list]:
        rng = f"{sheet_name}!{range_}"
        result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=rng
        ).execute()
        return result.get("values", [])

    def sheet_set(self, sheet_name: str, rows: list[list]) -> None:
        rng = f"{sheet_name}!A1:Z{len(rows) + 1}"
        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id, range=rng,
            valueInputOption="USER_ENTERED", body={"values": rows}
        ).execute()

    def sheet_append(self, sheet_name: str, row: list) -> None:
        rng = f"{sheet_name}!A:Z"
        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=self.spreadsheet_id, range=rng,
            valueInputOption="USER_ENTERED", body={"values": [row]}
        ).execute()

    def calendar_list(self) -> list[dict]:
        result = self.calendar_service.events().list(calendarId=self.calendar_id).execute()
        return result.get("items", [])

    def calendar_insert(self, body: dict) -> dict:
        return self.calendar_service.events().insert(calendarId=self.calendar_id, body=body).execute()


# ---------- Public API ----------

class GoogleAPIClient:
    """Единая обёртка. Под капотом — Mock или Real backend."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        if state_manager.is_real_mode(cfg):
            self.backend = RealBackend(cfg)
        else:
            mock_dir = state_manager.get_mock_dir(cfg)
            self.backend = MockBackend(mock_dir)

    # passthrough
    def list_tasklists(self): return self.backend.list_tasklists()
    def list_tasks(self, tasklist_id): return self.backend.list_tasks(tasklist_id)
    def patch_task(self, tasklist_id, task_id, body): return self.backend.patch_task(tasklist_id, task_id, body)
    def insert_task(self, tasklist_id, body): return self.backend.insert_task(tasklist_id, body)
    def sheet_get(self, sheet_name, range_="A:Z"): return self.backend.sheet_get(sheet_name, range_)
    def sheet_set(self, sheet_name, rows): return self.backend.sheet_set(sheet_name, rows)
    def sheet_append(self, sheet_name, row): return self.backend.sheet_append(sheet_name, row)
    def calendar_list(self): return self.backend.calendar_list()
    def calendar_insert(self, body): return self.backend.calendar_insert(body)
