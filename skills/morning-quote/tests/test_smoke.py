"""Smoke tests for the morning-quote skill.

Runs without network. Validates SKILL.md structure, the embedded QUOTES array,
the `morning_quote()` function semantics, and proposal.json metadata.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_MD = SKILL_DIR / "SKILL.md"
PROPOSAL_JSON = SKILL_DIR / "proposal.json"

FORBIDDEN_TOKENS = ("...", "дописать", "TODO", "FIXME")

REQUIRED_SECTIONS = (
    "## Цель",
    "## Триггер",
    "## Логика",
    "## Вход",
    "## Примеры",
    "## Что НЕ делает",
    "## Зависимости",
)

PY_BLOCK_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_text() -> str:
    assert SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}"
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(skill_text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", skill_text, re.DOTALL)
    assert m, "SKILL.md must start with YAML frontmatter delimited by ---"
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"')
    assert "name" in fm, "frontmatter must contain 'name'"
    assert "description" in fm, "frontmatter must contain 'description'"
    return fm


@pytest.fixture(scope="module")
def ns(skill_text: str) -> dict:
    """Execute BOTH python code blocks in a shared namespace."""
    blocks = PY_BLOCK_RE.findall(skill_text)
    assert len(blocks) >= 2, (
        "SKILL.md must contain two ```python blocks (QUOTES + morning_quote)"
    )
    namespace: dict = {"datetime": _dt}
    exec(blocks[0], namespace)  # noqa: S102 — defines QUOTES
    exec(blocks[1], namespace)  # noqa: S102 — uses QUOTES
    assert "QUOTES" in namespace, "first python block must define QUOTES"
    assert "morning_quote" in namespace, (
        "second python block must define morning_quote()"
    )
    return namespace


@pytest.fixture(scope="module")
def quote_fn(ns: dict):
    return ns["morning_quote"]


@pytest.fixture(scope="module")
def proposal() -> dict:
    assert PROPOSAL_JSON.exists(), f"proposal.json not found at {PROPOSAL_JSON}"
    return json.loads(PROPOSAL_JSON.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------

def test_frontmatter_name_matches_slug(frontmatter: dict) -> None:
    assert frontmatter["name"] == "morning-quote"


def test_frontmatter_description_length(frontmatter: dict) -> None:
    desc = frontmatter["description"]
    assert 0 < len(desc.encode("utf-8")) <= 160, (
        f"description must be 1..160 bytes (got {len(desc.encode('utf-8'))})"
    )


# ---------------------------------------------------------------------------
# Body hygiene
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("token", FORBIDDEN_TOKENS)
def test_no_placeholder_tokens(skill_text: str, token: str) -> None:
    assert token not in skill_text, f"forbidden token '{token}' found in SKILL.md"


def test_required_sections_present(skill_text: str) -> None:
    missing = [s for s in REQUIRED_SECTIONS if s not in skill_text]
    assert not missing, f"missing sections: {missing}"


def test_signature_in_examples(skill_text: str) -> None:
    assert "🔆 Утренняя цитата" in skill_text, (
        "signature '🔆 Утренняя цитата' must appear in SKILL.md"
    )


def test_timezone_moscow(skill_text: str) -> None:
    assert "Europe/Moscow" in skill_text or "Москв" in skill_text


# ---------------------------------------------------------------------------
# QUOTES array
# ---------------------------------------------------------------------------

def test_quotes_count_in_range(ns: dict) -> None:
    n = len(ns["QUOTES"])
    assert 15 <= n <= 20, f"QUOTES must have 15..20 items, got {n}"


def test_quotes_shape_and_nonempty(ns: dict) -> None:
    for i, item in enumerate(ns["QUOTES"]):
        assert isinstance(item, tuple) and len(item) == 2, (
            f"QUOTES[{i}] must be a (text, author) tuple, got {item!r}"
        )
        text, author = item
        assert isinstance(text, str) and text.strip(), f"QUOTES[{i}].text empty"
        assert isinstance(author, str) and author.strip(), f"QUOTES[{i}].author empty"


def test_quotes_unique(ns: dict) -> None:
    texts = [t for t, _ in ns["QUOTES"]]
    assert len(set(texts)) == len(texts), "QUOTES must not contain duplicates"


# ---------------------------------------------------------------------------
# morning_quote() function
# ---------------------------------------------------------------------------

def test_morning_quote_signature_and_format(quote_fn) -> None:
    out = quote_fn(_dt.date(2026, 6, 22))
    assert isinstance(out, str)
    assert out.startswith("🔆 Утренняя цитата"), out
    assert len(out) <= 250, f"output too long ({len(out)} chars): {out!r}"
    assert "«" in out and "»" in out, out
    assert "— " in out, out


def test_morning_quote_weekday_rotation_is_stable(quote_fn) -> None:
    a = quote_fn(_dt.date(2026, 6, 22))  # Monday
    b = quote_fn(_dt.date(2026, 6, 29))  # Next Monday
    assert a == b, "same weekday should yield the same quote"


def test_morning_quote_weekday_rotation_varies(quote_fn) -> None:
    outputs = {quote_fn(_dt.date(2026, 6, 22 + i)) for i in range(7)}
    assert len(outputs) >= 2, "rotation by weekday should yield >1 unique quote"


def test_morning_quote_randomize_is_deterministic(quote_fn) -> None:
    d = _dt.date(2026, 6, 22)
    a = quote_fn(d, randomize=True)
    b = quote_fn(d, randomize=True)
    assert a == b, "randomize=True must be deterministic for the same date"


def test_morning_quote_randomize_different_dates(quote_fn) -> None:
    a = quote_fn(_dt.date(2026, 6, 22), randomize=True)
    b = quote_fn(_dt.date(2026, 6, 23), randomize=True)
    assert a != b, "different dates should usually yield different random quotes"


def test_morning_quote_default_uses_today(quote_fn, monkeypatch) -> None:
    class FakeDate(_dt.date):
        @classmethod
        def today(cls) -> "FakeDate":
            return cls(2026, 1, 5)  # Monday

    monkeypatch.setattr(_dt, "date", FakeDate)
    out = quote_fn()
    assert out.startswith("🔆 Утренняя цитата")


# ---------------------------------------------------------------------------
# proposal.json
# ---------------------------------------------------------------------------

def test_proposal_has_required_fields(proposal: dict) -> None:
    for key in ("slug", "source_idea_id", "tags", "output"):
        assert key in proposal, f"proposal.json missing key: {key}"


def test_proposal_source_idea_id_matches(proposal: dict) -> None:
    assert proposal["source_idea_id"] == "ts=1782093544 user_id=1038917447"
