"""Idea intake: читает notes.jsonl, отсеивает мусор, пишет ideas.md.

Контракт:
- Вход: memory/notes.jsonl (формат, в который пишет telegram_notes_bot)
- Выход: memory/ideas.md (markdown, идеи по дням)
- Доп. выход: memory/ideas_rejected.md (markdown, отсеянные с категоризацией)
- Побочный эффект: memory/ideas_state.json (last_run_ts, seen для дедупа)

Правила отсева (применяются по порядку, первое срабатывание побеждает):
    1. content пустой / None
    2. kind == "other" + content начинается с "/" → это команда
    3. kind in {voice, photo} + len(content) < 10 → медиа без полезной подписи
    4. len(content.strip()) < MIN_CONTENT_LEN → слишком коротко
    5. content в STOP_WORDS → стоп-слово
    6. content матчит GARBAGE_PATTERNS → мусорный паттерн (1-3 буквы, повтор одного символа)
    7. дубликат: тот же content от того же user_id в пределах DEDUP_WINDOW_MIN
    8. is_idea == False в исходной записи (ручная разметка)

Ручная разметка is_idea имеет приоритет над автоматикой.

Запуск:
    python scripts/idea_intake.py              # переклассифицировать ВСЁ с нуля
    python scripts/idea_intake.py --new-only   # только записи после last_run_ts
    python scripts/idea_intake.py --dry-run    # не писать, только статистика

Использование из бота:
    from idea_intake import classify, load_records, write_ideas_md, load_state
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------- Пути ----------

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
JSONL_PATH = WORKSPACE / "memory" / "notes.jsonl"
IDEAS_MD_PATH = WORKSPACE / "memory" / "ideas.md"
REJECTED_MD_PATH = WORKSPACE / "memory" / "ideas_rejected.md"
STATE_PATH = WORKSPACE / "memory" / "ideas_state.json"

# Реестр user_id → handle/name (см. memory/members.json).
# Импортируем после определения путей, чтобы members.py мог взять WORKSPACE от себя.
import members as _members

MOSCOW_TZ = timezone(timedelta(hours=3))

# ---------- Правила отсева ----------

MIN_CONTENT_LEN = 3
DEDUP_WINDOW_MIN = 30  # окно для дедупликации, минут

# Forgeable: идею можно отправить в skill-workshop.
# Phase 1 (2026-06-18): критерий — длина content > 30 символов (т.е. содержательная мысль).
# В Phase 2+ Фельпик будет consume `forgeable` и предлагать Кариму через Telegram.
FORGEABLE_MIN_LEN = 30

# Точные совпадения (lowercase, strip)
STOP_WORDS: set[str] = {
    # тесты/проверки
    "тест", "тест.", "тест!", "тест?",
    "проверка", "проверка связи", "проверочный текст",
    # частые «набивки» из текущей истории
    "ппп", "ппр", "прпр", "ыыы", "qqq", "zzz", "asd", "fgh",
    # подтверждения
    "ок", "ок.", "ок!", "ок?", "окей", "да", "нет", "+", "-",
    "..", "...", "…",
    # одиночные эмодзи-подтверждения
    "👍", "👌", "✅", "❌", "🆗", "🤝", "🙏",
}

# Паттерны: запись мусор, если контент матчит
GARBAGE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^[a-zа-яё]{1,3}$", re.IGNORECASE),  # 1-3 буквы
    re.compile(r"^[^a-zа-яё0-9]+$", re.IGNORECASE),  # только спецсимволы/эмодзи
    re.compile(r"^(.)\1{2,}$"),                       # один символ повторён 3+ раз (ааа, 111, ---)
    re.compile(r"^(.)\1{4,}$"),                       # один символ повторён 5+ раз
)

# Плейсхолдеры, которые бот пишет в content при отсутствии реального контента.
# Сюда же — известные форматы от бота (голосовое/фото без полезной подписи).
BOT_PLACEHOLDERS: set[str] = {
    "(фото без подписи)",
}
VOICE_PLACEHOLDER_RE = re.compile(r"^\(голосовое \d+s, без транскрипта\)$")

# Эмодзи по типу записи (синхронизировано с bot'ом)
KIND_EMOJI: dict[str, str] = {
    "text": "💬",
    "voice": "🎙",
    "photo": "🖼",
    "document": "📎",
    "sticker": "😺",
    "video": "🎬",
    "other": "📝",
}

# ---------- Сплиттер комплексных идей ----------

# Разбивка по границам предложений: [.!?] + пробел + заглавная буква.
# Поддерживает кириллицу и латиницу.
SPLIT_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[А-ЯЁA-Z])")

# Связки для разбивки одиночного предложения.
# Используем границы слов, чтобы не цеплять «и» внутри слов.
SPLIT_CONNECTOR_RE = re.compile(
    r"\s+(?:и|также|а\s+также|а\s+ещё|плюс|к\s+тому\s+же|а\s+кроме\s+того)\s+",
    re.IGNORECASE,
)

# Маркированные списки: * / - / • в начале строки (в т.ч. вложенные).
BULLET_LINE_RE = re.compile(r"^\s*[\*\-•]\s+")
# Пометки-уточнения вроде *(написано скомканно...)*
PAREN_NOTE_RE = re.compile(r"\*\([^)]*\)\*")


def _clean_bullet_item(text: str) -> str:
    text = PAREN_NOTE_RE.sub("", text).strip()
    if text.startswith("+"):
        text = text[1:].strip()
    return re.sub(r"\s+", " ", text)


def split_bullet_list(content: str, min_len: int = 4) -> list[str] | None:
    """Если content — маркированный список, вернуть пункты. Иначе None."""
    if not content or "*" not in content:
        return None
    items: list[str] = []
    for ln in content.splitlines():
        if not BULLET_LINE_RE.match(ln):
            continue
        text = _clean_bullet_item(BULLET_LINE_RE.sub("", ln, count=1))
        if len(text) >= min_len:
            items.append(text)
    if len(items) >= 2:
        return items
    return None


def split_idea(content: str, min_substr_len: int = 12) -> list[str]:
    """Разбить «комплексную» идею на атомарные под-идеи.

    Возвращает список под-идей. Если идея простая — список из одного элемента
    (оригинал без изменений).

    Правила (по порядку, первое срабатывание побеждает):
        0. Маркированный список (* / - / •) — каждый пункт = под-идея.
        1. Multi-sentence: >= 2 предложений (границы: . ! ? + пробел + заглавная)
           → каждое предложение = под-идея.
        2. Одиночное предложение со связками (и / также / а ещё / плюс / к тому же /
           а кроме того): если все части >= min_substr_len символов, разбиваем.
        3. Иначе — оригинал как одна под-идея.

    min_substr_len — минимальная длина подстроки, чтобы считать её самостоятельной
                    под-идеей. Защищает от ложных срабатываний на коротких связках.
    """
    if not content or not content.strip():
        return []

    text = content.strip()

    bullets = split_bullet_list(text, min_len=min(min_substr_len, 4))
    if bullets:
        return bullets

    # 1) Multi-sentence
    sentences = SPLIT_SENTENCE_RE.split(text)
    sentences = [s.strip().rstrip(".!?") for s in sentences if s.strip()]
    if len(sentences) >= 2:
        return sentences

    # 2) Single sentence with connectors
    parts = SPLIT_CONNECTOR_RE.split(text)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) >= 2 and all(len(p) >= min_substr_len for p in parts):
        return parts

    return [text]

# ---------- Категории отсева ----------

# Маппинг reason → (category_id, category_title, emoji, описание).
# reason: то, что возвращает is_garbage() и 'is_idea=false' / 'duplicate'.
#
# Title звучит как «сигнал для улучшения проекта», а не как «тип мусора».
# Потому что каждая категория rejected'ов = подсказка, что подкрутить в боте.
CATEGORIES: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    (
        "command", "\U0001f4a1 Команды, не нашлось в меню", "\U0001f4a1",
        "Пользователь слал текстом то, что хотел как команду (вероятно, /info, /classify, /ideas). "
        "Сигнал: меню неполное или хелп нечитаемый.",
        ("command",),
    ),
    (
        "test_input", "\U0001f9ea Шум и тест: непонятно, что слать", "\U0001f9ea",
        "Стоп-лист, мусорные паттерны (1-3 буквы, повтор символа), случайные набивки. "
        "Сигнал: нужен onboarding, примеры или first-run подсказка.",
        ("stop_word", "pattern", "too_short"),
    ),
    (
        "empty", "\U0001f4ed Пусто: что-то потерялось по дороге", "\U0001f4ed",
        "Полностью пустой content. Обычно артефакт обёрток или медиа без тела. "
        "Сигнал: бот не логирует причину пустого сообщения.",
        ("empty",),
    ),
    (
        "media_no_caption", "\U0001f5bc Медиа без контекста", "\U0001f5bc",
        "Голосовые/фото с автосгенерированной заглушкой (нет полезной подписи). "
        "Сигнал: бот должен просить подпись или принимать медиа as-is.",
        ("media_no_caption:voice", "media_no_caption:photo"),
    ),
    (
        "duplicate", "\U0001f501 Дубли: нет подтверждения?", "\U0001f501",
        "Один и тот же content от того же автора в пределах 30 минут. "
        "Сигнал: первый раз бот не ответил / не подтвердил, и пользователь повторил.",
        ("duplicate",),
    ),
    (
        "manual", "\U0001f6ab Снято вручную", "\U0001f6ab",
        "Помечены is_idea: false в notes.jsonl. Твоё решение, action не нужен.",
        ("is_idea=false",),
    ),
]

# Быстрый лookup: reason → category_id
REASON_TO_CATEGORY: dict[str, str] = {}
for cat_id, _title, _emoji, _desc, reasons in CATEGORIES:
    for r in reasons:
        REASON_TO_CATEGORY[r] = cat_id


def categorize(rejected: list[tuple[dict, str]]) -> dict[str, list[tuple[dict, str]]]:
    """Сгруппировать (record, reason) по category_id.

    Если reason не нашёлся в маппинге — попадает в 'unknown' (отдельная категория).
    """
    out: dict[str, list[tuple[dict, str]]] = {cat_id: [] for cat_id, *_ in CATEGORIES}
    out["unknown"] = []
    for rec, reason in rejected:
        cat = REASON_TO_CATEGORY.get(reason, "unknown")
        out[cat].append((rec, reason))
    return out


# ---------- Классификация ----------

def is_garbage(record: dict) -> str | None:
    """Вернуть причину отсева или None, если запись — идея.

    Возвращает короткий строковый код причины для отладки и статистики.
    """
    content = (record.get("content") or "").strip()
    kind = record.get("kind", "other")

    if not content:
        return "empty"

    if kind == "other" and content.startswith("/"):
        return "command"

    if kind in ("voice", "photo"):
        # Известные плейсхолдеры бота ("(фото без подписи)", "(голосовое Xs, без транскрипта)")
        if content in BOT_PLACEHOLDERS or VOICE_PLACEHOLDER_RE.match(content):
            return f"media_no_caption:{kind}"
        # Fallback: совсем короткий content для медиа = скорее всего заглушка
        if len(content) < 10:
            return f"media_no_caption:{kind}"

    if len(content) < MIN_CONTENT_LEN:
        return "too_short"

    if content.lower() in STOP_WORDS:
        return "stop_word"

    for pat in GARBAGE_PATTERNS:
        if pat.match(content):
            return f"pattern"

    return None


def _dup_key(record: dict) -> str:
    return f"{record.get('user_id')}::{(record.get('content') or '').strip().lower()}"


def _is_duplicate(record: dict, state: dict) -> bool:
    """Тот же content от того же user в пределах DEDUP_WINDOW_MIN минут."""
    key = _dup_key(record)
    seen_at = state.get("seen", {}).get(key)
    if not seen_at:
        return False
    try:
        rec_ts = datetime.fromisoformat(record["ts"])
        seen_ts = datetime.fromisoformat(seen_at)
    except (KeyError, ValueError):
        return False
    return abs((rec_ts - seen_ts).total_seconds()) < DEDUP_WINDOW_MIN * 60


def _remember(record: dict, state: dict) -> None:
    state.setdefault("seen", {})[_dup_key(record)] = record.get("ts")


def is_forgeable(record: dict, min_len: int = FORGEABLE_MIN_LEN) -> bool:
    """True, если идею можно отправить в skill-workshop.

    Текущий критерий (Phase 1, 2026-06-18): длина content (без учёта
    автора/метаданных) > min_len символов. Защита от «заголовков» и
    слишком коротких мыслей, которые не оформить в скилл.

    В Phase 2/3 можно добавить: наличие примеров, тему, длину > 200
    (для full skill vs tiny-skill) и т.д.
    """
    content = (record.get("content") or "").strip()
    return len(content) > min_len


def load_records(since: str | None = None) -> list[dict]:
    """Загрузить записи из jsonl. Если since задан — только позже него."""
    if not JSONL_PATH.exists():
        return []
    out: list[dict] = []
    for line in JSONL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if since is None or rec.get("ts", "") > since:
            out.append(rec)
    return out


def classify(
    records: list[dict],
    state: dict | None = None,
    *,
    check_duplicates: bool = True,
) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Разделить записи на (идеи, отсев). state мутируется (запоминаем seen).

    check_duplicates:
      True  — проверять дубли (для инкрементального режима, --new-only).
              Новые записи сверяются с ранее seen; старые (< last_run_ts)
              пропускают dup-check (это «уже обработанные» в прошлом прогоне).
      False — не проверять дубли вообще (для полной переклассификации,
              детерминированный выход).
    """
    if state is None:
        state = load_state()

    ideas: list[dict] = []
    rejected: list[tuple[dict, str]] = []

    last_run_ts = state.get("last_run_ts") if check_duplicates else None

    for rec in records:
        # Ручная разметка имеет приоритет
        if rec.get("is_idea") is False:
            rejected.append((rec, "is_idea=false"))
            continue

        reason = is_garbage(rec)
        if reason:
            rejected.append((rec, reason))
            continue

        # Дубль: только для новых записей (после прошлого прогона).
        if check_duplicates:
            rec_ts = rec.get("ts", "")
            is_new = last_run_ts is None or rec_ts > last_run_ts
            if is_new and _is_duplicate(rec, state):
                rejected.append((rec, "duplicate"))
                continue

        ideas.append(rec)
        _remember(rec, state)

    # Phase 1 (2026-06-18): аннотируем каждую идею полем `forgeable`,
    # чтобы Felpik (Phase 2) мог отбирать кандидатов в skill-workshop
    # без повторного сканирования контента. Не мутируем input records —
    # делаем shallow copy с дополнительным полем.
    annotated: list[dict] = []
    for rec in ideas:
        copy = dict(rec)
        copy["forgeable"] = is_forgeable(rec)
        annotated.append(copy)

    return annotated, rejected


