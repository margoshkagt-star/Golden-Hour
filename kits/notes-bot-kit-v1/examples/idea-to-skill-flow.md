# Пример: путь идеи → SKILL.md

Это реальный кейс из production: как идея «бот должен присылать мотивационные цитаты по утрам» прошла путь от Telegram-сообщения до готового SKILL.md.

## Исходное сообщение

**Кто:** Karim (beatusx, chat_id `1038917447`)
**Когда:** 2026-06-21 16:39
**Где:** Telegram, бот `@Goldenteam239bot`
**Текст:** `бот должен присылать мне мотивационные цитаты по утрам`

## Шаг 1 — Бот принял сообщение

`telegram_notes_bot.py → _handle_text_note`:

1. `_is_greeting(text)` → False («бот должен присылать...» не в GREETINGS)
2. `_is_short_message(text)` → False (8 слов > 3)
3. `idea_intake.split_bullet_list(text)` → `["бот должен присылать мне мотивационные цитаты по утрам"]`
4. `append_note(user, "text", item)` → запись в `memory/notes.jsonl` + `memory/inbox/2026-06-21.md`

**Ответ бота:** «Записано 📝»

## Шаг 2 — Forgeable-проверка

`_maybe_auto_skill_from_text`:

1. `auto_skill_from_ideas` → True (bot-config.json)
2. `is_owner(user)` → True
3. `last_record` — последняя запись этого user_id (только что добавленная)
4. `idea_intake.is_forgeable(last_record)`:
   - `content = "бот должен присылать мне мотивационные цитаты по утрам"` (62 символа)
   - `len(content) >= FORGEABLE_MIN_LEN (30)` → **True**

## Шаг 3 — Очередь

`_enqueue_forge(last_record, content)` пишет в `memory/forge_queue.jsonl`:

```json
{
  "queued_at": "2026-06-21T16:39:25+03:00",
  "source": "ts=2026-06-21T16:39:25 user_id=1038917447",
  "chat_id": 1038917447,
  "username": "beatusx",
  "content": "бот должен присылать мне мотивационные цитаты по утрам",
  "ts": "2026-06-21T16:39:25+03:00",
  "status": "pending",
  "result_summary": null,
  "processed_at": null
}
```

Бот **НЕ** уведомляет Karim'а об этом (тихо ставит в очередь).

## Шаг 4 — notes-keeper подхватывает

`notes-keeper` агент (📓) в основной сессии Karim'а получает задачу «обработай forge_queue»:

1. Парсит `forge_queue.jsonl`, находит pending
2. Формирует вызов к `forge-skill`:

```
sessions_send(
    agentId="forge-skill",
    message="idea: бот должен присылать мне мотивационные цитаты по утрам | source_idea_id: ts=2026-06-21T16:39:25 user_id=1038917447"
)
```

## Шаг 5 — forge-skill делает 5 шагов

```
1. Research (≤90 сек)
   - web_search "motivational quotes daily telegram bot"
   - top-3 источника: статьи на Habr, пример quotes API, golden-hour skill patterns

2. Design
   - slug: morning-quote
   - description: "Утренняя мотивационная цитата в 9:00 МСК. 20 цитат, ротация по дню недели или случайно. 🔆."
   - 7 секций по шаблону: Цель / Триггер / Логика / Вход-Выход / Примеры / Что НЕ делает / Зависимости
   - встроенный массив из 20 цитат

3. Tests
   - tests/test_smoke.py: frontmatter, no placeholders, sections present
   - + behavioral: morning_quote(datetime.date(2026, 6, 22)) → ожидаемая строка
   - pytest 20/20 ✓

4. Save
   workspace/Golden-Hour/skills/morning-quote/
     ├── SKILL.md         (8.6 KB)
     ├── proposal.json    (1.4 KB)
     └── tests/
         ├── __init__.py
         └── test_smoke.py (7.5 KB)

5. Report
   🔨 forge-skill: morning-quote
   📁 workspace/Golden-Hour/skills/morning-quote/
   🔬 Research: 3 источника
   🧪 Tests: passed (20 проверок)
   📝 Sources: ...
   ✅ Готово к коммиту через Cursor.
```

## Шаг 6 — notes-keeper обновляет очередь

```python
item["status"] = "done"
item["result_summary"] = "🔨 forge-skill: morning-quote"
item["processed_at"] = "2026-06-21T16:42:18+03:00"
# write back to forge_queue.jsonl
```

Плюс добавляет запись в `memory/skills-digest.md`:

```markdown
## 2026-06-21 16:42:18 — morning-quote
- source: ts=2026-06-21T16:39:25 user_id=1038917447
- author: beatusx
- result: ✅ done
- path: workspace/Golden-Hour/skills/morning-quote/SKILL.md
- tests: 20/20 passed
```

## Шаг 7 — Karim получает уведомление

Notes-keeper шлёт Karim'у в webchat:

```
✅ forge-skill готов: morning-quote

Бот: "бот должен присылать мне мотивационные цитаты по утрам"
↓
📁 workspace/Golden-Hour/skills/morning-quote/SKILL.md (8.6 KB)
🧪 20 pytest-проверок зелёные
📊 20 цитат встроены

Готово к коммиту через Cursor.
```

## Шаг 8 — Cursor коммитит (ручной шаг)

Karim открывает Cursor, видит новую папку `workspace/Golden-Hour/skills/morning-quote/`, делает code review, коммитит, пушит в golden-hour repo.

## Общее время

- Шаг 1-3 (бот): ~50 мс
- Шаг 4-6 (notes-keeper + forge-skill): 3-5 минут
- Шаг 7-8 (Karim): по его графику

**Полный цикл от сообщения до готового SKILL.md:** ≤ 5 минут автономно.

## Что увидит Karim в Telegram

Ничего. Бот НЕ шлёт уведомлений о forge-операциях в Telegram (только notes-keeper в webchat). Это by design — Telegram для пользователей, webchat для оператора.

## Какие файлы создались в этом кейсе

| Файл | Размер | Когда |
|---|---|---|
| `memory/notes.jsonl` | +1 строка | Шаг 1 |
| `memory/inbox/2026-06-21.md` | +3 строки | Шаг 1 |
| `memory/forge_queue.jsonl` | +1 строка | Шаг 3 |
| `workspace/Golden-Hour/skills/morning-quote/SKILL.md` | 8.6 KB | Шаг 5 |
| `workspace/Golden-Hour/skills/morning-quote/proposal.json` | 1.4 KB | Шаг 5 |
| `workspace/Golden-Hour/skills/morning-quote/tests/__init__.py` | 41 B | Шаг 5 |
| `workspace/Golden-Hour/skills/morning-quote/tests/test_smoke.py` | 7.5 KB | Шаг 5 |
| `memory/skills-digest.md` | +6 строк | Шаг 6 |
| `memory/forge_queue.jsonl` | обновлён (status=done) | Шаг 6 |
