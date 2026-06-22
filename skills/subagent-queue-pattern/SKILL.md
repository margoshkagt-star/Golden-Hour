---
name: "subagent-queue-pattern"
description: "Устойчивый spawn субагентов: atomic-write контракт + queue + защита от OOM."
---

# subagent-queue-pattern

Шаблон устойчивого спавна субагентов в OpenClaw. Защищает от потери результата, когда main параллельно занят другой задачей, а субагент может упасть (OOM, segfault) или его push-уведомление не дойти.

## Когда применять

- Планируешь заспавнить субагента (через `sessions_spawn` или `sessions_send` + agentTurn)
- Задача длинная (>30 сек) или тяжёлая (большой контекст, риск OOM)
- Main в это время может быть занят другой задачей
- Push-уведомления о завершении субагента могут не дойти (или ты не хочешь на них полагаться)
- Хочешь **гарантированную** возможность забрать результат позже

## Когда НЕ применять

- Задача тривиальная (<5 сек, один tool call) — спавнить субагента не нужно
- Задача строго зависит от немедленного результата (всё равно придётся ждать)
- Можно сделать самому через `read` / `exec` без субагента

## Паттерн: контракт результата

Каждый субагент ОБЯЗАН следовать 3-шаговому контракту:

### Шаг 1. Выполнить задачу

Стандартная работа — читать файлы, делать exec, вызывать tool'ы.

### Шаг 2. Сначала записать результат в файл (atomic write)

```python
import os, json, tempfile

result = {
    "status": "ok" | "error",
    "task": "<краткое описание>",
    "data": <результат>,
    "completed_at": "<ISO timestamp>",
    "model": "<использованная модель>",
    "tokens": {"in": ..., "out": ...},
}

dest_path = r"C:\Users\Admin\.openclaw\workspace\memory\subagent-results\<task_name>.json"
dest_dir = os.path.dirname(dest_path)
os.makedirs(dest_dir, exist_ok=True)

# Atomic write: temp + os.replace (атомарен на одной FS)
fd, tmp_path = tempfile.mkstemp(suffix=".json.tmp", dir=dest_dir)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, dest_path)
except Exception:
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    raise
```

**Почему atomic:** `os.replace` атомарен на одной FS. Если субагент умрёт посреди write — будет либо полный файл, либо никакого. Не получится полу-файл.

### Шаг 3. Потом вернуть короткий ответ

```json
{"status": "ok", "ts": "2026-06-19T15:33:00+03:00", "task": "...", "result_path": "<путь к файлу>"}
```

**Если умрёшь между шагами 2 и 3** — файл остаётся, parent прочтёт через `read`.

## Параметры sessions_spawn (default)

```json
{
    "task": "<task с контрактом выше вшитым в начало>",
    "taskName": "<kebab-case имя для файла результата>",
    "runtime": "subagent",
    "agentId": "main",
    "cleanup": "keep",
    "context": "isolated"
}
```

- `cleanup: "keep"` — child-сессия сохраняется, можно достать результат через `sessions_history(sessionKey=childId)` даже если push не дошёл. **Использовать по умолчанию.**
- `cleanup: "delete"` — только для явно disposable задач (тест, разовый probe)
- `taskName` — kebab-case, стабильный, используется для имени файла результата
- `toolsAllow: ["read","write","edit",...]` — **опционально, но рекомендуется** для безопасности и снижения «поверхности атаки». Subagent не должен иметь доступ ко всем tools (например, `message` для отправки в Telegram, `cron` для создания кронов, `gateway` для управления шлюзом) если задача этого не требует.

## Subject Hygiene (требование к taskName)

`taskName` — это **идентификатор** задачи, по которому parent ищет файл и логи. Должен быть:

✅ **Хорошо:**
- `audit-golden-hour-skills-2026-06-19` — кто, что, когда
- `triage-notes-2026-06-19` — действие + scope + дата
- `research-frameworks-2026-q2` — тема + период

❌ **Плохо:**
- `test`, `task1`, `foo` — generic, невозможно найти
- `process-this` — нет subject, нет scope
- `important` — эмоция, не идентификатор

Subject hygiene позволяет:
- Легко найти результат через `ls memory/subagent-results/`
- Понять по логам, что делал субагент
- Дедуплицировать (если спавним повторно — знаем что уже запускали)

## Лимит на параллельные субагенты

**Эмпирический лимит: 2-4 параллельных субагента.**

Больше — coordination overhead, дебаты между ними в main session, OOM-риск. Если задач больше — разбивай на **волны**:

- Волна 1: спавни 3-4 параллельно
- Дождись результатов (через push events)
- Волна 2: спавни следующие 3-4

## Fan-Out паттерн (несколько параллельно)

Если задача распадается на 2-4 независимых подзадачи:

```python
# Все spawn в ОДНОМ блоке — OpenClaw запустит их параллельно
# (не жди результата одного, чтобы запустить следующий)

subagent_keys = []
for batch in batches:
    result = sessions_spawn(
        task=f"""
КОНТРАКТ РЕЗУЛЬТАТА:
1. Выполни: {batch.task}
2. Запиши финальный JSON в `C:\\\\Users\\\\Admin\\\\.openclaw\\\\workspace\\\\memory\\\\subagent-results\\\\{batch.taskName}.json`
   (atomic write — temp + os.replace).
3. Верни короткий статус.

ЗАДАЧА: {batch.details}
""",
        taskName=batch.taskName,
        runtime="subagent",
        agentId="main",
        cleanup="keep",
        context="isolated",
    )
    subagent_keys.append((batch.taskName, result["childSessionKey"]))

# Не поллить! Push events придут сами в main session.
# В следующих turn'ах, когда subagent'ы доставят результаты,
# прочитай их файлы и синтезируй.
```

Push-based auto-announce: результаты приходят как user-message. **Не вызывай** `sessions_list`, `sessions_history`, `exec sleep` после spawn — это блокирует.

## Чтение очереди (parent)

Когда main готов принять результат:

1. **Сначала** проверить файл `memory/subagent-results/<task_name>.json` (быстрее, гарантированно)
2. **Если файла нет** — `sessions_history(sessionKey=childId)` (если `cleanup: "keep"`)
3. **Если и там нет** — `subagent died, retry` или `notify user`

## Очередь в OpenClaw (встроенная)

OpenClaw уже имеет queue для inbound messages (default mode `steer`):
- `docs/concepts/queue.md` — общая модель
- `docs/concepts/queue-steering.md` — steering behavior

**Субагенты не блокируют main lane.** Результаты субагентов приходят в main как push events, инжектятся в следующий LLM call (steer mode).

**Но:** если субагент умер (OOM, segfault) — push event не отправляется → очередь пуста → нужно восстанавливать через файл или `sessions_history`.

## Анти-паттерны

- **`cleanup: "delete"` для важных задач** — сессия удаляется, до результата не добраться
- **`model: ollama/qwen2.5:7b` "чтобы не падало"** — локалка **только** для fallback при падении основной модели, не для обхода OOM
- **Длинная задача одним куском без чекпоинтов** — если упадёт на 80%, потеряешь всё
- **`taskName: "test"` или рандомный** — потом не найдёшь файл, subject hygiene нарушена
- **Записывать результат в файл ПОСЛЕ ответа** — если умрёшь между, файл не появится
- **Положиться только на push event** — если push не дошёл, результат потерян
- **`agentId: "golden-hour"` (или другой "реальный" агент) для лёгких задач** — лишний оверхед, используй main
- **Спавнить >4 параллельно** — coordination overhead, OOM-риск
- **Поллить `sessions_list` / `sessions_history` / `exec sleep` после spawn** — блокирует push delivery
- **`toolsAllow` = все tools (не задан)** — субагент получает доступ к message/cron/gateway, что ему обычно не нужно

## Чек-лист перед spawn

- [ ] Задача реально требует субагента? (если нет — делай сам)
- [ ] Есть `taskName` в kebab-case?
- [ ] `cleanup: "keep"`?
- [ ] Контракт результата вшит в начало `task`?
- [ ] В контракте упомянут путь к файлу с правильным `<task_name>`?
- [ ] Сохранил `childSessionKey` для fallback?

## Пример

```python
task = """
КОНТРАКТ РЕЗУЛЬТАТА:
1. Выполни задачу ниже.
2. Запиши финальный JSON в `C:\\\\Users\\\\Admin\\\\.openclaw\\\\workspace\\\\memory\\\\subagent-results\\\\triage-notes-2026-06-19.json`
   (atomic write — через temp-файл + os.replace, не прямой write).
3. Только потом верни короткий ответ.

Если умрёшь между шагами 2 и 3 — файл всё равно остаётся на диске, я прочту его через `read`.

ЗАДАЧА:
Триаж memory/notes.jsonl за 2026-06-19. Классифицируй все записи (idea/chat/trash/task/bug), сгруппируй по user_id, выведи топ-3 идеи.
"""

result = sessions_spawn(
    task=task,
    taskName="triage-notes-2026-06-19",
    runtime="subagent",
    agentId="main",
    cleanup="keep",
    context="isolated",
)
child_key = result["childSessionKey"]

# Позже: прочитать результат
import os, json
result_path = r"C:\\Users\\Admin\\.openclaw\\workspace\\memory\\subagent-results\\triage-notes-2026-06-19.json"
if os.path.exists(result_path):
    with open(result_path, encoding="utf-8") as f:
        data = json.load(f)
else:
    data = sessions_history(sessionKey=child_key)
```

## Связанные

- `agent-orchestration` (skill) — **когда и зачем** спавнить, какие типы агентов, шаблоны spawn. Этот скилл (subagent-queue-pattern) — **как гарантированно получить результат** даже при падении.
- `docs/concepts/queue.md` — OpenClaw command queue
- `docs/concepts/queue-steering.md` — steering behavior
- `docs/concepts/multi-agent.md` — multi-agent routing
- [agentic-patterns.com/patterns/sub-agent-spawning](https://agentic-patterns.com/patterns/sub-agent-spawning/) — канонический паттерн (validated in production), откуда взяты Subject Hygiene, tool scoping, 2-4 лимит
- [How Agents Manage Other Agents: 4 Patterns in 2026](https://medium.com/design-bootcamp/how-agents-manage-other-agents-four-subagents-patterns-in-2026-7abe5ab83b88) — Inline Tool, Fan-Out и др.