# ---------- Рендер и запись ----------

def render_ideas_md(ideas: list[dict]) -> str:
    """Сгенерировать тело ideas.md (без шапки файла)."""
    if not ideas:
        return "_Пока идей нет._\n"

    ideas = sorted(ideas, key=lambda r: (r.get("date", ""), r.get("time", "")))

    by_day: dict[str, list[dict]] = {}
    for r in ideas:
        by_day.setdefault(r.get("date", "?"), []).append(r)

    lines: list[str] = []
    for day in sorted(by_day.keys(), reverse=True):
        lines.append(f"## {day}")
        lines.append("")
        for r in by_day[day]:
            handle = _members.resolve_handle(r)
            emoji = KIND_EMOJI.get(r.get("kind", "other"), "📝")
            time = r.get("time", "??:??")
            topic = r.get("topic")

            lines.append(f"### {time} — {handle} {emoji}")
            if topic:
                lines.append(f"_тема: {topic}_")
            lines.append("")
            lines.append((r.get("content") or "").strip())
            lines.append("")

    return "\n".join(lines)


def write_ideas_md(ideas: list[dict], header_note: str = "") -> Path:
    """Записать ideas.md. Возвращает путь к файлу."""
    body = render_ideas_md(ideas)
    head = "# 💡 Идеи\n\n"
    if header_note:
        head += f"> {header_note}\n\n"
    head += f"_Всего: {len(ideas)}._\n\n---\n\n"
    IDEAS_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    IDEAS_MD_PATH.write_text(head + body, encoding="utf-8")
    return IDEAS_MD_PATH


