"""Идея → драфт скилла для golden-hour.

Пайплайн:
    memory/notes.jsonl (бот идей)
        → фильтр /ideas (мусор + дедуп через telegram_notes_bot._deduplicate_records
          и idea_intake.classify)
        → эвристический фильтр «actionable для golden-hour»
        → SKILL.md draft (по шаблону golden-hour)
        → workspace/Golden-Hour/skills/<name>/SKILL.md  (стейджинг для Cursor)
        → memory/skills-digest.md                       (лог)

Зачем отдельный модуль:
    • Держим логику отдельно от бота, чтобы её можно было дёргать и из бота,
      и из CLI (`python scripts/idea_to_skill.py`), и из cron'а.
    • Cursor увидит новые папки в workspace/Golden-Hour/skills/ сразу, без
      отдельной команды экспорта.

Куда сохраняем:
    C:/Users/Admin/.openclaw/workspace/Golden-Hour/skills/<slug>/SKILL.md

Использование:
    from idea_to_skill import run_pipeline, make_digest_text
    summary = run_pipeline(scope="all", auto=True)   # для бота
    print(make_digest_text(summary))                  # красиво в чат
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Подгружаем зависимости из этого же scripts/
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import idea_intake

# Импорт telegram_notes_bot делаем ленивым, чтобы избежать цикла:
# telegram_notes_bot → idea_to_skill → telegram_notes_bot.
def _load_records():
    from telegram_notes_bot import _load_records as _impl
    return _impl()


def _deduplicate_records(records):
    from telegram_notes_bot import _deduplicate_records as _impl
    return _impl(records)


def _filter_records(records, scope):
    from telegram_notes_bot import _filter_records as _impl
    return _impl(records, scope)

# ---------- Пути ----------

WORKSPACE = HERE.parent
GOLDEN_HOUR_REPO = WORKSPACE / "Golden-Hour"  # клон репо
SKILLS_STAGING = GOLDEN_HOUR_REPO / "skills"
DIGEST_PATH = WORKSPACE / "memory" / "skills-digest.md"
MEMBERS_PATH = WORKSPACE / "memory" / "members.json"

MOSCOW_TZ = timezone(timedelta(hours=3))

# ---------- Эвристика «actionable для golden-hour» ----------

# Базовый фильтр: то, что выводит /ideas, уже прошло мусорный фильтр бота
# (команды, стоп-слова, паттерны, медиа-без-подписи, is_idea=false) + дедуп.
# Здесь только минимальная защита от очевидного шума, который мог просочиться
# (короткий текст, чистый вопрос, только эмодзи). Карим сам решает в Cursor,
# какие драфты коммитить, а какие удалять.
MIN_CONTENT_LEN = 20

QUESTION_RE = re.compile(r"^\s*\?|.*\?$")
EMOJI_ONLY_RE = re.compile(
    r"^[\U0001F300-\U0001FAFF\U00002600-\U000027BF\s]+$",
    flags=re.UNICODE,
)


def _is_actionable(rec: dict) -> tuple[bool, str]:
    """Вернуть (actionable, reason_if_not)."""
    content = (rec.get("content") or "").strip()

    if len(content) < MIN_CONTENT_LEN:
        return False, f"слишком короткое ({len(content)} < {MIN_CONTENT_LEN})"

    if QUESTION_RE.match(content):
        return False, "вопрос (? в начале/конце)"

    if EMOJI_ONLY_RE.match(content):
        return False, "только эмодзи"

    return True, "ok"


# ---------- Slug / name / frontmatter ----------


_TRANS_TABLE = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    " ": "-", "_": "-", ".": "-", ",": "-", "!": "", "?": "", "—": "-",
    "–": "-",
})


def _slugify(text: str, max_len: int = 48) -> str:
    """Сделать kebab-case slug из русского/английского текста."""
    out = (text or "").lower().translate(_TRANS_TABLE)
    out = re.sub(r"[^a-z0-9-]+", "-", out)
    out = re.sub(r"-+", "-", out).strip("-")
    if not out:
        out = "idea"
    return out[:max_len]


def _first_sentence(text: str, max_len: int = 140) -> str:
    """Первое предложение / первые max_len символов — для description."""
    text = (text or "").strip()
    text = re.sub(r"\s+", " ", text)
    # Разбивка по точке/восклицательному/вопросительному
    m = re.match(r"^[^.!?]+[.!?]?", text)
    candidate = m.group(0).strip() if m else text
    if len(candidate) > max_len:
        candidate = candidate[: max_len - 1].rstrip() + "…"
    return candidate or text[:max_len]


def _clean_content_for_skill(content: str) -> str:
    """Убрать markdown-разметку (звёздочки, списки) для нормального описания."""
    text = (content or "").strip()
    # Разбить по строкам, убрать префиксы списков
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*[\*\-•]\s*", "", line)
        line = re.sub(r"\*\([^)]*\)\*", "", line)  # пометки-уточнения
        line = line.strip()
        if line:
            lines.append(line)
    return "\n".join(lines) or text


def _source_marker(idea: dict) -> str:
    """Устойчивый маркер источника: ts + user_id.

    Используется в SKILL.md как `<!-- source: ... -->` и как primary key
    для идемпотентности (проверяется в _save_skill_draft).
    """
    ts = idea.get("ts", "—")
    uid = idea.get("user_id", "—")
    return f"<!-- source: ts={ts} user_id={uid} -->\n"


def _render_skill_md(idea: dict, slug: str) -> str:
    """Сгенерировать SKILL.md по шаблону golden-hour (frontmatter + body).

    Шаблон взят с daily-plan/setup-finalize: краткое описание → Триггер → Логика
    → Что НЕ делает. Здесь мы заполняем только каркас — Карим (или я после
    ревью) дописывает детали в Cursor.
    """
    raw_content = (idea.get("content") or "").strip()
    content = _clean_content_for_skill(raw_content)
    summary = _first_sentence(raw_content, 120)
    handle = _resolve_handle_for_idea(idea)
    date = idea.get("date", "?")
    ts = idea.get("ts", "—")
    uid = idea.get("user_id", "—")
    idea_id = idea.get("id", "—")

    # Если идея-комплекс (split_idea > 1), выделим первую под-идею как фокус
    subs = idea_intake.split_idea(raw_content)
    focus = subs[0] if subs else raw_content

    # Первая строка описания в frontmatter — короче (≤ 160 байт под лимит)
    description = summary
    if len(description) > 160:
        description = description[:159].rstrip() + "…"

    marker = _source_marker(idea)
    body = f"""---
