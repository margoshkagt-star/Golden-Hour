---
name: notes-forge-pipeline
description: "Путь forgeable-идеи от бота до SKILL.md через forge-skill агента. Research→Design→Tests→Save→Report. 🔨."
---

# notes-forge-pipeline

Полный путь forgeable-идеи от сообщения в Telegram до готового `SKILL.md` в `workspace/Golden-Hour/skills/<slug>/`. Включает ручной fallback через `/skills`.

## Цель

Дать агенту в OpenClaw (обычно notes-keeper) чёткое понимание, что делать с записями в `forge_queue.jsonl`: как дёрнуть forge-skill, что передать, как обработать ответ, как пометить в очереди.

## Триггер

- `forge_queue.jsonl` содержит записи со `status: pending`
- Пользователь говорит «обработай forge_queue», «запусти forge», «сфорджи идеи»
- Задача «почему forge-skill не отвечает», «где SKILL.md от идеи X»
- Дебаг: forge результат не появился в `workspace/Golden-Hour/skills/`

## Логика

### 5 шагов пайплайна (≤5 мин на идею)

```
1. Research      ← web_search + web_fetch топ-3-5 источников (≤90 сек)
2. Design        ← SKILL.md по шаблону (frontmatter + 7 секций)
3. Tests         ← pytest до зелёного
4. Save          ← workspace/Golden-Hour/skills/<slug>/
5. Report        ← вернуть отчёт инициатору через sessions_send
```

### Где каждый шаг живёт

| Шаг | Где | Что делает |
|---|---|---|
| 1. Research | forge-skill агент | web_search + web_fetch, проверка дубликатов в `workspaces/golden-hour/skills/` и `workspace/Golden-Hour/skills/` |
| 2. Design | forge-skill агент | SKILL.md по строгому шаблону: frontmatter (name + description ≤160 байт) + 7 секций (Цель/Триггер/Логика/Вход-Выход/Примеры/Что НЕ делает/Зависимости) |
| 3. Tests | forge-skill агент | pytest: frontmatter, no placeholders, sections present, + поведенческие если есть Python. Прогнать. Добиться зелёного. |
| 4. Save | forge-skill агент | `workspace/Golden-Hour/skills/<slug>/` с SKILL.md, proposal.json, tests/test_smoke.py |
| 5. Report | sessions_send | вернуть инициатору |

### Шаблон SKILL.md (ОБЯЗАТЕЛЬНЫЕ секции)

```yaml
---
name: <slug>
description: "<≤160 байт, что делает + эмодзи>"
---
```

Секции (все 7 обязательны):
1. **Цель** — зачем этот скилл
2. **Триггер** — когда и как вызывается
3. **Логика** — пошаговый алгоритм
4. **Вход → Выход** — таблица типов и описаний
5. **Примеры** — doctest + пользовательский вид
6. **Что НЕ делает** — границы
7. **Зависимости** — от чего зависит

### Протокол вызова forge-skill

**Plain text (минимум):**
```
idea: <краткое описание идеи>
source_idea_id: ts=<unix> user_id=<chat_id>
```

**JSON (структурированно):**
```json
{
  "idea": "...",
  "source_idea_id": "ts=<unix> user_id=<chat_id>",
  "context": {
    "user_key": "beatusx",
    "related_skills": ["..."],
    "urgency": "low|normal|high"
  }
}
```

**Вызов:**
```python
sessions_send(
    agentId="forge-skill",
    message="<idea + source_idea_id>"
)
```

### Что forge-skill вернёт

**Успех:**
```
🔨 forge-skill: <slug>
📁 workspace/Golden-Hour/skills/<slug>/
🔬 Research: N источников
🧪 Tests: passed (M проверок)
📝 Sources: <url1>, <url2>, ...
✅ Готово к коммиту через Cursor.
```

**Проблема:**
```
⚠️ forge-skill: <slug>
Причина: <коротко>
Что сделано: <частично>
Следующий шаг: <что делать>
```

### Что делать с результатом (на стороне notes-keeper)

