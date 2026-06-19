---
name: "material-cache"
description: "Кеш сгенерированных/найденных материалов в knowledge/. Один раз research → файл с версией. Повторный запрос = ссылка, не новый search."
author: pending-clarification
status_source: agent-generated-2026-06-18 (per karim's request)
---

# Material Cache — material-cache

**Use when:** юзер просит «дай материал по X», «найди статью по Y», «покажи разбор задачи Z» — и есть риск, что через неделю он попросит то же самое снова.

**Don't use when:**
- Запрос разовый («как называется формула...») и не пойдёт в plan
- Юзер явно просит «свежее» (новости, текущая ситуация на рынке)
- Материал — это просто цитата/факт, не требующий файла

## Назначение

Сейчас каждый «дай материал» = новый `web_search` + `web_fetch` + генерация summary. Это:
1. **Дорого** (время и токены)
2. **Нестабильно** (новый search может дать другой результат)
3. **Теряет контекст** (где мы это уже нашли?)

**Решение:** один раз сгенерированный материал кладётся в `knowledge/<subject>/<slug>.md` с версией. Повторный запрос → поиск по `knowledge/`, нашли — отдаём ссылку. Не нашли — идём в web.

## Структура хранения

```
knowledge/
  <subject>/                  # "physics", "math", "informatics", "english"
    <slug>.md                 # "coulomb-law", "combinatorics-basics"
    _index.md                 # список всех материалов в этой папке
    <slug>.md.meta.yaml       # метаданные (опционально)
```

Имя `<slug>` — kebab-case, 2–4 слова, описывает суть (не «task-3-solution», а «integrals-by-parts»).

## Шаблон файла материала

```markdown
---
type: material
subject: physics
topic: электродинамика
subtopic: закон Кулона
created: 2026-06-18
updated: 2026-06-18
version: 1
source: web_search+web_fetch
sources:
  - url: "https://example.com/coulomb"
    title: "Закон Кулона — учебник"
    accessed: 2026-06-18
quality: medium              # low | medium | high — оценка источника
tags: [электродинамика, олимпиада, физика]
---

# Закон Кулона

**TL;DR:** Сила взаимодействия двух точечных зарядов F = k·q₁·q₂/r². k = 1/(4πε₀) ≈ 9·10⁹ Н·м²/Кл².

## Суть
- ...

## Формулы
- ...

## Разбор типовой задачи
[пример с решением]

## Где встречается
- [олимпиадные задачи, разборы]
- [учебник Мякишев, §X]

## Что не покрыто
- [если есть пробелы — отметить, чтобы не искать повторно]
```

## Алгоритм

### 1. Поиск в кеше
При запросе материала:
1. Определить `subject` (математика, физика, …) и `topic` (конкретная тема).
2. Прочитать `knowledge/<subject>/_index.md` — список slug'ов.
3. Найти совпадение по `topic` / `subtopic` / `tags`.
4. **Совпадение → отдать ссылку** на файл + краткое summary (1–2 строки). Не пересказывать.

### 2. Если в кеше нет — research

**Сначала оцени сложность** (≤ 5 сек):

| Условие | Стратегия |
|---|---|
| Простой факт (1–2 источника, < 10 сек) | **Main делает сам** (синхронно) |
| Сложный research (3+ источников, fetch+summary, > 20 сек) | **Делегировать субагенту** (`sessions_spawn`) — если сконфигурирован. Иначе main с пометкой. |
| Тяжёлая задача (10+ источников, анализ, генерация) | **Делегировать субагенту** + `sessions_yield` (main не ждёт) — если сконфигурирован. Иначе main + явное предупреждение пользователю. |

**Проверка конфигурации субагента:** перед попыткой `sessions_spawn` проверить, что `research-assistant` сконфигурирован в `openclaw.json` (это **необязательная** зависимость). Если нет — main делает research сам с пометкой.

**Простой research (main делает сам):**
1. **`web_search` по теме (2–3 запроса для покрытия)** — если работает. Если `web_search` сломан (SearXNG не настроен, нет ключа провайдера) — **сразу переход к шагу 2'** (fallback на `web_fetch` к known-good URLs).
2. `web_fetch` топ-2 источника.
3. Сгенерировать структурированный summary по шаблону.
4. Сохранить в `knowledge/<subject>/<slug>.md` с frontmatter.
5. Обновить `knowledge/<subject>/_index.md`.

**2'. Fallback при сломанном `web_search`:**

Если `web_search` возвращает ошибку или провайдер не сконфигурирован:
1. Использовать **known-good URLs** для темы (официальные docs: developer.mozilla.org, docs.python.org, ru.wikipedia.org, fipi.ru, и т.п. — для специфических тем свой список).
2. `web_fetch` напрямую к этим URLs (не ищем через search, сразу идём в источники).
3. Сгенерировать summary.
4. В frontmatter: `source: web_fetch-only (web_search unavailable)`, `quality: medium`, `note: "web_search fallback to direct fetch"`.
5. Сообщить пользователю: «`web_search` недоступен (SearXNG не настроен). Использовал прямой fetch к [list URLs]. Качество: medium.»

**Известные провайдеры для OpenClaw по умолчанию:**
- Если установлен SearXNG self-hosted → `web_search` работает
- Иначе — fallback на `web_fetch` к known-good URLs
- Списки known-good URLs по темам — собирать в `knowledge/_search-fallback/<subject>.md` (отдельный кеш списков)

**Сложный research через субагента (асинхронно):**

**Предусловие:** `agentId: "research-assistant"` сконфигурирован в `openclaw.json`. **Если не сконфигурирован** — main делает research сам с пометкой (см. выше «Простой research» + `quality: medium`, `note: "research-assistant not configured"`).

```javascript
// main: оценка сложности + проверка конфигурации
const isHeavy = (
  estimatedSources > 3 ||
  topic.includes("разбор") ||
  estimatedTime > 20000  // ms
);

// Проверить, сконфигурирован ли research-assistant (main знает свою конфигурацию)
const hasResearcher = /* main проверяет свой agentId allowlist или логирует "not configured" */;

if (isHeavy && hasResearcher) {
  // Делегировать субагенту researcher
  sessions_spawn({
    agentId: "research-assistant",
    model: "minimax/MiniMax-M3",            // OpenRouter недоступен
    cwd: "C:\\Users\\Tikho\\.openclaw\\workspace",  // пишет в общий knowledge/
    task: `Найди 3–5 источников по теме "${topic}" в области ${subject}.
Проведи факт-чек:
- Дата публикации < 2 лет (иначе пометь [требует проверки])
- Подтверждение из 2+ независимых источников (иначе пометь [единичный источник])
- Для олимпиадного материала — официальный сайт (olimpiada.ru, ФИПИ, оргкомитет)

Сгенерируй структурированный summary по шаблону:
- TL;DR (1–2 строки)
- Суть
- Формулы/тезисы
- Разбор типовой задачи (если есть)
- Где встречается
- Что не покрыто

Сохрани в /home/openclaw/.openclaw/workspace/knowledge/<subject>/<slug>.md с frontmatter:
- type: material
- subject: ${subject}
- topic: ${topic}
- created: ${today}
- version: 1
- source: web_search+web_fetch
- sources: [...]
- quality: medium
- tags: [...]

Верни в финальный ответ:
- Краткий TL;DR (1–2 предложения)
- 3 главных тезиса
- Путь к сохранённому файлу
`,
    context: "isolated",
    model: "minimax/MiniMax-M3"  // OpenRouter недоступен, minimax — единственный вариант
  });
  // main не ждёт — продолжает другие задачи
  sessions_yield();
  // через 30–60 сек: результат придёт в main
} else {
  if (isHeavy && !hasResearcher) {
    // Fallback: сложный research, но субагента нет
    // main делает сам, но явно предупреждает пользователя
    console.log("[material-cache] research-assistant not configured — main handles research directly with quality: medium");
  }
  // Простой research — main делает сам
  // ... (шаги выше, включая fallback на web_fetch при сломанном web_search)
}
```

**Изоляция при делегировании:**
- Researcher работает в своём workspace (`/data/workspace` внутри Docker)
- Не имеет доступа к `~/.openclaw/workspace` main
- Не видит USER.md, MEMORY.md, твои файлы
- Результат возвращает в main через announce (push, не poll)

**Что main делает после анонса researcher'а:**
1. Проверить, что файл сохранён в `knowledge/<subject>/<slug>.md` (через bind mount)
2. Обновить `_index.md` в main workspace
3. Выдать результат пользователю

**Преимущества субагента:**
- ✅ Main не блокируется на 30–60 сек research
- ✅ Researcher использует ту же модель `minimax/MiniMax-M3` (OpenRouter недоступен)
- ✅ Изоляция: ошибка researcher'а не сломает main
- ✅ Параллелизм: можно спавнить несколько researcher'ов одновременно

**Анти-паттерны:**
- ❌ Спавнить researcher для простого факта (overhead > benefit)
- ❌ Ждать результат poll'ом (`sessions_list` в цикле) — есть push через announce
- ❌ Передавать в `task` конфиденциальный контекст (Sayu не указывать)
- ❌ Использовать `context: "fork"` — researcher изолирован, fork даст ему main transcript

### 3. Если материал старый / устарел
В файле есть `updated` и `version`. Если запрос пришёл > 30 дней после `updated`:
- Показать ссылку **+** пометку «обновлено N дней назад, обновить?».
- Если юзер хочет — re-research, version+1, обновить `updated`.

### 4. Кеш «промахов»
Если `web_search` не дал хороших результатов — тоже записать в `knowledge/<subject>/_not-found.md`:
```markdown
# Не нашли: <тема>
- attempts: 2
- last_try: 2026-06-18
- почему: [причина]
- альтернативы: [смежные темы, которые могут подойти]
```
Чтобы не повторять те же поиски.

## Управление кешем

### Ротация
- Материалы, на которые не ссылались > 90 дней → пометить `stale: true`.
- Раз в месяц — предложить пользователю «архивировать stale».

### Качество
- В шаблоне есть поле `quality`. Помогает при ротации.
- `quality: low` — не цитировать без перепроверки.

### Согласованность
- `knowledge/` синхронизируется с Obsidian vault (если настроено в `TOOLS.md`).
- Для папки «Для openclaw» — авто-синхронизация.
- Для остального vault — спросить перед копированием.

## Анти-паттерны

- ❌ Делать `web_search` без проверки кеша — 80% случаев уже там
- ❌ Кешировать короткие ответы («формула F=ma») — это не материал, это факт
- ❌ Хранить без frontmatter (потеряется структура для поиска)
- ❌ Складывать всё в `knowledge/misc/` — должна быть структура по предметам
- ❌ Перезаписывать существующий материал без version bump
- ❌ Кешировать платные/приватные источники (риск copyright + токены)
- ❌ Не обновлять `_index.md` — поиск по кешу сломается

## Связанные навыки

- `daily-plan` — в задаче «прочитать §X учебника» ссылается на `knowledge/<subject>/...`
- `study-plan` — при составлении плана ссылки на материалы
- `goal-planned` — делит с этим навыком субагента `researcher`; в глубоком режиме, в черновиках «ресурсы по фазам» — ссылки на кеш
- `TOOLS.md` — настройка синхронизации `knowledge/` с Obsidian
- `research-assistant` (субагент) — для тяжёлого research через `sessions_spawn`, конфигурируется в `openclaw.json` (модель `minimax/MiniMax-M3`, скиллы `web-search` + `web-fetch`)

## Метрики

- Cache hit rate (сколько запросов нашло материал в кеше)
- Средний возраст материала на момент использования
- Число `stale` материалов (если > 30% — плохая ротация)
- Самые частые темы (для приоритетного research)
