"""Smoke-тест SKILL.md: frontmatter, секции, без плейсхолдеров.

Генерируется skill-forge. Использует unittest (stdlib), чтобы не тянуть pytest.
Синхронизировано с SOUL.md → раздел «Протокол → Tests».
"""
import re
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"

# pyyaml может отсутствовать — пробуем импортнуть, иначе парсим вручную
try:
    import yaml
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


def _parse_frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    if HAVE_YAML:
        try:
            return yaml.safe_load(block) or {}
        except Exception:
            return {}
    out = {}
    for line in block.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _body(text: str) -> str:
    parts = text.split("---", 2)
    return parts[2] if len(parts) >= 3 else text


class SkillSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert SKILL_MD.exists(), f"SKILL.md не найден: {SKILL_MD}"
        cls.text = SKILL_MD.read_text(encoding="utf-8")
        cls.fm = _parse_frontmatter(cls.text)
        cls.body = _body(cls.text)

    def test_frontmatter_has_name(self):
        self.assertIn("name", self.fm, "frontmatter не содержит 'name'")
        self.assertIsInstance(self.fm["name"], str)
        self.assertGreater(len(self.fm["name"]), 0)

    def test_frontmatter_has_description(self):
        self.assertIn("description", self.fm, "frontmatter не содержит 'description'")
        self.assertIsInstance(self.fm["description"], str)
        desc_bytes = len(self.fm["description"].encode("utf-8"))
        self.assertLessEqual(
            desc_bytes, 200,
            f"description слишком длинный ({desc_bytes} байт, лимит 200)",
        )

    def test_no_placeholders(self):
        """Плейсхолдеры (`...`, `дописать`, `TODO` и т.п.) запрещены в prose,
        но НЕ внутри блоков кода (```...```) — там `...` это синтаксис markdown.
        """
        # Удаляем все блоки кода (``` ... ```) перед проверкой.
        text_no_code = re.sub(r"```.*?```", "", self.body, flags=re.DOTALL)
        # Также инлайн-код: `...`
        text_no_code = re.sub(r"`[^`]+`", "", text_no_code)
        forbidden = ["...", "дописать", "TODO", "TBD", "FIXME", "XXX"]
        for token in forbidden:
            self.assertNotIn(
                token, text_no_code,
                f"найден плейсхолдер '{token}' в prose SKILL.md",
            )

    def test_required_sections(self):
        for section in ["## Цель", "## Триггер", "## Логика", "## Что НЕ делает"]:
            self.assertIn(section, self.body, f"нет секции '{section}'")

    def test_logika_has_steps(self):
        m = re.search(r"## Логика\s*\n(.*?)(?=\n## |\Z)", self.body, re.DOTALL)
        self.assertIsNotNone(m, "нет секции ## Логика")
        logic = m.group(1)
        has_step = bool(re.search(r"(^|\n)\s*\d+[.)]\s", logic)) or "### " in logic
        self.assertTrue(has_step, "секция Логика не содержит нумерованных шагов")

    def test_what_not_doing(self):
        m = re.search(
            r"## Что НЕ делает\s*\n(.*?)(?=\n## |\Z)", self.body, re.DOTALL,
        )
        self.assertIsNotNone(m, "нет секции ## Что НЕ делает")
        block = m.group(1).strip()
        self.assertGreater(
            len(block), 10,
            "## Что НЕ делает пустая или слишком короткая",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
