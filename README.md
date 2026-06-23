# Golden Hour — ИИ-агент для подготовки и тайм-менеджмента

ИИ-агент для подготовки к **олимпиадам / экзаменам / темам**: знакомится, **запоминает каждого пользователя в отдельной папке**, строит план, ведёт прогресс, напоминает в Telegram.

> **Установка:** [SETUP.md](SETUP.md) (ветка `main`). Полный дистрибутив: [`agent-install`](https://github.com/margoshkagt-star/Golden-Hour/tree/agent-install).

## Что внутри

| Компонент | Назначение |
|---|---|
| `SOUL.md` | Главная логика агента — грузится в каждой сессии |
| `skills/` | Дизайн-документы скиллов (онбординг, план, задачи, напоминания) |
| `scripts/` | Детерминированные скрипты планирования (Node ≥18, без npm) |
| `openclaw.agent.example.json` | Фрагмент конфига OpenClaw для Telegram-бота |
| `users/_example/` | Шаблон структуры данных пользователя |

## Две фазы работы

1. **Настройка** — только вопросы: имя, цель, предмет, уровень, дедлайн.
2. **Рабочий режим** — план, дневные слоты, чек-ины, фокус-таймер, статистика, календарь.

Рабочие скиллы включаются только после `setup_status: complete` в `users/<user_key>/profile.md`.

## Цепочка

```
session-start
  ├─ вернувшийся → продолжить / настроить заново
  └─ новый → hello-intro → purpose-select → [ветка] → setup-finalize → study-plan
                 ├─ olympiad → grade → subject → self-asses
                 ├─ exam     → type → subject → topics → self-assess
                 └─ topic    → clarify → self-assess

рабочий режим: daily-plan → goal-checkin-notifier → focus-timer → daily-study-checkin
```

## Скиллы

### Онбординг (`skills/_onboarding/`)

| Скилл | Описание |
|---|---|
| `hello-intro` | Приветствие + имя (дословно) |
| `purpose-select` | Цель: экзамен / олимпиада / тема |
| `olympiad-grade` / `olympiad-subject` / `olympiad-self-asses` | Олимпиадная ветка |
| `exam-type` / `exam-subject` / `exam-topics` / `exam-self-assess` | Экзаменационная ветка |
| `topic-clarify` / `topic-self-assess` | Ветка «тема» |
| `setup-finalize` | Дедлайн, часы, приоритеты → `setup_status: complete` |

### Рабочий режим

| Скилл | Описание | Статус |
|---|---|---|
| `study-plan` | Макро-план (недели/месяцы) | applied |
| `daily-plan` | Дневной план `plans/YYYY-MM-DD.json` | applied |
| `goal-checkin-notifier` | Telegram: бриф, пинги, вечерний чек-ин | applied |
| `focus-timer` | Фокус-сессии и статистика | applied |
| `current-tasks` | Живой список задач | applied |
| `task-tracker` | Прогресс, дедлайны, итоги | applied |
| `task-triage` | Приоритизация и декомпозиция | applied |
| `spaced-repetition` | Повтор слабых тем | applied |
| `longterm-stats` | Статистика за период | applied |
| `study-cards` | Render engine: план, статистика, **таблицы** → PNG (тёмная тема) | applied |
| `study-plan-cards` | Orchestrator: plan/state/topics/full → `study-cards` | applied |
| `pomodoro` | Циклы работа/перерыв, DND, stats | applied |
| `temporal-kg` | Временной граф учебных событий | applied |
| `team-tasks` | Командные таски: инвайты, lifecycle, уведомления | applied |
| `soul-guardian` | Контроль целостности SOUL.md / AGENTS.md | applied |
| `clawsec-suite` | Advisory feed, guarded skill install | applied |
| `goal-materials` | Материалы по цели: add/pick/status; web/file/image/draw через саб-агента | applied |
| `web-material-finder` | Саб-агент: web/file-поиск, AI-картинки, программная отрисовка (5 режимов) | applied |
| `google-calendar-sync` | Синхронизация с Google Calendar | applied |
| `reflection-loop` | Рефлексия при срывах | applied |
| `material-cache` | Кэш материалов по темам | applied |
| `help-menu` | Меню возможностей | applied |

### Инфраструктура

| Скилл | Описание | Статус |
|---|---|---|
| `coder` | Код по запросу — делегируется саб-агенту `code-writer`; main-сессия не пишет код | applied |

## Скрипты

Планирование — **только через скрипты**, не «в голове» у LLM:

```powershell
node scripts/session-start.mjs --user tg-123456 --telegram-id 123456
node scripts/study-plan.mjs --user tg-123456 --dry-run
node scripts/daily-plan.mjs --user tg-123456 --dry-run
node scripts/study-plan-cards.mjs --user tg-123456
node scripts/table-cards.mjs --user tg-123456 --title "План" --text "| A | B |`n|---|---|`n| 1 | 2 |"
node scripts/pomodoro.mjs start --user tg-123456
node scripts/temporal-kg.mjs import-all
node scripts/team-tasks.mjs team list --user tg-123456
node scripts/run-tests.mjs
```

Визуальные карточки (`study-plan-cards` → `study-cards`):

```powershell
node skills/study-plan-cards/scripts/render.js --mode=from-plan-file --source=cards/plan.json --output-dir=cards/
node skills/study-plan-cards/scripts/render.js --mode=from-state --source=state/tasks.yaml --output-dir=cards/
node skills/study-plan-cards/scripts/render.js --mode=full --plan-source=cards/plan.json --stats-source=state/tasks.yaml --themes=dark
```

Полный список: [scripts/README.md](scripts/README.md).

## Ветки репозитория

| Ветка | Содержимое |
|---|---|
| `main` | Только скиллы (legacy) |
| `unified-agent-v2` | Ранний дистрибутив агента |
| **`agent-install`** | **Полная установка** — рекомендуется |

## Лицензия

См. `skills/goal-materials/LICENSE` (MIT для goal-materials). Остальные скиллы в статусе `proposal` могут меняться.
