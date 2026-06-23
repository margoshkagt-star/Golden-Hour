"""Реестр участников Telegram-бота: единая точка истины для handle'ов.

Используется во всех местах, где показывается автор: /ideas, /info, /classify,
дайджесты, render_ideas_md и т.д. Раньше каждый модуль брал username/first_name
из самой записи notes.jsonl — что при смене username в Telegram давало устаревшие
данные. Теперь сначала пробуем resolve по user_id через members.json (актуальные
данные), а если не нашли — fallback на поля записи (старое поведение, fail-open).

Структура memory/members.json:
    {
      "_meta": {...},
      "members": [
        {"user_id": ..., "username": ..., "first_name": ...,
         "last_name": ..., "display": ..., "role": ..., "notes": ...},
        ...
      ]
    }

Приоритеты resolve_handle(record):
    1. members[user_id].display (если задан)
    2. members[user_id].first_name + last_name (если first_name есть)
    3. members[user_id].username c @ (если есть)
    4. record["username"] c @ (fallback)
    5. record["first_name"] (fallback)
    6. id:<user_id> (последний fallback)
    7. "anon"

Для ботов и aiogram types.User есть отдельная функция resolve_handle_from_user()
— принимает объект aiogram.types.User.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------- Пути ----------

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
MEMBERS_PATH = WORKSPACE / "memory" / "members.json"

# ---------- Кеш ----------

_CACHE: dict[str, Any] | None = None


def _load_fresh() -> dict[str, Any]:
    """Прочитать members.json без кеша. Возвращает {"by_id": ..., "by_username": ..., "members": [...]}."""
    if not MEMBERS_PATH.exists():
        return {"by_id": {}, "by_username": {}, "members": []}
    try:
        data = json.loads(MEMBERS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"by_id": {}, "by_username": {}, "members": []}

    members = data.get("members") or []
    by_id: dict[int, dict[str, Any]] = {}
    by_username: dict[str, dict[str, Any]] = {}
    for m in members:
        uid = m.get("user_id")
        if uid is not None:
            by_id[int(uid)] = m
        uname = (m.get("username") or "").strip().lower()
        if uname:
            by_username[uname] = m
    return {"by_id": by_id, "by_username": by_username, "members": members}


def load_members() -> dict[str, Any]:
    """Загрузить реестр (с кешем). Вызывайте reload_members() после правки members.json."""
    global _CACHE
    if _CACHE is None:
        _CACHE = _load_fresh()
    return _CACHE


def reload_members() -> dict[str, Any]:
    """Сбросить кеш и перечитать members.json. Возвращает свежий dict."""
    global _CACHE
    _CACHE = _load_fresh()
    return _CACHE


def get_member_by_id(user_id: int | str | None) -> dict[str, Any] | None:
    if user_id is None:
        return None
    try:
        return load_members()["by_id"].get(int(user_id))
    except (TypeError, ValueError):
        return None


def get_member_by_username(username: str | None) -> dict[str, Any] | None:
    if not username:
        return None
    return load_members()["by_username"].get(username.strip().lower())


# ---------- Резолвер handle'а ----------


def _format_name(m: dict[str, Any]) -> str:
    """Сформировать строку имени из записи members[].

    v2: возвращаем @username, если есть. Иначе first_name+last_name. Display
    больше не используется (см. members.json v2 — display убран).
    """
    uname = (m.get("username") or "").strip()
    if uname:
        return f"@{uname}"
    parts = []
    first = (m.get("first_name") or "").strip()
    if first:
        parts.append(first)
    last = (m.get("last_name") or "").strip()
    if last:
        parts.append(last)
    if parts:
        return " ".join(parts)
    return "anon"


def _format_handle(m: dict[str, Any]) -> str:
    """Handle для отображения — всегда @username, если есть; иначе имя."""
    uname = (m.get("username") or "").strip()
    if uname:
        return f"@{uname}"
    name = _format_name(m)
    return name if name != "anon" else "anon"


def resolve_handle(record: dict[str, Any]) -> str:
    """Handle для идентификации автора (как aiogram types.User.username): всегда
    @username, если есть. Иначе first_name, иначе id:user_id.

    Возвращает строку вида:
      "@svirepymedved" — если в members есть username;
      "Михаил"         — если username нет, но есть first_name;
      "id:1038917447"  — крайний fallback;
      "anon"           — если вообще ничего.

    Приоритет:
      1. members[user_id].username c @
      2. members[user_id].first_name
      3. record["username"] c @ (fallback)
      4. record["first_name"]
      5. id:<user_id>
      6. "anon"
    """
    user_id = record.get("user_id")
    m = get_member_by_id(user_id) if user_id is not None else None

    # Если в members по user_id не нашли — пробуем по username из записи
    if m is None:
        rec_username = (record.get("username") or "").strip()
        if rec_username:
            m_by_uname = get_member_by_username(rec_username)
            if m_by_uname:
                m = m_by_uname

    # 1) username из members
    if m is not None:
        uname = (m.get("username") or "").strip()
        if uname:
            return f"@{uname}"
        first = (m.get("first_name") or "").strip()
        if first:
            return first

    # 2) Fallback на поля записи
    rec_username = (record.get("username") or "").strip()
    if rec_username:
        return f"@{rec_username}"

    rec_first = (record.get("first_name") or "").strip()
    if rec_first:
        return rec_first

    # 3) Крайние fallback'ы
    if user_id is not None:
        return f"id:{user_id}"
    return "anon"


def resolve_handle_with_at(record: dict[str, Any]) -> str:
    """Как resolve_handle, но username всегда с @ (если есть). Используется в логах/таблицах.

    Здесь display-имя НЕ возвращается — это строго handle формата (@user) для
    однозначной идентификации. Для человекочитаемого имени используй resolve_name().
    """
    user_id = record.get("user_id")
    m = get_member_by_id(user_id) if user_id is not None else None

    if m is not None:
        uname = (m.get("username") or "").strip()
        if uname:
            return f"@{uname}"

    rec_username = (record.get("username") or "").strip()
    if rec_username:
        return f"@{rec_username}"

    if user_id is not None:
        return f"id:{user_id}"
    return "anon"


def resolve_name(record: dict[str, Any]) -> str:
    """Имя автора для отображения. v2: всегда @username (без реальных имён).

    Используется там, где @ допустим (заголовки, дайджесты, "Топ-авторов мусора").
    Сейчас полностью совпадает с resolve_handle() — сохранён как отдельная
    функция на случай, если позже захочется вернуть имена.

    Приоритет:
      1. members[user_id].username c @
      2. record["username"] c @
      3. first_name + last_name (если username нет)
      4. id:<user_id>
      5. "anon"
    """
    user_id = record.get("user_id")
    m = get_member_by_id(user_id) if user_id is not None else None

    if m is None:
        rec_username = (record.get("username") or "").strip()
        if rec_username:
            m_by_uname = get_member_by_username(rec_username)
            if m_by_uname:
                m = m_by_uname

    if m is not None:
        return _format_name(m)

    rec_username = (record.get("username") or "").strip()
    if rec_username:
        return f"@{rec_username}"

    parts = []
    first = (record.get("first_name") or "").strip()
    if first:
        parts.append(first)
    last = (record.get("last_name") or "").strip()
    if last:
        parts.append(last)
    if parts:
        return " ".join(parts)

    if user_id is not None:
        return f"id:{user_id}"
    return "anon"


def resolve_handle_from_user(user: Any) -> str:
    """Резолв handle из aiogram.types.User (owner-only ветка, всегда есть live-данные).

    v2: @username (из members или из live User) приоритетнее имени. Так
    единообразно с resolve_handle() для записей.
    """
    if user is None:
        return "anon"
    user_id = getattr(user, "id", None)
    username = getattr(user, "username", None)

    m = get_member_by_id(user_id)
    if m is not None:
        uname = (m.get("username") or "").strip()
        if uname:
            return f"@{uname}"

    if username:
        return f"@{username}"
    if user_id is not None:
        return f"id:{user_id}"
    return "anon"


def resolve_name_from_user(user: Any) -> str:
    """Имя из aiogram.types.User. v2: всегда @username (без реальных имён)."""
    if user is None:
        return "anon"
    user_id = getattr(user, "id", None)
    username = getattr(user, "username", None)
    m = get_member_by_id(user_id)
    if m is not None:
        uname = (m.get("username") or "").strip()
        if uname:
            return f"@{uname}"
    if username:
        return f"@{username}"
    if user_id is not None:
        return f"id:{user_id}"
    return "anon"


def _format_name_or(first: Any, last: Any, username: Any, user_id: Any) -> str:
    parts = []
    if first:
        parts.append(str(first).strip())
    if last:
        parts.append(str(last).strip())
    if parts:
        return " ".join(parts)
    if username:
        return f"@{username}"
    if user_id is not None:
        return f"id:{user_id}"
    return "anon"


# ---------- Совместимость со старым кодом ----------

def author_handle(record: dict[str, Any]) -> str:
    """Алиас для resolve_handle(). Сохранено для обратной совместимости с импортом."""
    return resolve_handle(record)


if __name__ == "__main__":
    # Демо-вывод: показывает реестр + пара тестовых resolve
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    data = load_members()
    print(f"👥 Members: {len(data['members'])} чел.")
    for m in data["members"]:
        uid = m.get("user_id")
        uname = m.get("username") or "—"
        first = m.get("first_name") or ""
        last = m.get("last_name") or ""
        role = m.get("role", "?")
        full = f"@{uname}" if uname != "—" else (f"{first} {last}".strip() or "anon")
        uid_str = f"id={uid}" if uid is not None else "id=—"
        print(f"  • {full} ({uid_str}, @{uname}, role={role})")
    print()
    print("🔍 Тест resolve_handle:")
    tests = [
        {"user_id": 1038917447, "username": "old_name", "first_name": "Beatus"},
        {"user_id": 5649925712, "username": "svirepymedved", "first_name": "Михаил"},
        {"user_id": 501775529, "username": "aabarabanov", "first_name": "Aleksey", "last_name": "Barabanov"},
        {"user_id": 1317020734, "username": "Sayu33", "first_name": "Sayu"},
        {"user_id": 999999999, "username": "unknown_user", "first_name": "NoName"},
        {"user_id": 2, "username": "maria", "first_name": "Мария"},
    ]
    for t in tests:
        print(f"  {t} → {resolve_handle(t)}")