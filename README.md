# Golden Hour — OpenClaw Skills

ИИ-агент для подготовки к олимпиадам/экзаменам и тайм-менеджмента. Этот репозиторий содержит **Agent Skills** (формат OpenClaw / Cursor) для проекта [Golden Hour](https://github.com/margoshkagt-star/Golden-Hour).

## Скиллы — онбординг и подготовка

| Скилл | Описание | Статус |
|-------|----------|--------|
| [hello-intro](skills/hello-intro/) | Первое знакомство: приветствие + имя (запоминает дословно) | applied |
| [purpose-select](skills/purpose-select/) | Выбор цели: экзамен / олимпиада / тема | applied |
| [olympiad-grade](skills/olympiad-grade/) | Класс для олимпиадной подготовки (7–11 / выпускник) | applied |
| [olympiad-subject](skills/olympiad-subject/) | Предмет олимпиады | applied |
| [olympiad-self-asses](skills/olympiad-self-asses/) | Самооценка знаний по предмету (адаптивные опции) | applied |
| [exam-type](skills/exam-type/) | Тип экзамена: ЕГЭ / ОГЭ / вступительные / другой | applied |
| [exam-subject](skills/exam-subject/) | Предмет экзамена | applied |
| [exam-topics](skills/exam-topics/) | Темы экзамена (кодификатор или список пользователя) | applied |
| [exam-self-assess](skills/exam-self-assess/) | Уровень по каждой теме экзамена | applied |
| [topic-clarify](skills/topic-clarify/) | Уточнение произвольной темы для изучения | applied |
| [topic-self-assess](skills/topic-self-assess/) | Самооценка по конкретной теме | applied |
| [daily-plan](skills/daily-plan/) | Генерация `plans/YYYY-MM-DD.json` из профиля пользователя | applied |

## Скиллы — задачи и напоминания

| Скилл | Описание | Статус |
|-------|----------|--------|
| [task-triage](skills/task-triage/) | Триаж задач: вес, декомпозиция, автокатегории, автовыполнение | proposal v2 |
| [goal-checkin-notifier](skills/goal-checkin-notifier/) | Telegram-напоминания и чек-ины по целям: утренний бриф, пинги задач, вечерний обзор | applied |
| [focus-timer](skills/focus-timer/) | Таймер фокус-сессий: выбор длительности, похвала по завершении, статистика за 5 периодов | applied |
| [current-tasks](skills/current-tasks/) | Живой список активных задач | applied |
| [task-tracker](skills/task-tracker/) | Трекер задач: прогресс, КТ, напоминания, итоги. Вывод в чат + Obsidian-дашборд | applied |
| [longterm-stats](skills/longterm-stats/) | Долговременная статистика: неделя/месяц/год/всё время в часах и весе, долговременные задачи, дедлайны | applied |
| [goal-materials](skills/goal-materials/) | Материалы по целям: задачи, теория, ссылки; add/pick/status; memory/inbox + Telegram-кнопки (README, MIT) | applied |
| [note-to-file](skills/note-to-file/) | Сохранение заметок в inbox + notes.jsonl | proposal |
| [show-ideas](skills/show-ideas/) | Дайджест идей за период | proposal |
| [idea-tools](skills/idea-tools/) | Поиск, теги, статистика по идеям | proposal |

## Скиллы — инфраструктура

| Скилл | Описание | Статус |
|-------|----------|--------|
| [coder](skills/coder/) | MANDATORY-делегация генерации кода: main спавнит саб-агента `code-writer` через `sessions_spawn`, сам не пишет. Архитектурно main лишён `write`/`edit`/`apply_patch`/`exec`/`process` (README, references/architecture, MIT) | applied |

## Цепочка онбординга

```
hello-intro → purpose-select → [ветка]
  ├─ olympiad → olympiad-grade → olympiad-subject → olympiad-self-asses
  ├─ exam     → exam-type → exam-subject → exam-topics → exam-self-assess
  └─ topic    → topic-clarify → topic-self-assess
```

После онбординга: `daily-plan` → `goal-checkin-notifier` → `focus-timer`.

## Структура

```
skills/
  <skill-name>/
    SKILL.md          # основной файл скилла
    proposal.json     # метаданные Skill Workshop (опционально)
    assets/           # шаблоны (опционально)
    examples/         # примеры (опционально)
    tests/            # тестовые фикстуры (опционально)
```

## Установка в OpenClaw

Скопируйте нужную папку в `~/.openclaw/workspaces/golden-hour/skills/<skill-name>/` и перезапустите gateway, либо примените proposal через Skill Workshop.

## Лицензия

См. репозиторий. Скиллы в статусе `proposal` ещё не финальные.