# ---------- Рендер rejected ----------

def _short_for_table(text: str, limit: int = 80) -> str:
    """Ещё короче, чем _shorten: для таблиц в rejected.md."""
    body = (text or "").strip().replace("\n", " ").replace("|", "\\|")
    if not body:
        body = "_(пусто)_"
    if len(body) > limit:
        body = body[: limit - 1] + "…"
    return body


def _shorten(text: str, limit: int = 200) -> str:
    """Безопасное обрезание текста + замена переносов на пробелы."""
    body = (text or "").strip().replace("\n", " ")
    if len(body) > limit:
        body = body[: limit - 1] + "…"
    return body


def render_rejected_md(rejected: list[tuple[dict, str]]) -> str:
    """Сгенерировать тело ideas_rejected.md (без шапки файла).

    rejected: список (record, reason) из classify().
    Категории — в порядке CATEGORIES. Неизвестные reason'ы идут в конец (unknown).
    """
    if not rejected:
        return "_Пока ничего не отсеяно._\n"

    by_cat = categorize(rejected)
    total = len(rejected)

    # Топ-авторов мусора (по всем категориям)
    by_author: dict[str, int] = {}
    for rec, _ in rejected:
        handle = _members.resolve_name(rec)
        by_author[handle] = by_author.get(handle, 0) + 1
    top_garbage = sorted(by_author.items(), key=lambda kv: -kv[1])[:5]

    lines: list[str] = []

    # Сводка по категориям
    lines.append("## Сводка по категориям")
    lines.append("")
    lines.append("| Категория | Кол-во | Доля |")
    lines.append("|---|---:|---:|")
    for cat_id, title, _emoji, _desc, _reasons in CATEGORIES:
        n = len(by_cat.get(cat_id, []))
        if n == 0:
            continue
        pct = (n / total) * 100 if total else 0
        lines.append(f"| {title} | {n} | {pct:.0f}% |")
    # unknown (если есть)
    unk = by_cat.get("unknown", [])
    if unk:
        pct = (len(unk) / total) * 100 if total else 0
        lines.append(f"| ❓ Неизвестная причина | {len(unk)} | {pct:.0f}% |")
    lines.append(f"| **Итого** | **{total}** | **100%** |")
    lines.append("")

    # Топ мусорщиков
    if top_garbage:
        lines.append("## Топ-авторы мусора")
        lines.append("")
        for name, n in top_garbage:
            lines.append(f"- @{name} — {n}")
        lines.append("")

    # Детализация по категориям
    for cat_id, title, emoji, desc, _reasons in CATEGORIES:
        items = by_cat.get(cat_id, [])
        if not items:
            continue
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"_{desc}_")
        lines.append("")
        lines.append("| Дата | Время | Автор | Тип | Содержимое | Причина |")
        lines.append("|---|---|---|---|---|---|")
        # Сортируем: новые сверху
        items_sorted = sorted(items, key=lambda rr: rr[0].get("ts", ""), reverse=True)
        for rec, reason in items_sorted:
            date = rec.get("date", "?")
            time = rec.get("time", "??:??")
            handle = _members.resolve_handle(rec)
            kind = rec.get("kind", "other")
            kind_emoji = KIND_EMOJI.get(kind, "📝")
            content = _short_for_table(rec.get("content", ""), 80)
            lines.append(
                f"| {date} | {time} | {handle} | {kind_emoji} {kind} | {content} | `{reason}` |"
            )
        lines.append("")

    # unknown
    unk = by_cat.get("unknown", [])
    if unk:
        lines.append("## ❓ Неизвестная причина")
        lines.append("")
        lines.append("Reason'ы, которых нет в REASON_TO_CATEGORY. Стоит добавить в CATEGORIES.")
        lines.append("")
        lines.append("| Дата | Время | Автор | Тип | Содержимое | Reason |")
        lines.append("|---|---|---|---|---|---|")
        for rec, reason in sorted(unk, key=lambda rr: rr[0].get("ts", ""), reverse=True):
            date = rec.get("date", "?")
            time = rec.get("time", "??:??")
            handle = _members.resolve_handle(rec)
            kind = rec.get("kind", "other")
            kind_emoji = KIND_EMOJI.get(kind, "📝")
            content = _short_for_table(rec.get("content", ""), 80)
            lines.append(
                f"| {date} | {time} | {handle} | {kind_emoji} {kind} | {content} | `{reason}` |"
            )
        lines.append("")

    return "\n".join(lines)


