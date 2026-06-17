# Golden Hour — OpenClaw Skills

ИИ-агент для тайм-менеджмента и работы с задачами. Этот репозиторий содержит **Agent Skills** (формат OpenClaw / Cursor) для проекта [Golden Hour](https://github.com/margoshkagt-star/Golden-Hour).

## Скиллы

| Скилл | Описание | Статус |
|-------|----------|--------|
| [task-triage](skills/task-triage/) | Триаж задач: вес, декомпозиция, автокатегории, автовыполнение | proposal v2 |
| [current-tasks](skills/current-tasks/) | Живой список активных задач | applied |
| [note-to-file](skills/note-to-file/) | Сохранение заметок в inbox + notes.jsonl | proposal |
| [show-ideas](skills/show-ideas/) | Дайджест идей за период | proposal |
| [idea-tools](skills/idea-tools/) | Поиск, теги, статистика по идеям | proposal |

## Структура

```
skills/
  <skill-name>/
    SKILL.md          # основной файл скилла
    proposal.json     # метаданные Skill Workshop
    assets/           # шаблоны (опционально)
    examples/         # примеры (опционально)
    tests/            # тестовые фикстуры (опционально)
```

## Установка в OpenClaw

Скопируйте нужную папку в `~/.openclaw/workspace/skills/<skill-name>/` и перезапустите gateway, либо примените proposal через Skill Workshop.

## Лицензия

См. репозиторий. Скиллы в статусе `proposal` ещё не финальные.