```python
# 1. Получить ответ от forge-skill через sessions_send
# 2. Распарсить: ✅ или ⚠️
# 3. Обновить forge_queue.jsonl:
item["status"] = "done" if "✅" in response else "failed"
item["result_summary"] = response
item["processed_at"] = now_iso()
# 4. Если ✅ — добавить запись в memory/skills-digest.md
# 5. Если ⚠️ — уведомить Karim'а, оставить в failed для ретрая
```

### Локальный fallback: /skills

Команда `/skills [scope]` запускает `idea_to_skill.run_pipeline(scope)` — локальный генератор без research и тестов. Используется, когда forge-skill агент недоступен.

**Что умеет:**
- Берёт forgeable-идеи из `notes.jsonl`
- Создаёт SKILL.md в `workspace/Golden-Hour/skills/<slug>/`
- Логирует в `memory/skills-digest.md`

**Что НЕ умеет:**
- Research (тянет из общих знаний LLM)
- Tests (не создаёт)
- Quality gates (нет зелёного pytest)

**Когда использовать:**
- Forge-skill агент не зарегистрирован
- Нужно быстро сделать драфт для редактирования руками
- Тестовая среда без forge-skill

### Гарантии forge-skill (контракт)

- ✅ В SKILL.md после frontmatter НЕ будет `...` или «дописать»
- ✅ Все 7 секций шаблона присутствуют
- ✅ `pytest tests/` проходит
- ✅ Использует существующую Golden-Hour инфраструктуру

### ЗАПРЕЩЕНО для forge-skill (по контракту)

- ❌ Писать скиллы с плейсхолдерами / TODO
- ❌ Трогать рабочую копию `workspaces/golden-hour/skills/` (только staging `workspace/Golden-Hour/skills/`)
- ❌ Пуш в GitHub
- ❌ Использовать реальные API-ключи в тестах
- ❌ Принимать вызовы не от notes-keeper / main / skill-forge
- ❌ Запускать необратимые действия без явного `confirm` Karim'а

## Вход → Выход

| Вход | Действие | Выход |
|---|---|---|
| `forge_queue.jsonl` с pending | Цикл: `sessions_send` → forge-skill → mark status | Готовые SKILL.md + обновлённая очередь |
| «Обработай forge_queue» | Запустить цикл | N идей обработано |
| «Где SKILL.md от идеи X?» | Поиск в `workspace/Golden-Hour/skills/` по `proposal.json → source_idea_id` | Путь к SKILL.md |
| «Forge-skill не отвечает» | Чек A2A allow, agentId, время ожидания | Ретрай или fallback на `/skills` |
| «Сделать SKILL.md из идеи Y» | Вызвать forge-skill с `idea=Y, source_idea_id=Y.ts+Y.user_id` | Готовый skill |
| «Сводка forge-операций» | Парсинг `skills-digest.md` | Список slug'ов с датами |

## Что НЕ делает

- Не запускает forge-skill параллельно (1 идея = 1 вызов, ≤5 мин; очередь последовательная)
- Не модифицирует `workspace/Golden-Hour/skills/` напрямую (это делает forge-skill)
- Не коммитит в git (Karim решает когда мержить staging → production)
- Не вызывает forge-skill от незнакомых в A2A allow (notes-keeper — единственный валидный инициатор)

## Зависимости

| Зависимость | Назначение |
|---|---|
| `forge-skill` агент в OpenClaw | Исполнитель Research→Design→Tests→Save→Report |
| `sessions_send` API | Коммуникация notes-keeper ↔ forge-skill |
| `tools.agentToAgent.allow` | forge-skill в allow-list обоих |
| `workspace/Golden-Hour/skills/` | Staging (куда forge-skill пишет) |
| `memory/forge_queue.jsonl` | Очередь |
| `memory/skills-digest.md` | Лог forge-операций |

## Связанные скиллы

- `notes-bot-architecture` — где pipeline в общей картине
- `notes-idea-intake` — откуда forgeable берутся
- `notes-bot-commands` — `/skills` как fallback
- `notes-bot-operator` — мониторинг forge-очереди