def write_rejected_md(rejected: list[tuple[dict, str]], header_note: str = "") -> Path:
    """Записать ideas_rejected.md. Файл перезаписывается целиком (не append)."""
    body = render_rejected_md(rejected)
    head = "# 🗑 Отсеянные идеи\n\n"
    if header_note:
        head += f"> {header_note}\n\n"
    head += f"_Всего отсеяно: {len(rejected)}._\n\n---\n\n"
    REJECTED_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    REJECTED_MD_PATH.write_text(head + body, encoding="utf-8")
    return REJECTED_MD_PATH


# ---------- Telegram-формат (plain text) ----------

def build_rejected_summary(rejected: list[tuple[dict, str]]) -> str:
    """Сводка для /rejected (без аргумента).

    Категории + проценты + топ-авторы + подсказка про /rejected <категория>.
    """
    if not rejected:
        return "🗑 Отсеянных пока нет."

    by_cat = categorize(rejected)
    total = len(rejected)

    # Сводка по категориям
    lines: list[str] = [f"🗑 Отсеянные идеи — {total} шт.", ""]
    lines.append("📊 По категориям:")
    for cat_id, title, _emoji, _desc, _reasons in CATEGORIES:
        n = len(by_cat.get(cat_id, []))
        if n == 0:
            continue
        pct = (n / total) * 100 if total else 0
        lines.append(f"  {title}: {n} ({pct:.0f}%)")
    unk = by_cat.get("unknown", [])
    if unk:
        pct = (len(unk) / total) * 100 if total else 0
        lines.append(f"  ❓ Неизвестная причина: {len(unk)} ({pct:.0f}%)")
    lines.append("")

    # Топ-авторов
    by_author: dict[str, int] = {}
    for rec, _ in rejected:
        handle = _members.resolve_name(rec)
        by_author[handle] = by_author.get(handle, 0) + 1
    if by_author:
        lines.append("👤 Топ-авторы мусора:")
        for name, n in sorted(by_author.items(), key=lambda kv: -kv[1])[:5]:
            lines.append(f"  {name} — {n}")
        lines.append("")

    # Подсказка
    cat_ids = [c[0] for c in CATEGORIES if by_cat.get(c[0])]
    if cat_ids:
        lines.append("💡 Детали: /rejected <категория>")
        lines.append("   Доступные: " + ", ".join(cat_ids))

    return "\n".join(lines)