name: "{slug}"
description: "{description}"
---

{marker}# {slug}

> 🚧 **DRAFT** — авто-сгенерировано из идеи в боте `golden_hour_team` (`@Goldenteam239bot`).
> Источник: ts={ts}, user_id={uid}, {date}, {handle}, id={idea_id}.
> Требует ревью Карима и дописывания деталей в Cursor.

## Источник

{handle} в {date} предложил(а):

> {content}

## Цель

{_first_sentence(focus, 200)}

## Триггер

- **Авто:** генерируется этим скиллом, когда ...
- **Вручную:** ...

## Логика (каркас — дописать)

1. ...
2. ...

## Что НЕ делает

- ❌ ...

## Заметки для ревью

- Уровень важности в боте: importance={idea.get("importance", "?")}.
- Тема в боте: `{idea.get("topic") or "—"}`.
- Автор: {handle} (см. `memory/members.json`).
"""
    return body


def _resolve_handle_for_idea(idea: dict) -> str:
    import members as members_mod
    return members_mod.resolve_handle(idea)


# ---------- Запись в стейджинг ----------


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _save_skill_draft(slug: str, content: str, idea: dict) -> tuple[str, Path | None, str | None]:
    """Сохранить SKILL.md идемпотентно по (ts, user_id).

    Возвращает (status, path, message):
      status: 'created' | 'updated' | 'skipped' | 'conflict'
      path:   путь к файлу (None если conflict без файла)
      message: человекочитаемое пояснение

    Логика:
      1) Если файл <slug>/SKILL.md уже есть и в нём есть маркер
         `<!-- source: ts=<X> user_id=<Y> -->` с тем же (ts, user_id) —
         пропустить (уже наш, идемпотентно).
      2) Если файл уже есть, но с ДРУГИМ источником — конфликт имён.
         Добавить суффикс -2/-3/...
      3) Если файла нет — создать.
    """
    if not SKILLS_STAGING.parent.exists():
        raise FileNotFoundError(
            f"Golden-Hour repo не найден: {GOLDEN_HOUR_REPO}. "
            f"Сначала склонируй: git clone https://github.com/margoshkagt-star/Golden-Hour.git"
        )

    target_ts = idea.get("ts", "")
    target_uid = idea.get("user_id", "")
    target_key = f"ts={target_ts} user_id={target_uid}"

    base_slug = slug
    suffix = 1
    dest_path: Path | None = None
    while suffix < 100:
        candidate_dir = SKILLS_STAGING / slug
        candidate_file = candidate_dir / "SKILL.md"
        if not candidate_file.exists():
            dest_path = candidate_file
            break
        try:
            existing = candidate_file.read_text(encoding="utf-8")
        except OSError:
            existing = ""
        if target_key in existing:
            return ("skipped", candidate_file, "уже сгенерирован для этой идеи")
        slug = f"{base_slug}-{suffix + 1}"
        suffix += 1
    if dest_path is None:
        return ("conflict", None, f"слишком много конфликтов имён (>100) для {base_slug}")

    dest_dir = dest_path.parent
    _ensure_dir(dest_dir)
    dest_path.write_text(content, encoding="utf-8")
    status = "created" if suffix == 1 else "updated"
    return (status, dest_path, "ok")


# ---------- Digest / лог ----------


def _ensure_digest() -> None:
    DIGEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DIGEST_PATH.exists():
        DIGEST_PATH.write_text(
            "# 🛠 Драфты скиллов (идея → SKILL.md)\n\n"
            "Лог того, что бот `golden_hour_team` сгенерировал как кандидаты в скиллы для "
            "[Golden-Hour](https://github.com/margoshkagt-star/Golden-Hour) агента.\n\n"
            "Каждый драфт — это папка `workspace/Golden-Hour/skills/<slug>/SKILL.md`. "
            "Cursor видит её сразу. Если скилл годен — коммить и пушь. Если нет — удали папку.\n\n"
            "---\n\n",
            encoding="utf-8",
        )


def _append_digest(slug: str, idea: dict, dest: Path) -> None:
    _ensure_digest()
    handle = _resolve_handle_for_idea(idea)
    content_preview = (idea.get("content") or "").strip()[:200]
    importance = idea.get("importance", "?")
    idea_id = idea.get("id", "—")
    date = idea.get("date", "?")
    topic = idea.get("topic") or "—"
    ts = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M %Z")

    entry = (
        f"## {ts} — `{slug}`\n\n"
        f"- **Файл:** `{dest.relative_to(WORKSPACE)}`\n"
        f"- **Источник:** idea id=`{idea_id}`, date={date}, author={handle}, importance={importance}, topic=`{topic}`\n"
        f"- **Контент идеи:** {content_preview!r}\n"
        f"- **Статус:** `proposal` (awaiting Cursor review)\n\n"
        "---\n\n"
    )
    with DIGEST_PATH.open("a", encoding="utf-8") as f:
        f.write(entry)


# ---------- Пайплайн ----------


def _load_actionable_ideas(scope: str) -> tuple[list[dict], list[dict], list[tuple[dict, str]]]:
    """Загрузить и отфильтровать идеи:
    1) дедуп + classify (как в /ideas бота)
    2) scope по дате
    3) эвристика actionable
    """
    recs = _load_records()
    recs = _deduplicate_records(recs)
    state = idea_intake.load_state()
    kept, _ = idea_intake.classify(recs, state, check_duplicates=False)
    # scope фильтр (как _filter_records в боте)
    ideas = _filter_records(kept, scope)

    actionable: list[dict] = []
    rejected: list[tuple[dict, str]] = []
    for idea in ideas:
        ok, reason = _is_actionable(idea)
        if ok:
            actionable.append(idea)
        else:
            rejected.append((idea, reason))
    return ideas, actionable, rejected


def run_pipeline(scope: str = "all", *, only_ids: set[str] | None = None) -> dict:
    """Главная точка входа. Вернёт dict с тем, что сделано.

    only_ids — если задан, обрабатывать только эти id (для повторного запуска
    конкретных идей).
    """
    if not SKILLS_STAGING.parent.exists():
        return {
            "ok": False,
            "error": f"Golden-Hour repo не найден: {GOLDEN_HOUR_REPO}",
            "created": [],
            "skipped": [],
            "rejected": [],
            "all_ideas": [],
        }

    all_ideas, actionable, rejected = _load_actionable_ideas(scope)

    if only_ids:
        actionable = [i for i in actionable if i.get("id") in only_ids]

    created: list[dict] = []
    skipped: list[dict] = []

    for idea in actionable:
        raw = (idea.get("content") or "").strip()
        # slug: первые 4-6 слов
        head = " ".join(raw.split()[:5])
        slug = _slugify(head, max_len=40)
        if not slug:
            slug = "idea-" + (idea.get("id") or "anon")[:8]

        idea_id = idea.get("id")

        try:
            md = _render_skill_md(idea, slug)
            status, dest, message = _save_skill_draft(slug, md, idea)
            if status == "skipped":
                created.append({
                    "slug": slug,
                    "path": dest,
                    "idea_id": idea_id,
                    "idea_date": idea.get("date"),
                    "idea_content": raw,
                    "status": "skipped",
                    "message": message,
                })
                continue
            if status == "conflict":
                skipped.append({
                    "slug": slug,
                    "idea_id": idea_id,
                    "error": message,
                })
                continue
            _append_digest(slug, idea, dest)
            created.append({
                "slug": slug,
                "path": dest,
                "idea_id": idea_id,
                "idea_date": idea.get("date"),
                "idea_content": raw,
                "status": status,
                "message": message,
            })
        except Exception as e:  # noqa: BLE001
            skipped.append({
                "slug": slug,
                "idea_id": idea_id,
                "error": str(e),
            })

    return {
        "ok": True,
        "scope": scope,
        "all_ideas": all_ideas,
        "actionable": actionable,
        "created": created,
        "skipped": skipped,
        "rejected": rejected,
        "staging_root": SKILLS_STAGING,
        "digest_path": DIGEST_PATH,
    }


def make_digest_text(summary: dict) -> str:
    """Красиво для Telegram-сообщения."""
    if not summary.get("ok"):
        return f"❌ {summary.get('error', 'unknown error')}"

    n_all = len(summary["all_ideas"])
    n_act = len(summary["actionable"])
    n_new = len(summary["created"])
    n_skip = len(summary["skipped"])
    n_rej = len(summary["rejected"])

    lines: list[str] = [f"🛠 Идеи → скиллы (scope={summary['scope']})", ""]
    lines.append(f"📊 Прошло /ideas: {n_all}")
    lines.append(f"🎯 Actionable (после мин-фильтра): {n_act}")
    lines.append(f"📝 Создано драфтов: {n_new}")
    if n_skip:
        lines.append(f"⚠️ Пропущено (ошибка): {n_skip}")
    if n_rej:
        lines.append(f"🗑 Отклонено эвристикой: {n_rej}")
    lines.append("")

    if summary["created"]:
        lines.append("✨ Драфты SKILL.md:")
        for c in summary["created"]:
            rel = c["path"].relative_to(WORKSPACE)
            content_preview = (c["idea_content"] or "")[:80].replace("\n", " ")
            status_label = {"created": "🆕", "updated": "♻️", "skipped": "⏭"}.get(
                c.get("status", "created"), "•"
            )
            lines.append(f"  {status_label} `{rel}`")
            lines.append(f"      «{content_preview}…»")
        lines.append("")

    if summary["rejected"]:
        lines.append("🚫 Отклонено эвристикой (не скилл):")
        for idea, reason in summary["rejected"][:8]:
            handle = _resolve_handle_for_idea(idea)
            content = (idea.get("content") or "")[:60].replace("\n", " ")
            lines.append(f"  • {handle} — {reason}: «{content}…»")
        if len(summary["rejected"]) > 8:
            lines.append(f"  … и ещё {len(summary['rejected']) - 8}")
        lines.append("")

    lines.append(f"📂 Все драфты в: `{summary['staging_root'].relative_to(WORKSPACE)}`")
    lines.append(f"📋 Лог: `{summary['digest_path'].relative_to(WORKSPACE)}`")
    lines.append("")
    lines.append("👉 Открой `Golden-Hour/skills/<slug>/SKILL.md` в Cursor, отредактируй, "
                 "закоммить и запушь.")
    return "\n".join(lines)


# ---------- CLI ----------


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    import argparse
    parser = argparse.ArgumentParser(description="Идеи из бота → драфты SKILL.md в Golden-Hour")
    parser.add_argument("--scope", default="all", choices=["all", "today", "week", "month"])
    parser.add_argument("--ids", default="", help="Только эти id (через запятую)")
    args = parser.parse_args(argv)

    only_ids = {s.strip() for s in args.ids.split(",") if s.strip()} or None
    summary = run_pipeline(scope=args.scope, only_ids=only_ids)
    print(make_digest_text(summary))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())