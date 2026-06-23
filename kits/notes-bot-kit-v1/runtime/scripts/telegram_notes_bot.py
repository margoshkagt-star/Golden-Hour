"""
Telegram notes bot (aiogram 3.x) — Owner + Team edition.

- Public bot; everyone can write notes (no rate limit by request). Guests get a
  minimal "Принято ✅" reply and no command access; their notes still get into the inbox.
- Owner (@beatusx) is recognized by username; first /start fills chat_id.
- Team members (config in memory/bot-config.json → team) get read access to /info, /ideas, /classify.
- Notes go to memory/inbox/YYYY-MM-DD.md and memory/notes.jsonl.
- /classify (or scripts/idea_intake.py) produces memory/ideas.md (separate file with
  pre-filtered ideas, garbage removed by deterministic rules).

Owner commands:
    /start    — register as owner, return chat_id
    /help     — list commands
    /today    — show all notes for today
    /week     — show notes for the last 7 days
    /digest   — send unsent notes since the last digest
    /search q — search notes by substring
    /info [scope]   — summary of ideas
    /ideas [scope]  — full list of ideas
    /classify [new-only] — run idea classifier, refresh ideas.md

Team read:
    /info [scope], /ideas [scope]

A background task sends a digest to the owner every 3 hours (configurable in
memory/bot-config.json → digest.interval_hours).

This is deliberately small and predictable. No LLM classification, no vision,
no semantic search, no tags — just save and read.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    Message,
)

# Local modules
import idea_intake  # лежит рядом, в scripts/
import members as members_mod  # реестр user_id → handle/name (см. memory/members.json)
import idea_to_skill  # пайплайн «идея → драфт SKILL.md»

# ----- Paths & env -----

WORKSPACE = Path(__file__).resolve().parent.parent
ENV_PATH = WORKSPACE.parent / ".env"
CONFIG_PATH = WORKSPACE / "memory" / "bot-config.json"
INBOX_DIR = WORKSPACE / "memory" / "inbox"
JSONL_PATH = WORKSPACE / "memory" / "notes.jsonl"
LOG_PATH = WORKSPACE / "scripts" / "telegram_notes_bot.log"

INBOX_DIR.mkdir(parents=True, exist_ok=True)
JSONL_PATH.touch(exist_ok=True)

# Forge pipeline v2 (2026-06-21): бот НЕ делает заглушки.
# Forgeable идеи кладутся в FORGE_QUEUE_PATH; notes-keeper (я) забирает их
# и зовёт skill-forge через sessions_send. См. _maybe_auto_skill_from_text.
FORGE_QUEUE_PATH = WORKSPACE / "memory" / "forge_queue.jsonl"
FORGE_RESULTS_PATH = WORKSPACE / "memory" / "forge_results.jsonl"
FORGE_QUEUE_PATH.touch(exist_ok=True)
FORGE_RESULTS_PATH.touch(exist_ok=True)

# Voice transcribe (2026-06-22): голосовые через faster-whisper (skill voice-transcribe).
# Skill: ~/.openclaw/workspace/skills/voice-transcribe/ (applied через Skill Workshop).
# Скачиваем .ogg -> MEDIA_DIR, запускаем transcribe.py, читаем .txt.
MEDIA_DIR = WORKSPACE / "media" / "inbound"
TRANSCRIBE_SCRIPT = WORKSPACE / "skills" / "voice-transcribe" / "scripts" / "transcribe.py"
TRANSCRIBE_PYTHON = r"C:\Users\Admin\AppData\Local\Programs\Python\Python312\python.exe"
TRANSCRIBE_TIMEOUT = 60  # секунд на одно голосовое
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


# ----- Guards для Bug #1 -----
# Идея: greetings и короткие служебные сообщения НЕ должны триггерить forge.
# - greetings: вообще не записывать как идею (это не идея)
# - короткие (< 3 слов): записать (для истории), но без auto_skill
GREETINGS: set[str] = {
    "привет", "hello", "hi", "хай", "здаров", "здарова", "йоу",
    "test", "тест", "ок", "окей", "ok", "okay",
    "хей", "хелло", "хеллоу", "прив", "qq", "йо",
}
SHORT_MSG_MAX_WORDS = 3


def _is_greeting(text: str) -> bool:
    """True если текст — приветствие или служебная реплика (не идея)."""
    t = (text or "").strip().lower()
    if not t:
        return True
    return t in GREETINGS


def _is_short_message(text: str) -> bool:
    """True если сообщение слишком короткое для forge (но уже не приветствие)."""
    t = (text or "").strip()
    return 0 < len(t.split()) < SHORT_MSG_MAX_WORDS


def load_env() -> None:
    """Load .env with FORCE override. .env is the source of truth for secrets."""
    if not ENV_PATH.exists():
        return
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ[k.strip()] = v.strip()


load_env()

TELEGRAM_BOT_TOKEN = (
    os.environ.get("TEAM_BOT_TOKEN")
    or os.environ.get("TELEGRAM_BOT_TOKEN")
)
if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("Missing TEAM_BOT_TOKEN (or TELEGRAM_BOT_TOKEN fallback) in .env")

MOSCOW_TZ = timezone(timedelta(hours=3))


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ----- Logging -----

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("notes_bot")

# ----- Storage -----


def author_label(user: types.User) -> str:
    """Полная подпись автора для только что полученного сообщения.
    v2: «@username (id 123)» — без реальных имён (только юзернейм).
    """
    handle = members_mod.resolve_handle_from_user(user)
    return f"{handle} (id {user.id})"


def author_handle(record: dict) -> str:
    """Handle автора для dict-записи из notes.jsonl.

    Использует members.resolve_handle() — сначала пробует resolve через
    memory/members.json (актуальные данные), потом fallback на поля записи.

    Используется в build_ideas_report / _format_idea_entry / format_digest,
    где есть только dict, а не types.User.
    """
    return members_mod.resolve_handle(record)


def author_name(record: dict) -> str:
    """Человекочитаемое имя автора (без @).

    Для сводок по авторам и "Топ-авторов". Через members.resolve_name().
    """
    return members_mod.resolve_name(record)


def note_kind_emoji(kind: str) -> str:
    return {
        "text": "💬",
        "voice": "🎙",
        "photo": "🖼",
        "document": "📎",
        "sticker": "😺",
        "video": "🎬",
        "other": "📝",
    }.get(kind, "📝")


def append_note(
    user: types.User, kind: str, content: str, *, duration: int | None = None
) -> dict:
    now = datetime.now(MOSCOW_TZ)
    record = {
        "ts": now.isoformat(timespec="seconds"),
        "date": now.date().isoformat(),
        "time": now.strftime("%H:%M"),
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "kind": kind,
        "duration": duration,
        "content": content,
    }
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    md_path = INBOX_DIR / f"{now.date().isoformat()}.md"
    header = f"# Inbox {now.date().isoformat()}\n\n"
    if not md_path.exists():
        md_path.write_text(header, encoding="utf-8")

    duration_str = f" ({duration}s)" if duration else ""
    line = (
        f"## {now.strftime('%H:%M')} — {author_label(user)} "
        f"{note_kind_emoji(kind)} {kind}{duration_str}\n"
        f"{content}\n\n"
    )
    with md_path.open("a", encoding="utf-8") as f:
        f.write(line)

    return record


def read_jsonl_since(iso_ts: str | None) -> list[dict]:
    if not JSONL_PATH.exists():
        return []
    out = []
    for line in JSONL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if iso_ts is None or rec["ts"] > iso_ts:
            out.append(rec)
    return out


def _load_records() -> list[dict]:
    """Загрузить все записи из jsonl. Возвращает [] если файла нет.

    Используется в /info, /ideas, /classify и в офлайн-демках (_demo_info.py).
    """
    if not JSONL_PATH.exists():
        return []
    out: list[dict] = []
    for line in JSONL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            log.warning("skip malformed jsonl line: %r", line[:80])
    return out


def _filter_records(recs: list[dict], scope: str) -> list[dict]:
    """Отфильтровать записи по scope (живой фильтр для /info и /ideas).

    Сейчас любая сохранённая заметка считается «идеей» (is_idea по умолчанию True).
    Для более глубокой фильтрации (стоп-слова, дубли и т.п.) используй /classify
    или scripts/idea_intake.py — он пишет отдельный memory/ideas.md.

    Scope: 'all' | 'today' | 'week' | 'month' — фильтр по дате.
    """
    if not recs:
        return []
    today = datetime.now(MOSCOW_TZ).date()
    if scope == "today":
        d_from = today.isoformat()
    elif scope == "week":
        d_from = (today - timedelta(days=6)).isoformat()
    elif scope == "month":
        d_from = (today - timedelta(days=29)).isoformat()
    else:
        d_from = "0000-00-00"
    out: list[dict] = []
    for r in recs:
        if not r.get("is_idea", True):
            continue
        if r.get("date", "0000-00-00") >= d_from:
            out.append(r)
    return out


def _shorten(text: str, limit: int = 200) -> str:
    """Безопасное обрезание текста + замена переносов на пробелы."""
    body = (text or "").strip().replace("\n", " ")
    if len(body) > limit:
        body = body[: limit - 1] + "…"
    return body


def _parse_scope(message: Message, default: str = "all") -> str:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].strip().lower() in {"all", "today", "week", "month"}:
        return parts[1].strip().lower()
    return default


def build_ideas_report(ideas: list[dict], scope: str) -> str:
    """Собрать отчёт /info: сводка + последние идеи (plain text)."""
    if not ideas:
        return (
            f"📊 Идеи ({scope})\n\n"
            f"Пока ничего нет. Пришли текст или голосовое — запишу."
        )

    total = len(ideas)

    by_author: dict[str, int] = {}
    for r in ideas:
        handle = author_handle(r)
        by_author[handle] = by_author.get(handle, 0) + 1
    top_authors = sorted(by_author.items(), key=lambda kv: (-kv[1], kv[0]))[:5]

    by_kind: dict[str, int] = {}
    for r in ideas:
        k = r.get("kind", "other")
        by_kind[k] = by_kind.get(k, 0) + 1

    by_day: dict[str, int] = {}
    for r in ideas:
        d = r.get("date", "?")
        by_day[d] = by_day.get(d, 0) + 1
    sorted_days = sorted(by_day.items(), reverse=True)[:7]

    dates = sorted(r.get("date", "") for r in ideas if r.get("date"))
    if dates:
        date_range = dates[0] if dates[0] == dates[-1] else f"{dates[0]} → {dates[-1]}"
    else:
        date_range = "—"

    sorted_ideas = sorted(ideas, key=lambda r: r.get("ts", ""), reverse=True)
    last = sorted_ideas[:5]

    lines: list[str] = []
    scope_label = {
        "all": "все",
        "today": "сегодня",
        "week": "за неделю",
        "month": "за месяц",
    }.get(scope, scope)
    lines.append(f"📊 Идеи ({scope_label}) — {total} шт.")
    lines.append(f"📅 Диапазон: {date_range}")
    lines.append("")
    lines.append("👤 По авторам:")
    for name, n in top_authors:
        lines.append(f"  • {name} — {n}")
    lines.append("")
    lines.append("🗂 По типу:")
    for kind, n in sorted(by_kind.items(), key=lambda kv: -kv[1]):
        lines.append(f"  • {note_kind_emoji(kind)} {kind} — {n}")
    lines.append("")
    lines.append("📅 По дням (топ-7):")
    for d, n in sorted_days:
        lines.append(f"  • {d} — {n}")
    lines.append("")
    lines.append("🔥 Последние 5:")
    for r in last:
        handle = author_handle(r)
        emoji = note_kind_emoji(r.get("kind", "other"))
        prefix = f"{r.get('time', '??:??')} — {handle} {emoji}"
        if r.get("kind") == "voice":
            dur = r.get("duration") or 0
            prefix += f" (голос {dur}s)"
        body = _shorten(r.get("content", ""), 180)
        lines.append(f"  • {prefix}: «{body}»")

    return "\n".join(lines)


def _format_idea_entry(r: dict, body: str) -> list[str]:
    """Строки отчёта для одной записи; разворачивает списки и комплексные идеи."""
    handle = author_handle(r)
    emoji = note_kind_emoji(r.get("kind", "other"))
    date = r.get("date", "?")
    time = r.get("time", "??:??")
    prefix = f"  • {date} {time} — {handle} {emoji}"
    if r.get("kind") == "voice":
        dur = r.get("duration") or 0
        prefix += f" (голос {dur}s)"
    subs = idea_intake.split_idea(body)
    if len(subs) > 1:
        out = [f"{prefix} ({len(subs)} пунктов):"]
        for sub in subs:
            out.append(f"      └─ {sub}")
        return out
    return [f"{prefix}: «{_shorten(body, 220)}»"]


def build_ideas_list(ideas: list[dict], scope: str) -> str:
    """Список всех идей для /ideas (plain text)."""
    scope_label = {
        "all": "все",
        "today": "сегодня",
        "week": "за неделю",
        "month": "за месяц",
    }.get(scope, scope)
    if not ideas:
        return (
            f"💡 Идеи ({scope_label})\n\n"
            f"Пока ничего нет. Пришли текст или голосовое — запишу."
        )

    sorted_ideas = sorted(ideas, key=lambda r: r.get("ts", ""), reverse=True)
    lines = [f"💡 Идеи ({scope_label}) — {len(sorted_ideas)} шт.", ""]
    for r in sorted_ideas:
        body = (r.get("content") or "").strip()
        lines.extend(_format_idea_entry(r, body))
    return "\n".join(lines)


def build_ideas_categorized(ideas: list[dict], scope: str) -> str:
    """Идеи, сгруппированные по теме (поле `topic`).

    Записи с topic — в тематических разделах.
    Записи без topic — в разделе «_без темы_» (с развёрткой списков).
    """
    scope_label = {
        "all": "все",
        "today": "сегодня",
        "week": "за неделю",
        "month": "за месяц",
    }.get(scope, scope)

    with_topic = [r for r in ideas if (r.get("topic") or "").strip()]
    without_topic = [r for r in ideas if not (r.get("topic") or "").strip()]

    if not with_topic:
        return (
            f"💡 Важные идеи ({scope_label})\n\n"
            f"_Нет идей с темой. Добавь поле `topic` в запись в notes.jsonl._"
        )

    by_topic: dict[str, list[dict]] = {}
    for r in with_topic:
        topic = (r.get("topic") or "").strip()
        by_topic.setdefault(topic, []).append(r)

    topics_sorted = sorted(
        by_topic.keys(),
        key=lambda t: (-len(by_topic[t]), t.lower()),
    )

    lines: list[str] = [
        f"💡 Важные идеи ({scope_label}) — {len(with_topic)} шт. в {len(by_topic)} темах",
        "",
    ]
    split_total = 0
    for topic in topics_sorted:
        items = by_topic[topic]
        lines.append(f"📁 {topic} ({len(items)})")
        items_sorted = sorted(items, key=lambda r: r.get("ts", ""), reverse=True)
        for r in items_sorted:
            body = (r.get("content") or "").strip()
            entry_lines = _format_idea_entry(r, body)
            if len(idea_intake.split_idea(body)) > 1:
                split_total += 1
            lines.extend(entry_lines)
        lines.append("")

    if without_topic:
        lines.append(f"📁 _без темы_ ({len(without_topic)})")
        for r in sorted(without_topic, key=lambda x: x.get("ts", ""), reverse=True):
            body = (r.get("content") or "").strip()
            entry_lines = _format_idea_entry(r, body)
            if len(idea_intake.split_idea(body)) > 1:
                split_total += 1
            lines.extend(entry_lines)
        lines.append("")

    if split_total:
        lines.append(f"🔍 Разбито на под-идеи: {split_total} идей")

    return "\n".join(lines)


def read_jsonl_for(period: str) -> list[dict]:
    today = datetime.now(MOSCOW_TZ).date()
    if period == "today":
        d_from = today.isoformat()
    elif period == "week":
        d_from = (today - timedelta(days=6)).isoformat()
    else:
        d_from = "0000-00-00"
    out = []
    for line in JSONL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["date"] >= d_from:
            out.append(rec)
    return out


def format_digest(records: list[dict], header: str) -> str:
    if not records:
        return f"{header}\n\n(пусто)"
    lines = [header, ""]
    for r in records:
        handle = author_handle(r)
        emoji = note_kind_emoji(r["kind"])
        prefix = f"{r['time']} — {handle} {emoji}"
        if r["kind"] == "voice":
            dur = f" (голос {r.get('duration', 0)}s)"
            prefix += dur
        body = (r["content"] or "").strip().replace("\n", " ")
        if len(body) > 220:
            body = body[:217] + "…"
        lines.append(f"• {prefix}: «{body}»")
    lines.append(f"\nИтого: {len(records)} заметок")
    return "\n".join(lines)


def _split_for_tg(text: str, limit: int = 3800) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks, cur, cur_len = [], [], 0
    for line in text.splitlines(keepends=True):
        if cur_len + len(line) > limit and cur:
            chunks.append("".join(cur))
            cur, cur_len = [line], len(line)
        else:
            cur.append(line)
            cur_len += len(line)
    if cur:
        chunks.append("".join(cur))
    return chunks


# ----- Bot & dispatcher -----

bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()


def is_owner(user: types.User) -> bool:
    cfg = load_config()
    target = (cfg.get("owner", {}) or {}).get("username")
    return bool(user.username) and user.username.lower() == (target or "").lower()


def is_team_member(user: types.User) -> bool:
    if is_owner(user):
        return True
    if not user.username:
        return False
    cfg = load_config()
    team = cfg.get("team") or []
    uname = user.username.lower()
    return any(str(u).lower() == uname for u in team)


def _auto_skill_enabled() -> bool:
    """Читать bot-config.json → auto_skill_from_ideas. По умолчанию True."""
    try:
        cfg = load_config()
        val = cfg.get("auto_skill_from_ideas")
        return True if val is None else bool(val)
    except Exception:
        return False


async def _maybe_auto_skill_from_text(message: Message) -> None:
    """Если forgeable — поставить идею в очередь на skill-forge.

    Pipeline v2 (2026-06-21):
      1. Находим последнюю запись этого user_id (только что добавлена).
      2. Проверяем forgeable (idea_intake.is_forgeable: len > 30).
      3. Если forgeable — пишем в forge_queue.jsonl.
      4. Karim'у говорим «queued».

    НИКАКИХ заглушек. Реальный forge делает skill-forge агент через
    sessions_send. Karim'у нужно сказать notes-keeper'у
    «обработай forge_queue» (в этом же чате / webchat), и тот
    вызовет skill-forge за ≤5 мин на одну идею.
    """
    if not _auto_skill_enabled():
        return
    if not is_owner(message.from_user):
        return

    # Найти последнюю запись для этого user_id
    user_id = message.from_user.id
    last_record: dict | None = None
    if JSONL_PATH.exists():
        for line in reversed(JSONL_PATH.read_text(encoding="utf-8").splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("user_id") == user_id and rec.get("kind") == "text":
                last_record = rec
                break

    if last_record is None:
        return

    content = (last_record.get("content") or "").strip()
    if not idea_intake.is_forgeable(last_record):
        log.info("not forgeable (len=%d): %r", len(content), content[:60])
        return

    _enqueue_forge(last_record, content)
    # Автономный pipeline: Karim не видит forge-деталей. Бот молча записывает,
    # notes-keeper (я) ловит forgeable через cron и сам зовёт skill-forge.
    log.info("auto-queued for forge: %r", content[:80])


def _enqueue_forge(record: dict, content: str) -> None:
    """Поставить forgeable идею в очередь на skill-forge.

    Формат очереди — jsonl, каждая строка:
      {
        "queued_at": ISO ts,
        "source": "ts=... user_id=...",
        "chat_id": int (куда слать результат),
        "username": str,
        "content": str (forgeable идея),
        "ts": ISO ts из notes.jsonl,
        "status": "pending" | "processing" | "done" | "failed",
        "result_summary": str | None,
        "processed_at": ISO ts | None,
      }
    """
    item = {
        "queued_at": datetime.now(MOSCOW_TZ).isoformat(timespec="seconds"),
        "source": f"ts={record.get('ts', '')} user_id={record.get('user_id', '')}",
        "chat_id": record.get("user_id"),
        "username": record.get("username"),
        "content": content,
        "ts": record.get("ts"),
        "status": "pending",
        "result_summary": None,
        "processed_at": None,
    }
    with FORGE_QUEUE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    log.info("queued for forge: %r", content[:80])


def ensure_owner_registered(user: types.User) -> None:
    cfg = load_config()
    cfg.setdefault("owner", {})
    cfg["owner"]["chat_id"] = user.id
    cfg["owner"]["user_id"] = user.id
    cfg["owner"]["first_name"] = user.first_name
    save_config(cfg)


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    user = message.from_user
    if not is_owner(user):
        await message.answer(
            "Принято ✅\n"
            "Я — бот для сбора заметок. Просто пришли текст или голосовое, "
            "и я сохраню."
        )
        return
    ensure_owner_registered(user)
    await message.answer(
        f"Привет, хозяин! 👋\n"
        f"Твой chat_id = {user.id} записан.\n\n"
        f"Команды:\n"
        f"/today — заметки за сегодня\n"
        f"/week — за неделю\n"
        f"/digest — непрочитанные с последней рассылки\n"
        f"/search <запрос> — поиск\n"
        f"/info [all|today|week|month] — сводка по идеям\n"
        f"/ideas [all|today|week|month] — валидные идеи (без мусора)\n"
        f"/skills [scope] — сгенерить драфты SKILL.md в Golden-Hour/skills/\n"
        f"/rejected [категория] — отсеянные (по категориям)\n"
        f"/split <идея> — разбить идею на под-идеи\n"
        f"/classify [new-only] — обновить ideas.md\n"
        f"/help — это сообщение"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if is_owner(message.from_user):
        await cmd_start(message)
    elif is_team_member(message.from_user):
        await message.answer(
            "Команды:\n"
            "/info [all|today|week|month] — сводка по идеям\n"
            "/ideas [all|today|week|month] — валидные идеи (без мусора)\n"
            "/skills [scope] — сгенерить драфты SKILL.md в Golden-Hour/skills/\n"
            "/rejected [категория] — отсеянные (по категориям)\n"
            "/split <идея> — разбить идею на под-идеи\n"
            "/classify [new-only] — обновить ideas.md\n\n"
            "Или просто пришли текст или голосовое — я запишу ✅"
        )
    else:
        await message.answer("Просто пришли текст или голосовое — я запишу ✅")


@dp.message(Command("today"))
async def cmd_today(message: Message) -> None:
    if not is_owner(message.from_user):
        return
    recs = read_jsonl_for("today")
    text = format_digest(recs, "📒 Заметки за сегодня")
    for chunk in _split_for_tg(text):
        await message.answer(chunk)


@dp.message(Command("week"))
async def cmd_week(message: Message) -> None:
    if not is_owner(message.from_user):
        return
    recs = read_jsonl_for("week")
    text = format_digest(recs, "📒 Заметки за последние 7 дней")
    for chunk in _split_for_tg(text):
        await message.answer(chunk)


@dp.message(Command("digest"))
async def cmd_digest(message: Message) -> None:
    if not is_owner(message.from_user):
        return
    cfg = load_config()
    last_ts = (cfg.get("digest") or {}).get("last_digest_at")
    recs = read_jsonl_since(last_ts)
    text = format_digest(recs, "📥 Дайджест с прошлой отправки")
    for chunk in _split_for_tg(text):
        await message.answer(chunk)
    cfg.setdefault("digest", {})
    cfg["digest"]["last_digest_at"] = datetime.now(MOSCOW_TZ).isoformat(timespec="seconds")
    cfg["digest"]["last_digest_message_count"] = len(recs)
    save_config(cfg)


@dp.message(Command("search"))
async def cmd_search(message: Message) -> None:
    if not is_owner(message.from_user):
        return
    q = (message.text or "").split(maxsplit=1)
    if len(q) < 2 or not q[1].strip():
        await message.answer("Использование: /search <текст>")
        return
    needle = q[1].strip().lower()
    hits = []
    for line in JSONL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if needle in (rec.get("content") or "").lower():
            hits.append(rec)
    text = format_digest(hits, f"🔍 Поиск: «{needle}»")
    for chunk in _split_for_tg(text):
        await message.answer(chunk)


_MAX_IDEAS_PER_INFO = 30
_MAX_CONTENT_LEN = 320


def _format_user_idea_block(r: dict) -> list[str]:
    """Одна идея в персональной выдаче /info: время, важность, тема, текст."""
    lines: list[str] = []
    time = r.get("time", "??:??")
    imp = r.get("importance", 0) or 0
    topic = (r.get("topic") or "").strip()
    emoji = note_kind_emoji(r.get("kind", "other"))

    header_parts = [f"💡 {time}"]
    if imp:
        stars = "⭐" * min(imp, 5)
        header_parts.append(f"важность {imp}/5 {stars}")
    header_parts.append(emoji)
    lines.append(" · ".join(header_parts))

    if topic:
        lines.append(f"   🏷 {topic}")

    content = (r.get("content") or "").strip()
    if not content:
        summary = (r.get("summary") or "").strip()
        content = summary or "(без текста)"

    if len(content) > _MAX_CONTENT_LEN:
        shown = content[: _MAX_CONTENT_LEN - 1].rstrip() + "…"
        lines.append(f"   «{shown}»")
        lines.append(f"   _и ещё {len(content) - _MAX_CONTENT_LEN} символов — полный текст в /ideas_")
    else:
        lines.append(f"   «{content}»")

    return lines


def build_user_ideas_report(ideas: list[dict], scope: str, user_label: str) -> str:
    """Сводка по идеям конкретного пользователя — читаемый список, не дашборд.

    Идеи группируются по дате (свежие сверху), с важностью, темой и полным
    текстом (с мягкой обрезкой если очень длинно). Лимит сверху — чтобы
    не превращать ответ в простыню.
    """
    scope_label = {
        "all": "все",
        "today": "сегодня",
        "week": "за неделю",
        "month": "за месяц",
    }.get(scope, scope)

    if not ideas:
        return (
            f"📊 Твои идеи ({scope_label})\n\n"
            f"Пока ничего. Пришли текст или голосовое — запишу."
        )

    total = len(ideas)
    truncated = total > _MAX_IDEAS_PER_INFO
    if truncated:
        ideas = ideas[:_MAX_IDEAS_PER_INFO]

    imps = [r.get("importance", 0) or 0 for r in ideas]
    avg_imp = sum(imps) / len(imps) if imps else 0

    topics_count: dict[str, int] = {}
    for r in ideas:
        t = (r.get("topic") or "").strip()
        if t:
            topics_count[t] = topics_count.get(t, 0) + 1
    top_topics = sorted(topics_count.items(), key=lambda kv: -kv[1])[:3]

    dates = sorted({r.get("date", "") for r in ideas if r.get("date")})
    if dates:
        date_range = dates[0] if dates[0] == dates[-1] else f"{dates[0]} → {dates[-1]}"
    else:
        date_range = "—"

    by_date: dict[str, list[dict]] = {}
    for r in ideas:
        d = r.get("date", "?")
        by_date.setdefault(d, []).append(r)
    for d in by_date:
        by_date[d].sort(key=lambda r: r.get("ts", ""), reverse=True)

    lines: list[str] = []
    lines.append(f"📊 Твои идеи ({scope_label}) — {user_label}")
    lines.append(f"📈 {total} шт. · {date_range} · средняя важность {avg_imp:.1f} ⭐")
    if top_topics:
        topics_str = ", ".join(f"{name} ({n})" for name, n in top_topics)
        lines.append(f"🏷 Топ-темы: {topics_str}")
    lines.append("")

    for d in sorted(by_date.keys(), reverse=True):
        day_ideas = by_date[d]
        lines.append(f"─── {d} ({len(day_ideas)} шт.) ───")
        lines.append("")
        for r in day_ideas:
            lines.extend(_format_user_idea_block(r))
        lines.append("")

    if truncated:
        lines.append(f"_…показано {_MAX_IDEAS_PER_INFO} из {total}. Полный список — /ideas {scope}_")

    return "\n".join(lines)


# ----- /info : categorized showcase of all good ideas -----

# Пути к SKILL.md — staging (workspace/Golden-Hour) и production (workspaces/golden-hour).
# Используется для пометки реализованных идей в /info.
import re as _re_info
from pathlib import Path as _Path_info
_INFO_SKILL_DIRS: list[tuple[str, _Path_info]] = [
    ("staging", _Path_info(r"C:\Users\Admin\.openclaw\workspace\Golden-Hour\skills")),
    ("prod",    _Path_info(r"C:\Users\Admin\.openclaw\workspaces\golden-hour\skills")),
]
_INFO_SOURCE_RE = _re_info.compile(r"<!--\s*source:\s*ts=(\S+)\s+user_id=(\S+)\s*-->")


def _load_realized_ideas_index() -> dict[tuple[str, int], dict]:
    """Индекс реализованных идей: {(ts, user_id): {slug, location}}.

    location ∈ {'staging', 'prod', 'both'} — где лежит SKILL.md.
    Если в обоих местах — location = 'both' (Karim смержил staging→prod).
    """
    index: dict[tuple[str, int], dict] = {}
    for location, dir_path in _INFO_SKILL_DIRS:
        if not dir_path.exists():
            continue
        for skill_dir in dir_path.iterdir():
            md = skill_dir / "SKILL.md"
            if not md.is_file():
                continue
            try:
                content = md.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            m = _INFO_SOURCE_RE.search(content)
            if not m:
                continue
            ts = m.group(1)
            try:
                uid = int(m.group(2))
            except ValueError:
                continue
            key = (ts, uid)
            slug = skill_dir.name
            existing = index.get(key)
            if existing:
                index[key] = {"slug": slug, "location": "both"}
            else:
                index[key] = {"slug": slug, "location": location}
    return index


_INFO_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("🧘 Wellness и состояние", ["mood", "устал", "эмоциональн", "здоров", "sleep", "energy", "отдых", "стресс", "выгор", "бодрост"]),
    ("🎓 Образование и учёба", ["конспект", "anki", "карточк", "урок", "учить", "шпаргалк", "зубрит", "зазубр", "материал", "теория", "лекц", "запомин", "выучив", "диктофон"]),
    ("⚡ Продуктивность и задачи", ["задач", "фокус", "помодоро", "декомпозиц", "разбив", "рефлекс", "streak", "чек-ин", "продуктивност", "сложност", "приоритет", "тріаж", "triage", "активн", "учёт действий"]),
    ("🤖 Автоматизация и скиллы", ["автоматич", "повторя", "навык", "skill", "автовыполн", "обрабатыв", "автоматиз", "обработ"]),
    ("💡 Контент и развлечения", ["стих", "мем", "погод", "юмор", "развлеч", "вечер", "утрен", "контент", "настроени"]),
    ("⚙️ Engineering и dev", ["ci ", "code review", "pipeline", "flaky", "ревью", "openclaw", "skill-forge", "knowledge", "кэш", "material cache", "материальн", "study-buddy", "frameworks", "spaced repetition"]),
    ("📚 Research и стратегия", ["аналог", "конкурент", "тренд", "обзор", "концепц", "macaron", "zerolambda", "plan + telegram", "дашборд", "sqlite", "yaml"]),
    ("💼 Бизнес и юридическое", ["оферт", "клиент", "юрид", "документ", "договор", "бизнес", "smb", "агентств", "заработ", "mrr", "консалтинг", "vps", "сервер"]),
]

_INFO_TRASH_PATTERNS: list[str] = [
    r"^\s*/",                          # /info, /ideas, etc.
    r"^\s*(ппп|ппр|аааа|test|тест)\s*$",
    r"хорошая идея для теста",
    r"добавить котиков",
    r"покажи\s+идеи",
    r"перечисли\s+(основные\s+)?идеи",
    r"^\s*сколько стоит",
    r"проверочный текст",
    r"голосовое.*не\s+удалось",
    r"фото без подписи",
    r"^\s*\(.*\)\s*$",
]

_INFO_TRASH_RES: list[_re_info.Pattern] = [_re_info.compile(p, _re_info.IGNORECASE) for p in _INFO_TRASH_PATTERNS]


def _info_is_trash(r: dict) -> bool:
    content = (r.get("content") or "").strip()
    if len(content) < 15:
        return True
    if content.endswith("?"):
        return True
    if r.get("kind") in ("photo", "sticker", "video") and len(content) < 30:
        return True
    for pat in _INFO_TRASH_RES:
        if pat.search(content):
            return True
    return False


def _info_categorize(r: dict) -> str:
    """Определить категорию идеи по keywords. Возвращает '📌 Прочее' если ничего не подошло."""
    blob = " ".join([
        (r.get("content") or ""),
        (r.get("summary") or ""),
        (r.get("topic") or ""),
    ]).lower()
    for cat, keywords in _INFO_CATEGORY_RULES:
        for kw in keywords:
            if kw in blob:
                return cat
    return "📌 Прочее"


def _info_format_idea_line(r: dict, realized: dict | None = None) -> str:
    """Одна идея в витрине — заголовок + подпись с автором, датой, важностью, темой.

    realized: если задано (dict с slug/location) — добавляет метку ✅ <slug> в подпись.
    """
    time = r.get("time", "??:??")
    date = r.get("date", "?")
    handle = author_handle(r)
    imp = r.get("importance", 0) or 0
    imp_str = f" · ⭐{imp}" if imp else ""
    topic = (r.get("topic") or "").strip()
    topic_str = f" 🏷{topic}" if topic else ""

    content = (r.get("content") or r.get("summary") or "").strip()
    if len(content) > 240:
        content = content[:239].rstrip() + "…"
    content_one = content.replace("\n", " · ")

    realized_str = ""
    if realized:
        slug = realized.get("slug", "?")
        loc = realized.get("location", "?")
        if loc == "both":
            realized_str = f" · ✅ `{slug}`"
        elif loc == "prod":
            realized_str = f" · ✅ `{slug}` (в golden-hour)"
        else:
            realized_str = f" · ✅ `{slug}` (драфт)"

    header = f"{date} {time} · {handle}{imp_str}{topic_str}{realized_str}"
    return f"• «{content_one}»\n  {header}"


def build_categorized_ideas_report(ideas: list[dict], scope: str) -> str:
    """Витрина ВСЕХ хороших идей команды, разбитых по категориям.

    Для каждой идеи проходит фильтр мусора и эвристически определяет
    категорию. Категории сортируются по количеству идей (популярные
    сверху). Внутри категории — свежие сверху. Реализованные идеи (есть
    SKILL.md в staging/prod с маркером source) помечаются ✅ <slug>.
    """
    scope_label = {
        "all": "все",
        "today": "сегодня",
        "week": "за неделю",
        "month": "за месяц",
    }.get(scope, scope)

    clean = [r for r in ideas if not _info_is_trash(r)]

    if not clean:
        return (
            f"📚 Витрина идей ({scope_label})\n\n"
            f"Пока ничего хорошего. Пришли текст или голосовое — запишу и категоризирую."
        )

    realized_index = _load_realized_ideas_index()
    realized_count = 0

    by_cat: dict[str, list[dict]] = {}
    for r in clean:
        cat = _info_categorize(r)
        by_cat.setdefault(cat, []).append(r)
    for cat in by_cat:
        by_cat[cat].sort(key=lambda r: r.get("ts", ""), reverse=True)

    cats_sorted = sorted(by_cat.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    dates = sorted({r.get("date", "") for r in clean if r.get("date")})
    if dates:
        date_range = dates[0] if dates[0] == dates[-1] else f"{dates[0]} → {dates[-1]}"
    else:
        date_range = "—"

    lines: list[str] = []
    lines.append(f"📚 Витрина идей команды ({scope_label})")
    lines.append(f"📊 {len(clean)} хороших идей в {len(by_cat)} категориях · {date_range}")
    if len(clean) < len(ideas):
        lines.append(f"_Отфильтровано {len(ideas) - len(clean)} шумных / тестовых записей_")
    lines.append("")

    for cat, items in cats_sorted:
        lines.append(f"─── {cat} ({len(items)}) ───")
        lines.append("")
        for r in items:
            key = (r.get("ts", ""), r.get("user_id", 0))
            realized = realized_index.get(key)
            if realized:
                realized_count += 1
            lines.append(_info_format_idea_line(r, realized))
        lines.append("")

    if realized_count:
        lines.append(f"_✅ Уже реализовано скиллами: {realized_count} из {len(clean)}_")

    return "\n".join(lines)


@dp.message(Command("info"))
async def cmd_info(message: Message) -> None:
    """/info [mine|stats|today|week|month] — витрина хороших идей команды.

    По умолчанию (без аргументов) — категоризированная витрина ВСЕХ хороших
    идей, отсортированных по категориям. Мусор и тестовые записи отфильтрованы.

    Аргументы:
      `mine`      — только твои идеи (группировка по дате)
      `stats`     — командная статистика (топ-авторы, по дням)
      today|week|month — фильтр по дате (по умолчанию all)
    """
    if not is_team_member(message.from_user):
        return

    parts = (message.text or "").split(maxsplit=1)
    arg = parts[1].strip().lower() if len(parts) == 2 else ""

    want_mine = arg == "mine"
    want_stats = arg in {"stats", "team", "all", "everyone"}
    if want_stats:
        scope = "all"
    else:
        scope = _parse_scope(message)

    user = message.from_user
    recs = _load_records()
    recs = _deduplicate_records(recs)
    all_ideas = _filter_records(recs, scope)

    if want_mine:
        my_ideas = [r for r in all_ideas if r.get("user_id") == user.id]
        my_ideas.sort(key=lambda r: r.get("ts", ""), reverse=True)
        user_label = author_label(user)
        text = build_user_ideas_report(my_ideas, scope, user_label)
    elif want_stats:
        text = build_ideas_report(all_ideas, scope)
    else:
        text = build_categorized_ideas_report(all_ideas, scope)

    for chunk in _split_for_tg(text):
        await message.answer(chunk, parse_mode=None)


def _deduplicate_records(records: list[dict]) -> list[dict]:
    """Оставить только одну запись для каждой группы (user_id + content).

    Из каждой группы берётся новейшая (по ts). Полное совпадение content
    трактуется как дубль — это самый строгий и предсказуемый критерий.
    Применяется ДО классификации, чтобы /ideas, /info и дайджесты не
    показывали одну идею дважды.
    """
    if not records:
        return []
    seen: dict[tuple, dict] = {}
    for r in records:
        content = (r.get("content") or "").strip()
        if not content:
            # Пустой content — отдельная группа; всё равно оставляем как есть.
            key = (r.get("user_id"), "", r.get("ts", ""))
        else:
            key = (r.get("user_id"), content)
        ts = r.get("ts", "")
        existing = seen.get(key)
        if existing is None or ts > existing.get("ts", ""):
            seen[key] = r
    return list(seen.values())


@dp.message(Command("ideas"))
async def cmd_ideas(message: Message) -> None:
    """/ideas [scope] — валидные идеи без мусора (список).

    Прогоняет через:
      1. _deduplicate_records — полный дедуп по (user_id, content), оставляем
         новейшую запись из каждой группы (без ограничения по времени).
      2. idea_intake.classify (check_duplicates=False) — отсев команд,
         стоп-слов, паттернов, медиа-без-подписи, пустых, is_idea=false.
      3. _filter_records — фильтр по scope (по дате).

    scope: all (по умолчанию) | today | week | month
    """
    if not is_team_member(message.from_user):
        return
    scope = _parse_scope(message)

    recs = _load_records()
    recs = _deduplicate_records(recs)
    state = idea_intake.load_state()
    kept, _rejected = idea_intake.classify(recs, state, check_duplicates=False)
    ideas = _filter_records(kept, scope)
    text = build_ideas_list(ideas, scope)
    for chunk in _split_for_tg(text):
        await message.answer(chunk, parse_mode=None)


@dp.message(Command("rejected"))
async def cmd_rejected(message: Message) -> None:
    """/rejected [категория] — отсеянные идеи в категоризированном виде.

    Без аргументов: сводка по категориям + топ-авторов + подсказка.
    С аргументом (cat_id): список записей в этой категории.

    Доступные cat_id зависят от reason'ов; типичные:
        command, test_input, media_no_caption, empty, duplicate, manual
    """
    if not is_team_member(message.from_user):
        return

    parts = (message.text or "").split(maxsplit=1)
    cat_filter = parts[1].strip().lower() if len(parts) == 2 else None

    # Переклассифицируем (без записи файлов — чисто для просмотра)
    state = idea_intake.load_state()
    records = idea_intake.load_records()
    _, rejected = idea_intake.classify(records, state, check_duplicates=False)
    by_cat = idea_intake.categorize(rejected)

    valid_ids = {c[0] for c in idea_intake.CATEGORIES} | {"unknown"}

    if cat_filter:
        if cat_filter not in valid_ids:
            avail = ", ".join(sorted(valid_ids))
            text = (
                f"❓ Неизвестная категория: {cat_filter}\n\n"
                f"Доступные: {avail}"
            )
        else:
            items = by_cat.get(cat_filter, [])
            text = idea_intake.build_rejected_list(items, cat_filter)
    else:
        text = idea_intake.build_rejected_columns(rejected)

    for chunk in _split_for_tg(text):
        await message.answer(chunk, parse_mode=None)


@dp.message(Command("split"))
async def cmd_split(message: Message) -> None:
    """/split <идея> — разбить комплексную идею на атомарные под-идеи.

    Без аргумента показывает usage. С аргументом — прогоняет сплиттер и выводит
    нумерованный список под-идей. Если идея атомарная — сообщает об этом.
    """
    if not is_team_member(message.from_user):
        return

    text = (message.text or "")
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Использование: /split <текст идеи>\n\n"
            "Пример:\n"
            "/split Бот должен понимать настроение, присылать мемы "
            "и помогать с CI",
            parse_mode=None,
        )
        return

    idea = parts[1].strip()
    subs = idea_intake.split_idea(idea)

    if len(subs) <= 1:
        out = (
            "🪓 Разбивка идеи\n\n"
            f"Исходная идея:\n  «{idea}»\n\n"
            "_Идея выглядит атомарной — сплиттер не нашёл под-идей._\n"
            "Попробуй переформулировать:\n"
            "  • через «и», «также», «а ещё»;\n"
            "  • разбить на 2-3 предложения (по точкам)."
        )
    else:
        out_lines = [
            f"🪓 Разбивка идеи — {len(subs)} под-идей:",
            "",
            "Исходная идея:",
            f"  «{idea}»",
            "",
            "Под-идеи:",
        ]
        for i, sub in enumerate(subs, 1):
            out_lines.append(f"  {i}. {sub}")
        out_lines.append("")
        out_lines.append(
            "💡 Сохранить? Сейчас сплит только показывает. "
            "Чтобы под-идеи попали в ideas.md — отправь их текстом с темой."
        )
        out = "\n".join(out_lines)

    for chunk in _split_for_tg(out):
        await message.answer(chunk, parse_mode=None)


@dp.message(Command("skills"))
async def cmd_skills(message: Message) -> None:
    """/skills [scope] — сгенерировать драфты SKILL.md из идей (локальный fallback).

    Сейчас: локальная генерация через idea_to_skill.run_pipeline().
    В будущем (после перезапуска gateway с skill-forge): main будет
    делегировать субагенту skill-forge, который сделает research + design
    + tests + save. Пока skill-forge не прописан в OpenClaw runtime, бот
    использует локальный fallback.

    Cursor увидит новые папки сразу. Карим коммитит и пушит в Golden-Hour.

    scope: all (по умолчанию) | today | week | month
    """
    if not is_owner(message.from_user):
        return
    scope = _parse_scope(message, default="all")
    summary = idea_to_skill.run_pipeline(scope=scope)
    text = idea_to_skill.make_digest_text(summary)
    for chunk in _split_for_tg(text):
        await message.answer(chunk, parse_mode=None)


@dp.message(Command("classify"))
async def cmd_classify(message: Message) -> None:
    """/classify [new-only] — прогнать классификатор идей и обновить memory/ideas.md.

    Без аргументов: переклассифицировать ВСЁ с нуля.
    С аргументом new-only: только записи после последнего запуска.
    """
    if not is_team_member(message.from_user):
        return

    parts = (message.text or "").split(maxsplit=1)
    new_only = len(parts) == 2 and parts[1].strip().lower() in {"new-only", "new"}

    state = idea_intake.load_state()
    since = state.get("last_run_ts") if new_only else None
    stats = idea_intake.run(since=since, dry_run=False)

    lines: list[str] = []
    lines.append(f"🧮 Классификация {'(только новые)' if new_only else '(полная)'}")
    lines.append("")
    lines.append(f"📥 Записей: {stats['scanned']}")
    lines.append(f"💡 Идей: {stats['ideas']}")
    lines.append(f"🗑  Отсеяно: {stats['rejected']}")
    if stats.get("categories"):
        lines.append("")
        lines.append("По категориям:")
        for cat_id, n in stats["categories"].items():
            title = next((t for c, t, *_ in idea_intake.CATEGORIES if c == cat_id), cat_id)
            lines.append(f"  • {title}: {n}")
    elif stats["reasons"]:
        lines.append("")
        lines.append("По причинам:")
        for reason, n in stats["reasons"].items():
            lines.append(f"  • {reason}: {n}")
    if "written_to" in stats:
        rel = Path(stats["written_to"]).relative_to(WORKSPACE)
        lines.append("")
        lines.append(f"✅ Идеи — {rel}")
    if "rejected_written_to" in stats:
        rel_r = Path(stats["rejected_written_to"]).relative_to(WORKSPACE)
        lines.append(f"✅ Отсеянные — {rel_r}")

    for chunk in _split_for_tg("\n".join(lines)):
        await message.answer(chunk, parse_mode=None)


# ----- Generic note handlers -----


async def _handle_text_note(message: Message) -> None:
    user = message.from_user
    if not user or not message.text:
        return
    text = message.text

    # Guard 1: greetings — НЕ записывать как идею, короткий ответ
    if _is_greeting(text):
        log.info("greeting skipped: %r", text[:60])
        if is_owner(user):
            await message.answer("Привет! 👋 Жду идей.")
        else:
            await message.answer("Принято ✅")
        return

    items = idea_intake.split_bullet_list(text) or [text]
    for item in items:
        append_note(user, "text", item)
    n = len(items)
    if is_owner(user):
        await message.answer(
            f"Записано 📝 ({n} {'идея' if n == 1 else 'идеи' if 2 <= n <= 4 else 'идей'})"
            if n > 1
            else "Записано 📝"
        )
    else:
        await message.answer(
            f"Принято ✅ ({n} пунктов)" if n > 1 else "Принято ✅"
        )
    # Guard 2: короткие (< 3 слов) — записали, но НЕ триггерим auto_skill
    if _is_short_message(text):
        log.info("short message, skip auto_skill: %r", text[:60])
        return

    # Авто-конвертация в драфт скилла (если включено)
    await _maybe_auto_skill_from_text(message)


async def _handle_voice(message: Message) -> None:
    user = message.from_user
    if not user or not message.voice:
        return
    duration = message.voice.duration or 0
    file_id = message.voice.file_id

    # Транскрибация только для owner (гостям не нужны тяжёлые модели).
    transcript: str | None = None
    if is_owner(user):
        transcript = await _try_transcribe_voice(message, file_id)

    if transcript:
        content = transcript
        snippet = transcript[:3500] + ("…" if len(transcript) > 3500 else "")
        await message.answer(f"🎙 Транскрипт ({duration}s):\n\n{snippet}")
        record = append_note(user, "voice", content, duration=duration)
        # Если forgeable (длинный транскрипт) — в очередь skill-forge.
        try:
            if idea_intake.is_forgeable({"content": content, "kind": "voice"}):
                _enqueue_forge(record, content)
        except Exception as e:
            log.warning("forge queue check failed: %s", e)
    else:
        content = f"(голосовое {duration}s, без транскрипта)"
        append_note(user, "voice", content, duration=duration)
        if is_owner(user):
            await message.answer(f"Записано 🎙 ({duration}s) — без транскрипта (Whisper недоступен)")
        else:
            await message.answer("Принято ✅")


async def _try_transcribe_voice(message: Message, file_id: str) -> str | None:
    """Скачать .ogg из Telegram и прогнать через transcribe.py. None при любой ошибке."""
    try:
        ogg_path = MEDIA_DIR / f"{file_id}.ogg"
        if not ogg_path.exists():
            file = await message.bot.get_file(file_id)
            await message.bot.download_file(file.file_path, destination=str(ogg_path))
            log.info("voice downloaded: %s (%d bytes)", ogg_path, ogg_path.stat().st_size)
        return await _transcribe_audio(ogg_path)
    except Exception as e:
        log.warning("voice download/transcribe pipeline failed: %s", e)
        return None


async def _transcribe_audio(ogg_path: Path) -> str | None:
    """Запустить transcribe.py через subprocess. Прочитать <ogg>.txt. None при ошибке."""
    if not TRANSCRIBE_SCRIPT.exists():
        log.warning("transcribe.py not found: %s", TRANSCRIBE_SCRIPT)
        return None
    try:
        proc = subprocess.run(
            [
                TRANSCRIBE_PYTHON,
                str(TRANSCRIBE_SCRIPT),
                str(ogg_path),
                "--model", "small",
                "--language", "ru",
                "--no-timestamps",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TRANSCRIBE_TIMEOUT,
        )
        if proc.returncode != 0:
            log.warning("transcribe.py rc=%d, stderr=%s", proc.returncode, (proc.stderr or "")[:200])
            return None
        txt_path = ogg_path.with_suffix(".txt")
        if txt_path.exists():
            return txt_path.read_text(encoding="utf-8").strip() or None
        return None
    except subprocess.TimeoutExpired:
        log.warning("transcribe.py timeout %ds for %s", TRANSCRIBE_TIMEOUT, ogg_path)
        return None
    except Exception as e:
        log.warning("transcribe.py error: %s", e)
        return None


async def _handle_photo(message: Message) -> None:
    user = message.from_user
    if not user:
        return
    caption = message.caption or "(фото без подписи)"
    append_note(user, "photo", caption)
    await message.answer("Принято ✅")


async def _handle_document(message: Message) -> None:
    user = message.from_user
    if not user:
        return
    fname = message.document.file_name if message.document else "файл"
    caption = message.caption or ""
    content = f"{fname}" + (f" — {caption}" if caption else "")
    append_note(user, "document", content)
    await message.answer("Принято ✅")


async def _handle_other(message: Message) -> None:
    user = message.from_user
    if not user:
        return
    append_note(user, "other", message.text or f"[{message.content_type}]")
    await message.answer("Принято ✅")


# Order matters: text first, then media
dp.message.register(_handle_text_note, F.text, ~F.text.startswith("/"))
dp.message.register(_handle_voice, F.voice)
dp.message.register(_handle_photo, F.photo)
dp.message.register(_handle_document, F.document)
dp.message.register(_handle_other)


# ----- Background digest -----


async def periodic_digest() -> None:
    cfg = load_config()
    interval = (cfg.get("digest") or {}).get("interval_hours", 3)
    chat_id = (cfg.get("owner") or {}).get("chat_id")
    while True:
        try:
            await asyncio.sleep(interval * 3600)
            cfg = load_config()
            chat_id = (cfg.get("owner") or {}).get("chat_id")
            if not chat_id:
                continue
            last_ts = (cfg.get("digest") or {}).get("last_digest_at")
            recs = read_jsonl_since(last_ts)
            if not recs:
                continue
            text = format_digest(recs, f"⏰ Дайджест каждые {interval}ч")
            for chunk in _split_for_tg(text):
                await bot.send_message(chat_id=chat_id, text=chunk)
            cfg.setdefault("digest", {})
            cfg["digest"]["last_digest_at"] = datetime.now(MOSCOW_TZ).isoformat(timespec="seconds")
            cfg["digest"]["last_digest_message_count"] = len(recs)
            save_config(cfg)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("periodic_digest error: %s", e)
            await asyncio.sleep(60)


async def set_bot_commands() -> None:
    """Обновить меню команд бота во всех scope'ах."""
    commands = [
        BotCommand(command="start", description="Регистрация владельца"),
        BotCommand(command="info", description="Сводка по идеям"),
        BotCommand(command="ideas", description="Все идеи участников"),
        BotCommand(command="skills", description="Сгенерировать драфты SKILL.md из идей"),
        BotCommand(command="rejected", description="Отсеянные идеи (по категориям)"),
        BotCommand(command="split", description="Разбить идею на под-идеи"),
        BotCommand(command="classify", description="Обновить ideas.md"),
    ]
    scopes = [
        BotCommandScopeDefault(),
        BotCommandScopeAllPrivateChats(),
        BotCommandScopeAllGroupChats(),
    ]
    names = [c.command for c in commands]
    for scope in scopes:
        try:
            await bot.set_my_commands(commands, scope=scope)
        except Exception as e:  # noqa: BLE001
            log.warning("set_my_commands failed for %s: %s", scope, type(e).__name__)
    log.info("Bot menu commands set to: %s", names)


async def on_startup() -> None:
    cfg = load_config()
    cfg["started_at"] = datetime.now(MOSCOW_TZ).isoformat(timespec="seconds")
    save_config(cfg)
    # Retry get_me: handles transient network blips at startup
    for attempt in range(1, 6):
        try:
            me = await bot.get_me()
            log.info("Bot started: @%s (id %s) on attempt %d", me.username, me.id, attempt)
            await set_bot_commands()
            return
        except Exception as e:  # noqa: BLE001
            log.warning("get_me failed (attempt %d/5): %s", attempt, type(e).__name__)
            await asyncio.sleep(min(2 ** attempt, 30))
    log.error("get_me failed after 5 attempts; proceeding to polling anyway")


async def main() -> None:
    await on_startup()
    asyncio.create_task(periodic_digest())
    await dp.start_polling(bot, allowed_updates=["message"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped")