def build_rejected_list(
    rejected_in_cat: list[tuple[dict, str]], cat_id: str
) -> str:
    """Список отсеянных в указанной категории (для /rejected <cat_id>)."""
    title = next((t for c, t, *_ in CATEGORIES if c == cat_id), cat_id)
    if not rejected_in_cat:
        return f"{title}\n\n_в этой категории пусто_"

    lines: list[str] = [f"{title} — {len(rejected_in_cat)} шт.", ""]
    # Сортируем новые сверху
    items = sorted(rejected_in_cat, key=lambda rr: rr[0].get("ts", ""), reverse=True)
    for rec, reason in items:
        handle = _members.resolve_handle(rec)
        emoji = KIND_EMOJI.get(rec.get("kind", "other"), "📝")
        prefix = f"{rec.get('date', '?')} {rec.get('time', '??:??')} — {handle} {emoji}"
        if rec.get("kind") == "voice":
            dur = rec.get("duration") or 0
            prefix += f" (голос {dur}s)"
        body = _shorten(rec.get("content", ""), 160)
        lines.append(f"• {prefix}: «{body}»  _[{reason}]_")
    return "\n".join(lines)


def build_rejected_columns(rejected: list[tuple[dict, str]]) -> str:
    """Полный вид: все категории как секции, идеи под каждой.

    Используется в /rejected без аргументов. Категории с нулём пропускаются.
    """
    if not rejected:
        return "💡 Идеи для усовершенствования проекта\n\n_пока пусто — ни одного отсеянного._"

    by_cat = categorize(rejected)
    total = len(rejected)
    lines: list[str] = [
        f"💡 Идеи для усовершенствования проекта — {total} шт.",
        "_Отсеянные сообщения как сигналы: что в боте/проекте стоит улучшить._",
        "",
    ]

    for cat_id, title, _emoji, _desc, _reasons in CATEGORIES:
        items = by_cat.get(cat_id, [])
        if not items:
            continue
        n = len(items)
        lines.append(f"📌 {title} ({n})")
        # Идеи под категорией
        items_sorted = sorted(items, key=lambda rr: rr[0].get("ts", ""), reverse=True)
        for rec, reason in items_sorted:
            handle = _members.resolve_handle(rec)
            kind_emoji = KIND_EMOJI.get(rec.get("kind", "other"), "📝")
            time = rec.get("time", "??:??")
            date = rec.get("date", "?")
            content = (rec.get("content") or "").strip()
            # Компактный вид для колонки
            lines.append(f"  • {date} {time} — {handle} {kind_emoji}: «{content}»")
        lines.append("")

    # Unknown (если есть)
    unk = by_cat.get("unknown", [])
    if unk:
        lines.append(f"📌 ❓ Неизвестная причина ({len(unk)})")
        for rec, reason in sorted(unk, key=lambda rr: rr[0].get("ts", ""), reverse=True):
            handle = _members.resolve_handle(rec)
            kind_emoji = KIND_EMOJI.get(rec.get("kind", "other"), "📝")
            content = (rec.get("content") or "").strip()
            lines.append(f"  • {rec.get('date','?')} {rec.get('time','??:??')} — {handle} {kind_emoji}: «{content}»  [{reason}]")
        lines.append("")

    # Подсказка
    lines.append("💡 /rejected <категория> — только одна категория")
    cat_ids = [c[0] for c in CATEGORIES if by_cat.get(c[0])]
    if cat_ids:
        lines.append("   " + ", ".join(cat_ids))

    return "\n".join(lines)


