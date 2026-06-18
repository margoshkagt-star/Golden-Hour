---
name: "goal-materials"
description: "Библиотека учебных материалов по целям пользователя (задачи/теория/ссылки): add/pick/list/status. Хранение в папке пользователя. Требует setup_status=complete."
---

# goal-materials

Библиотека материалов (задачи, теория, ссылки, файлы, заметки), привязанная к целям пользователя из его профиля. Принимает то, что прислал пользователь, и сам подбирает задачи/ссылки по теме.

**Хранение — в папке пользователя** `users/<user_key>/materials/`. Требует `setup_status: complete`.

## Когда использовать
- Пользователь прислал задачу/ссылку/формулу/файл и хочет сохранить к цели.
- Нужно выдать материал по цели («дай задачу по параметрам»).
- Посмотреть, что уже есть по цели/предмету.
- Отметить материал как разобранный / непонятый.

## Workflow

### 1. Определить цель
- Если пользователь указал явно («ЕГЭ математика», «олимпиада по физике») — берём её.
- Иначе читаем активные цели из `users/<user_key>/profile.md`:
  - `exam_subject` (+`exam_subject_variant`) → цель `exam_<subject>_<variant>`
  - `olympiad_subject` (+`grade`) → `olymp_<subject>_<grade>`
  - `study_topic` → `topic_<slug>`
- Одна цель — используем без вопроса; несколько — спрашиваем списком; нет — просим назвать.

### 2. Добавить материал (`add`)
- Типы: `problem`, `theory`, `link`, `file`, `note`.
- Теги: тема (`параметры`, `стереометрия`), источник (`fipi`, `foxford`), уровень (`easy/medium/hard`).
- Статус при создании: `new`.
- Путь: `users/<user_key>/materials/<goal_id>/<type>/YYYY-MM-DD_<slug>.md` + индекс `users/<user_key>/materials/index.json`.
- Frontmatter материала: `id, goal_id, type, tags, status, source, created_at, status_history`.
- Если пользователь прислал URL и просит «найди ещё по теме» — подобрать 2–3 ссылки через `web_search` (`source: web_search`), только при активной цели. Можно переиспользовать `material-cache`, чтобы не искать одно и то же дважды.

### 3. Посмотреть (`list`)
- По цели / по тегу / `--summary` (счётчики по статусам).

### 4. Выдать (`pick`)
- Случайный из `new` (свежее) или `working` (добить). Фильтры `--type/--tag/--status`. Возвращает содержимое + переводит в `working`.

### 5. Поиск (`search`)
- По тексту/тегу/типу/статусу (grep по markdown + индекс).

### 6. Статус (`status`)
Переходы: `new → working → understood`; `working → stuck → working/understood`; `understood → archived`. Каждое изменение — в `status_history`. Смена `understood`/`stuck` дополнительно отражается строкой в `users/<user_key>/progress.md`.

## Telegram-интерфейс (inline buttons)
- **`pick`:** `[✅ Разобрал] [❌ Не понял] [⏭ Пропустить]` → `mat:status:<id>:understood|stuck|archived`
- **`list`:** `[Открыть] [В работу] [🗑 В архив]` → `mat:show:<id>` / `mat:status:<id>:working|archived`
- **`add`:** `[Открыть] [Добавить ещё]` → `mat:show:<id>` / `mat:add:continue`

Callback приходит как сообщение с `callback_data`. Агент парсит `mat:<action>:<id>[:<value>]`, выполняет, обновляет файл + `index.json`, коротко подтверждает.

## Хранение
```
users/<user_key>/materials/
  index.json
  <goal_id>/
    problems/YYYY-MM-DD_<slug>.md
    theory/…  links/…  files/  notes/…
```
`index.json` обновляется при каждом `add`/`status`. Переиндексация — «пересобери индекс материалов».

## Конвенции
- ID материала: `m_<8>`; имя файла `YYYY-MM-DD_<slug>.md` (slug транслитом, kebab-case).
- Теги — lower-case, kebab-case. Статусы — фикс. набор: `new/working/stuck/understood/archived`.

## Что НЕ делает
- ❌ Не работает при `setup_status ≠ complete`.
- ❌ Не пишет в чужую папку и не смешивает цели разных пользователей.
- ❌ Не ищет в web без активной цели.

## Связь с другими скиллами
- `material-cache` — общий кеш найденного, чтобы не искать повторно.
- `focus-timer` — может писать минуты на конкретный материал (опц.).
- `daily-plan` / `study-plan` — ссылаются на материалы в задачах.

## Где живёт реальное исполнение
**`SOUL.md` → секция «Рабочий режим»** — то, что агент реально выполняет. Этот скилл — дизайн-документ.
