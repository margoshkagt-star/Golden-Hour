# SETUP — как запустить агента «Золотой час»

Ветка `unified-agent-v2` — цельный ИИ-агент для подготовки к олимпиадам/экзаменам/темам: знакомится, **запоминает каждого пользователя в отдельной папке**, строит план, ведёт прогресс, напоминает.

Две фазы: **(1) настройка** (только вопросы) → **(2) рабочий режим** (план, задачи, чек-ины, напоминания). Рабочие скиллы включаются только после завершения настройки.

---

## 1. Предпосылки

- Установлен **OpenClaw** (CLI + gateway). Проверка: `openclaw --version`.
- Есть рабочее пространство агента, напр. `~/.openclaw/workspaces/golden-hour/`
  (Windows: `C:\Users\<you>\.openclaw\workspaces\golden-hour\`).
- Для напоминаний — подключённый Telegram-бот (см. шаг 4).

---

## 2. Установка скиллов

Скопировать содержимое репозитория в воркспейс агента:

```bash
# из корня этого репозитория
cp -r skills/*      ~/.openclaw/workspaces/golden-hour/skills/
cp    SOUL.md       ~/.openclaw/workspaces/golden-hour/SOUL.md
cp    AGENTS.md     ~/.openclaw/workspaces/golden-hour/AGENTS.md
```

PowerShell (Windows):

```powershell
$ws = "$env:USERPROFILE\.openclaw\workspaces\golden-hour"
Copy-Item .\skills\*  "$ws\skills\" -Recurse -Force
Copy-Item .\SOUL.md   "$ws\SOUL.md" -Force
Copy-Item .\AGENTS.md "$ws\AGENTS.md" -Force
```

> **Важно:** `SOUL.md` — это **реальная логика исполнения** (агент грузит его в каждой сессии). Файлы `skills/<name>/SKILL.md` — подробные дизайн-документы. Без `SOUL.md` скиллы не «склеятся» в единый поток.

Создать профиль владельца из шаблона (свои данные):

```bash
cp USER.example.md  ~/.openclaw/workspaces/golden-hour/USER.md
# отредактировать имя, Telegram, часовой пояс
```

---

## 3. Включить inline-кнопки (для напоминаний)

В `~/.openclaw/openclaw.json` у агента `golden-hour` должно быть:

```jsonc
{
  "agents": {
    "golden-hour": {
      "capabilities": { "inlineButtons": "all" }
    }
  }
}
```

Это нужно скиллу `goal-checkin-notifier` (кнопки «Начинаю / Отложить / Пропустить»).

---

## 4. Telegram (опционально, для пингов и чек-инов)

- Подключить Telegram-канал агенту в `openclaw.json` (токен бота).
- Агент сам определит пользователя по Telegram id (см. ниже «Как агент узнаёт пользователя»).

---

## 5. Перезапуск

```bash
openclaw gateway restart      # или: openclaw gateway stop && openclaw gateway start
openclaw gateway status
```

---

## 6. Проверка

Запустить тестовую сессию:

```bash
openclaw agent --agent golden-hour --session-key test-1 --message "привет"
```

Ожидаемо:
1. **Новый пользователь** → приветствие + запрос имени → выбор цели → ветка (олимпиада/экзамен/тема) → дедлайн + часы → план.
2. После настройки появляется папка `users/<user_key>/profile.md` с `setup_status: complete`.
3. **Повторный заход** (новая сессия, тот же пользователь) → «С возвращением! 1. Продолжить 2. Настроить заново».

---

## Как это работает

### Фазы
- **Настройка** (`session-start` → `hello-intro` → `purpose-select` → ветка → `setup-finalize`): только вопросы, профиль собирается по шагам.
- **Рабочий режим** (после `setup_status: complete`): `study-plan`, `daily-plan`, `daily-study-checkin`, `goal-checkin-notifier`, `current-tasks`, `task-tracker`, `task-triage`.

### Как агент узнаёт пользователя
В начале каждой сессии определяется `user_key` по **отправителю канала** (не по имени в тексте):

| Источник | `user_key` |
|---|---|
| Telegram | `tg-<id>` |
| Другой канал | `<channel>-<id>` |
| Webchat / CLI | `local` |

Затем агент смотрит `users/<user_key>/profile.md`:
- **нет файла** → новый → онбординг;
- **есть, `setup_status: in_progress`** → «продолжить настройку / заново»;
- **есть, `setup_status: complete`** → «продолжить (загрузить план) / настроить заново».

Новизна определяется **наличием папки на диске**, а не памятью чата — поэтому после `/new` или перезапуска тот же Telegram-пользователь опознаётся и получает свой план.

### Хранение данных (по пользователям)
```
users/<user_key>/
  profile.md    # цель, предмет/темы, уровни, дедлайн, часы, setup_status
  plan.md       # макро-план (недели/месяцы)
  progress.md   # дневник чек-инов, streak, закрытые темы
  tasks.md      # активные задачи
  tasks.yaml    # данные трекера (опц.)
  plans/
    YYYY-MM-DD.json   # дневные планы для напоминаний
```
Папка `users/` **приватна** — её НЕ коммитят в репозиторий (см. `.gitignore`).

---

## Состав скиллов

**Инфраструктура / память**
- `user-profile` — слой хранения: папка на пользователя.
- `session-start` — точка входа: новый/старый, загрузка-или-сброс.
- `setup-finalize` — финал настройки (дедлайн, часы), `setup_status: complete`.

**Онбординг**
- `hello-intro`, `purpose-select`
- olympiad: `olympiad-grade` → `olympiad-subject` → `olympiad-self-asses`
- exam: `exam-type` → `exam-subject` → `exam-topics` → `exam-self-assess`
- topic: `topic-clarify` → `topic-self-assess`

**Рабочий режим**
- `study-plan` — макро-план в папку пользователя.
- `daily-plan` — дневной план (JSON) для напоминаний.
- `daily-study-checkin` — ежедневный чек-ин + streak.
- `goal-checkin-notifier` — утренний бриф, пинги, вечерний чек-ин (Telegram).
- `current-tasks` — живой список задач.
- `task-tracker` — прогресс по весу, итоги.
- `task-triage` — приоритизация, декомпозиция, автокатегории.

---

## Частые проблемы

| Симптом | Причина / решение |
|---|---|
| Агент каждый раз спрашивает имя заново | Не скопирован `SOUL.md` (логика `session-start`). Скопировать и перезапустить gateway. |
| Рабочие команды («план», «задачи») игнорируются | `setup_status ≠ complete` — закончить настройку. |
| Нет напоминаний | Нет `users/<user_key>/plans/YYYY-MM-DD.json` или выключены `inlineButtons`. |
| Данные пользователей смешиваются | Проверить, что `user_key` берётся из канала, а не из имени. |
