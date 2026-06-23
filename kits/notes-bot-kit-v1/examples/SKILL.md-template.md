# Шаблон SKILL.md, который forge-skill генерирует

> Реальный пример из production: `morning-quote` (2026-06-22). Сгенерирован `forge-skill` агентом, сохранён в `workspace/Golden-Hour/skills/morning-quote/SKILL.md`.

```markdown
---
name: morning-quote
description: "Утренняя мотивационная цитата в 9:00 МСК. 20 цитат, ротация по дню недели или случайно. 🔆."
---

# morning-quote

Утренняя мотивационная цитата в ежедневный чек-ин пользователя. Цитаты — из встроенного локального массива (20 шт.), никаких внешних API.

## Цель

Сделать утренний чек-ин golden-hour теплее и осмысленнее: пользователь каждое утро в 9:00 по Москве получает одну короткую мотивационную цитату с подписью «🔆 Утренняя цитата».

## Триггер

- **Расписание:** ежедневно в 09:00 Europe/Moscow, в связке со скиллом `daily-plan` (утренний чек-ин).
- **Точка вызова:** golden-hour-bot вызывает функцию `morning_quote(now=None, randomize=False)` и шлёт результат пользователю в Telegram.
- **Условие:** skill активен в `users/<user_key>/profile.md` (по умолчанию — `morning_quote: enabled`).

## Логика

1. Получить текущую локальную дату (Москва).
2. Выбрать индекс цитаты:
   - **По умолчанию:** `now.weekday() % len(QUOTES)` — один и тот же день недели = одна и та же цитата всю неделю.
   - **Если `randomize=True`:** индекс через `random.Random(now.toordinal())` — детерминированная случайность (одна цитата на весь день, повторно в этот день не выпадет).
3. Вернуть отформатированную строку:

\`\`\`
🔆 Утренняя цитата

«<текст>»

— <автор>
\`\`\`

### Массив цитат (20 шт.)

\`\`\`python
QUOTES = [
    ("Каждый день — это новая возможность стать лучше.", "Стивен Кови"),
    ("Будущее принадлежит тем, кто верит в красоту своей мечты.", "Элеонора Рузвельт"),
    ("Не ошибается тот, кто ничего не делает.", "Теодор Рузвельт"),
    # ... 17 more
]
\`\`\`

### Реализация

\`\`\`python
import datetime
import random
from typing import Optional

def morning_quote(
    now: Optional[datetime.date] = None,
    randomize: bool = False,
) -> str:
    """Return one formatted motivational quote for the morning check-in."""
    if now is None:
        now = datetime.date.today()
    if randomize:
        idx = random.Random(now.toordinal()).randrange(len(QUOTES))
    else:
        idx = now.weekday() % len(QUOTES)
    text, author = QUOTES[idx]
    return f"🔆 Утренняя цитата\n\n«{text}»\n\n— {author}"
\`\`\`

## Вход → Выход

| Вход | Тип | Обязательно | Описание |
|---|---|---|---|
| `now` | `datetime.date` | нет | Локальная дата. По умолчанию `today()`. |
| `randomize` | `bool` | нет | Режим ротации. По умолчанию `False` (по дню недели). |

**Выход:** строка вида

\`\`\`
🔆 Утренняя цитата

«<текст>»

— <автор>
\`\`\`

Длина ≤ 250 символов. Всегда ровно 1 цитата.

## Примеры

\`\`\`python
>>> morning_quote(datetime.date(2026, 6, 22))   # понедельник
'🔆 Утренняя цитата\\n\\n«Каждый день — это новая возможность стать лучше.»\\n\\n— Стивен Кови'

>>> morning_quote(datetime.date(2026, 6, 23), randomize=True)
'🔆 Утренняя цитата\\n\\n«Дисциплина — это мост между целями и достижениями.»\\n\\n— Джим Рон'
\`\`\`

**Пользовательский вид в Telegram:**

> 🔆 Утренняя цитата
>
> «Успех — это сумма маленьких усилий, повторяемых день за днём.»
>
> — Роберт Кольер

## Что НЕ делает

- Не звонит в Telegram / не отправляет сообщения напрямую — это задача golden-hour-bot.
- Не использует внешние API, сеть, файлы и переменные окружения — всё в локальном массиве.
- Не генерирует новые цитаты и не подтягивает их из интернета.
- Не меняет `users/<user_key>/profile.md` — это делает skill `user-profile` при opt-in/opt-out.

## Зависимости

| Зависимость | Назначение |
|---|---|
| Python 3.10+ (stdlib) | `datetime`, `random`, `typing`. Без сторонних пакетов. |
| `daily-plan` | Триггер расписания 09:00 МСК. |
| `user-profile` | Флаг `morning_quote: enabled/disabled` в профиле пользователя. |
| `golden-hour-bot` (main) | Точка вызова: `morning_quote()` → Telegram. |

## Связанные скиллы

- `daily-plan` — утренний чек-ин.
- `daily-study-checkin`, `goal-checkin-notifier`, `mood-checkin` — соседи по утреннему блоку.
- `user-profile` — хранит флаг включения.
```

