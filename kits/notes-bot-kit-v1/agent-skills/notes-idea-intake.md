---
name: notes-idea-intake
description: "Классификатор идей Notes-Bot: дедуп, стоп-слова, is_forgeable(), split на под-идеи. JSONL + markdown. 🧮."
---

# notes-idea-intake

Как Notes-Bot Kit классифицирует сообщения: дедупликация, стоп-слова, фильтрация мусора, разбиение на под-идеи, определение forgeable-идей.

## Цель

Дать агенту в OpenClaw полное понимание логики intake, чтобы:
- Объяснить, почему конкретная запись попала в `ideas.md` или в `ideas_rejected.md`
- Дебажить странные категории rejected
- Помочь пользователю переформулировать идею, чтобы она прошла фильтр
- Расширить intake (добавить новые стоп-слова / категории) с пониманием последствий

## Триггер

- Вопросы про `/classify`, `ideas.md`, `ideas_rejected.md`
- «Почему мою идею отсеяли?»
- «Как сделать чтобы идея попала в forge?»
- Дебаг: «X forgeable, а Y нет»
- Задача модификации intake (добавить категорию / изменить порог)

## Логика

### 8 правил отсева (в порядке применения)

Запись ОТКЛОНЯЕТСЯ (идёт в `ideas_rejected.md`), если ЛЮБОЕ из:

1. **Empty content** — `content == None or ""`
2. **Команда** — `kind == "other"` И content начинается с `/`
3. **Медиа без подписи** — `kind in {voice, photo}` И `len(content) < 10`
4. **Слишком короткий** — `len(content.strip()) < MIN_CONTENT_LEN` (=3)
5. **Стоп-слово** — content в `STOP_WORDS` (привет, ок, qq, ... 26 штук)
6. **Garbage pattern** — content подходит под один из regex:
   - 1-3 буквы без цифр (`ааа`, `ппп`)
   - Только спецсимволы
   - Один символ повторён 3+ раз (`111`, `---`)
   - Один символ повторён 5+ раз (`aaaaa`)
7. **Дубль** — у того же user_id был такой же content в течение `DEDUP_WINDOW_MIN` (=30 мин)
8. **Ручная отметка** — `is_idea == false` (выставлена вручную в notes.jsonl)

### is_forgeable() — отдельная проверка

Идея FORGEABLE (пойдёт в `forge_queue.jsonl`), если:

```python
def is_forgeable(record, min_len=FORGEABLE_MIN_LEN):  # min_len=30
    content = (record.get("content") or "").strip()
    return len(content) >= min_len
```

**Важно:** `is_forgeable` НЕ зависит от `is_idea` / rejected — может быть как прошедшая intake, так и rejected. Но бот вызывает `_maybe_auto_skill_from_text` ТОЛЬКО для owner, и ТОЛЬКО если текст не greeting и не короткий (Bug #1 guards).

### split_idea() — разбиение на под-идеи

Сплиттер ищет:

1. **Маркированные списки:**
   ```
   * идея раз
   - идея два
   • идея три
   ```

2. **Разделители по словам:** ` и `, ` также `, ` а ещё `, ` + `, `. ` (перед заглавной)

3. **Разделители по предложениям:** `.!?` + пробел + заглавная буква

Возвращает список строк. Если 1 — идея атомарная.

**Пример:**
```
split_idea("Бот должен понимать настроение, присылать мемы и помогать с CI")
→ ["Бот должен понимать настроение", "присылать мемы", "помогать с CI"]
```

### Категоризация rejected

`_categorize_rejected(reason)` → возвращает category_id:

| reason (причина отсева) | category_id |
|---|---|
| Начинается с `/` | `command` |
| В STOP_WORDS или GARBAGE_PATTERNS | `test_input` |
| kind in {voice,photo} + len < 10 | `media_no_caption` |
| len(content) < MIN_CONTENT_LEN | `empty` |
| Дубль в окне DEDUP_WINDOW_MIN | `duplicate` |
| is_idea == false вручную | `manual` |
| Прочее | `unknown` |

### Шаги пайплайна

```
classify(records, state, check_duplicates=True):
    1. Для каждой записи проверить 8 правил
    2. Если прошло — в kept, иначе в rejected (с reason)
    3. Вернуть (kept, rejected) И shallow copy с полем forgeable на kept
```

### Состояние

`memory/ideas_state.json` хранит:
- `last_run_ts` — для `/classify new-only`
- `seen` — список (user_id, content) для дедупа (на самом деле дедуп по окну времени, не по seen)

### Артефакты

- `memory/ideas.md` — отфильтрованные хорошие идеи, сгруппированные по дате
- `memory/ideas_rejected.md` — отсеянные, сгруппированные по category_id

## Вход → Выход

| Вход | Действие | Выход |
|---|---|---|
| «Почему X rejected?» | Проверить 8 правил для X | Конкретная причина |
| «Сделать Y forgeable?» | Проверить `len(content) >= 30` | Да/нет + как увеличить |
| «Сколько rejected по причинам?» | Парсинг `ideas_rejected.md` | Сводка |
| «Добавить новое стоп-слово» | Поправить `STOP_WORDS` в `idea_intake.py` + рестарт бота | Новое стоп-слово |
| «Разбить идею на под-идеи» | `split_idea(text)` | Список строк |
| «Прогнать intake заново» | `python idea_intake.py` или `/classify` | Обновлённые .md |

## Что НЕ делает

- Не модифицирует `notes.jsonl` (только читает)
- Не триггерит forge (это к `notes-forge-pipeline`)
- Не отправляет ничего в Telegram
- Не делает ML-классификацию (только детерминированные правила)

## Зависимости

- Python 3.10+ (`re`, `json`, `pathlib`, `datetime`)
- `members.py` — для resolve handle в markdown-выводе
- `memory/notes.jsonl` — источник записей
- `memory/ideas_state.json` — состояние для `new-only`
- `memory/members.json` — реестр handle'ов

## Связанные скиллы

- `notes-bot-architecture` — где intake в общей картине
- `notes-bot-commands` — `/classify`, `/rejected`
- `notes-forge-pipeline` — куда идут forgeable
- `notes-voice-transcribe` — голосовые тоже идут через intake