# ---------- State ----------

def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"last_run_ts": None, "seen": {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"last_run_ts": None, "seen": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------- CLI ----------

def _now_iso() -> str:
    return datetime.now(MOSCOW_TZ).isoformat(timespec="seconds")


def run(since: str | None = None, dry_run: bool = False) -> dict:
    """Основная точка входа. Возвращает dict со статистикой.

    since:
      None — полная переклассификация (без dedup, детерминированный выход).
      ISO ts — инкрементальный режим (только новые, с dedup против ранее seen).
    """
    check_duplicates = since is not None
    state = load_state()
    records = load_records(since=since)
    ideas, rejected = classify(records, state, check_duplicates=check_duplicates)

    reasons = Counter(reason for _, reason in rejected)

    stats = {
        "scanned": len(records),
        "ideas": len(ideas),
        "rejected": len(rejected),
        "reasons": dict(reasons.most_common()),
    }

    if not dry_run:
        header_note = f"Обновлено: {datetime.now(MOSCOW_TZ).strftime('%Y-%m-%d %H:%M %Z')}"
        path_ideas = write_ideas_md(ideas, header_note=header_note)
        path_rejected = write_rejected_md(rejected, header_note=header_note)
        state["last_run_ts"] = _now_iso()
        save_state(state)
        stats["written_to"] = str(path_ideas)
        stats["rejected_written_to"] = str(path_rejected)
        # Категории для вывода
        by_cat = categorize(rejected)
        stats["categories"] = {
            cat_id: len(items) for cat_id, items in by_cat.items() if items
        }

    return stats


def main(argv: list[str] | None = None) -> int:
    # На Windows консоль по умолчанию cp1251 — не умеет в эмодзи.
    # Переключаем stdout на utf-8, если получится.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description="Idea intake: notes.jsonl → ideas.md")
    parser.add_argument("--new-only", action="store_true",
                        help="Только записи после последнего запуска")
    parser.add_argument("--dry-run", action="store_true",
                        help="Не писать файлы, только статистика")
    args = parser.parse_args(argv)

    state = load_state()
    since = state.get("last_run_ts") if args.new_only else None

    stats = run(since=since, dry_run=args.dry_run)

    print(f"📥 Записей: {stats['scanned']}")
    print(f"💡 Идей: {stats['ideas']}")
    print(f"🗑  Отсеяно: {stats['rejected']}")
    if stats.get("categories"):
        print("   По категориям:")
        for cat_id, n in stats["categories"].items():
            title = next((t for c, t, *_ in CATEGORIES if c == cat_id), cat_id)
            print(f"     • {title}: {n}")
    elif stats["reasons"]:
        print("   По причинам:")
        for reason, n in stats["reasons"].items():
            print(f"     • {reason}: {n}")

    if args.dry_run:
        print("\n[DRY-RUN] Файлы не записаны.")
    elif "written_to" in stats:
        rel = Path(stats["written_to"]).relative_to(WORKSPACE)
        print(f"\n✅ Идеи — {rel}")
        if "rejected_written_to" in stats:
            rel_r = Path(stats["rejected_written_to"]).relative_to(WORKSPACE)
            print(f"✅ Отсеянные — {rel_r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