## Что forge-skill ОБЯЗАН обеспечить

1. ✅ Frontmatter с `name` (slug) и `description` (≤160 байт)
2. ✅ Все 7 секций: Цель, Триггер, Логика, Вход → Выход, Примеры, Что НЕ делает, Зависимости
3. ✅ Никаких `...`, «дописать», TODO в теле после frontmatter
4. ✅ Минимум 1 пример (doctest или пользовательский)
5. ✅ Реализация на Python или чёткая спецификация входа/выхода для других языков
6. ✅ pytest в `tests/test_smoke.py` — зелёный

## Что forge-skill НЕ делает

1. ❌ Не пишет в `workspaces/golden-hour/skills/` (только в `workspace/Golden-Hour/skills/`)
2. ❌ Не пушит в GitHub
3. ❌ Не использует реальные API-ключи в тестах
4. ❌ Не запрашивает внешние сервисы (только в Research шаге)

## Структура папки

```
workspace/Golden-Hour/skills/<slug>/
├── SKILL.md
├── proposal.json       ← метаданные (slug, source_idea_id, tags, status, author)
├── assets/             ← (опционально)
├── examples/           ← (опционально)
└── tests/
    ├── __init__.py
    └── test_smoke.py   ← pytest
```

## proposal.json (пример)

```json
{
  "slug": "morning-quote",
  "title": "Утренняя мотивационная цитата",
  "summary": "Одна мотивационная цитата в утренний чек-ин в 9:00 МСК. Локальный массив 20 цитат, ротация по дню недели или случайно. Подпись 🔆 Утренняя цитата.",
  "author": "beatusx",
  "user_key": "beatusx",
  "source_idea_id": "ts=1782093544 user_id=1038917447",
  "source_idea_date": "2026-06-21",
  "created_at": "2026-06-22",
  "tags": ["morning", "motivation", "quote", "checkin", "daily"],
  "triggers": {
    "schedule": "0 9 * * *",
    "tz": "Europe/Moscow",
    "via_skill": "daily-plan"
  },
  "input": {
    "now": "datetime.date (optional, default today)",
    "randomize": "bool (optional, default false)"
  },
  "output": {
    "type": "str",
    "format": "🔆 Утренняя цитата\\n\\n«<text>»\\n\\n— <author>",
    "max_length": 250
  },
  "related_skills": ["daily-plan", "daily-study-checkin", "goal-checkin-notifier", "mood-checkin", "user-profile"],
  "depends_on": ["daily-plan", "user-profile"],
  "depends_on_external_api": false,
  "tests_passed": true,
  "status": "ready",
  "notes": "Не вызывает Telegram — это задача golden-hour. Массив 20 цитат вшит в SKILL.md."
}
```

## Как /info в боте использует этот SKILL.md

`telegram_notes_bot.py → _load_realized_ideas_index()`:

1. Парсит `<!-- source: ts=... user_id=... -->` из всех SKILL.md
2. Индексирует `{(ts, user_id): {slug, location}}`
3. В `/info` помечает соответствующие идеи как `✅ <slug>`

(В текущей версии morning-quote SKILL.md нет такого маркера — нужно добавить руками или в v2 forge-skill будет добавлять автоматически.)
