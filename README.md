# Golden Hour — OpenClaw Skills (ветка `unified-agent-v2`)

Цельный ИИ-агент для подготовки к **олимпиадам / экзаменам / темам** и тайм-менеджмента.
Знакомится, **запоминает каждого пользователя в отдельной папке**, строит план, ведёт прогресс, напоминает.

> 🚀 **Как запустить — см. [SETUP.md](SETUP.md).**

## Главное

- **Две фазы:** настройка (только вопросы) → рабочий режим (план, задачи, чек-ины, напоминания). Рабочие скиллы включаются только после `setup_status: complete`.
- **Память по пользователям:** каждый пользователь = папка `users/<user_key>/` (`tg-<id>` / `local`). Данные не смешиваются.
- **Старт сессии:** агент сам понимает, новый это человек или вернувшийся (по наличию `users/<user_key>/profile.md`), и предлагает «продолжить / настроить заново».
- **Реальная логика — в `SOUL.md`** (грузится в каждой сессии). `skills/<name>/SKILL.md` — дизайн-документы.

## Скиллы

**Инфраструктура / память**

| Скилл | Описание |
|---|---|
| `user-profile` | Слой хранения: папка `users/<user_key>/` (profile/plan/progress/tasks) |
| `session-start` | Точка входа: новый/старый пользователь, загрузка-или-сброс |
| `setup-finalize` | Финал настройки (дедлайн, часы/нед) → `setup_status: complete` |

**Онбординг**

| Скилл | Описание |
|---|---|
| `hello-intro` | Приветствие + имя (дословно) |
| `purpose-select` | Выбор цели: экзамен / олимпиада / тема |
| `olympiad-grade` / `olympiad-subject` / `olympiad-self-asses` | Класс → предмет → уровень (адаптивно) |
| `exam-type` / `exam-subject` / `exam-topics` / `exam-self-assess` | Тип → предмет → темы → уровень по темам |
| `topic-clarify` / `topic-self-assess` | Уточнение темы → уровень по теме |

**Рабочий режим**

| Скилл | Описание |
|---|---|
| `study-plan` | Макро-план (недели/месяцы) в папку пользователя |
| `daily-plan` | Дневной план `plans/YYYY-MM-DD.json` для напоминаний |
| `daily-study-checkin` | Ежедневный чек-ин прогресса + streak |
| `goal-checkin-notifier` | Telegram: утренний бриф, пинги задач, вечерний чек-ин |
| `current-tasks` | Живой список активных задач |
| `task-tracker` | Прогресс по весу, итоги, дашборд |
| `task-triage` | Приоритизация, декомпозиция, автокатегории |

## Цепочка

```
session-start (новый/старый?)
  ├─ старый  → «продолжить / настроить заново» → загрузка плана
  └─ новый   → hello-intro → purpose-select → [ветка] → setup-finalize → study-plan
                 ├─ olympiad → grade → subject → self-asses
                 ├─ exam     → type → subject → topics → self-assess
                 └─ topic    → clarify → self-assess

рабочий режим: study-plan → daily-plan → goal-checkin-notifier / current-tasks / task-tracker
```

## Структура

```
skills/<skill-name>/SKILL.md   # дизайн-документ скилла
SOUL.md                        # реальная логика исполнения (грузится агентом)
AGENTS.md                      # базовое поведение воркспейса
USER.example.md                # шаблон профиля владельца
SETUP.md                       # инструкция по установке
```

Приватные данные (`users/`, `memory/`, `projects/`, `USER.md`) в репозиторий не коммитятся (см. `.gitignore`).

## Установка

См. **[SETUP.md](SETUP.md)**.
