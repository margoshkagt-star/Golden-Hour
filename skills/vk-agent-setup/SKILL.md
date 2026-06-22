---
name: "vk-agent-setup"
description: "Создать изолированного OpenClaw-агента и подключить VK (не вешать VK на main). Триггеры: подключи VK, создай VK-бота, vk-buddy, openclaw-vk, pairing approve, channels.vk"
---

# VK Agent Setup — изолированный агент + VK-канал

Процедура подключения VK к OpenClaw **через отдельного агента**, а не через `main`.

Проверено: OpenClaw 2026.6.8, плагин `@openclaw-vk/vk`, рабочий пример `vk-buddy` (Виктор).

Подробный референс: `workspace/memory/instructions/VK-Agent-Setup.md`  
Настройка VK-сообщества: `workspace/memory/instructions/VK-OpenClaw-Setup.md`  
Живой пример: `workspaces/vk-buddy/`

---

## Главный принцип (читать первым)

> **НЕ** «прикрутить VK к main».  
> **ДА** «создать нового агента под канал».

| Подход | Почему плохо / хорошо |
|---|---|
| VK на `main` | ❌ Загрязняет контекст, падение VK влияет на main, общая память |
| Отдельный агент (`vk-buddy`) | ✅ Изоляция контекста, своя идентичность, свой воркспейс, независимые сессии |

Имена должны совпадать по цепочке: `agentId` = `accountId` = имя воркспейса (удобно, не обязательно юридически, но **accountId в channels и bindings обязан совпадать**).

---

## Когда применять

- «Подключи VK», «создай VK-бота», «связь агента с VK»
- «Резервный канал если Telegram ляжет»
- Пользователь дал VK community token

**Не применять:**
- Пользователь явно хочет VK **только** на `main` (предупреди о минусах, но выполни по запросу)
- Нет токена сообщества VK

---

## Антипаттерны (типичные ошибки агентов)

| # | Ошибка | Правильно |
|---|---|---|
| 1 | Вешать VK на `main` | Создать `agents.list` entry + отдельный `workspaces/<id>/` |
| 2 | Забыть `bindings` | `bindings`: `{ agentId, match: { channel: "vk", accountId } }` — иначе VK идёт в main |
| 3 | Токен в `C:\secrets\` или произвольный путь | `%USERPROFILE%\.openclaw\secrets\<accountId>.token` |
| 4 | `channels.vk.token` без `accounts` | `channels.vk.accounts.<accountId>` — multi-account под каждый агент |
| 5 | Тест `groups.getById` через curl/API | `openclaw channels status --probe` — учитывает plugin, binding, accountId |
| 6 | Не проверить `plugins.entries.vk.enabled` | Явно `true` в `openclaw.json` |
| 7 | Pairing «в теории» | Полный flow: пользователь пишет в VK → `pairing list` → `pairing approve vk` |
| 8 | VK user id = Telegram chat id | Это **разные** id! Брать из pairing-сообщения бота или `users.get` |
| 9 | Токен в shell / чат | Записать в файл через редактор, не `curl` с токеном в команде |
| 10 | Не перезапустить gateway | После правок: `openclaw config validate` → `openclaw gateway restart` |

---

## Процедура (пошагово)

### Шаг 0. Проверить плагин

```powershell
openclaw plugins list
```

В `openclaw.json`:

```json
"plugins": {
  "entries": {
    "vk": { "enabled": true }
  }
}
```

Если нет:

```powershell
openclaw plugins install @openclaw-vk/vk
openclaw plugins enable vk
```

### Шаг 1. Выбрать id агента

Пример: `vk-buddy` (kebab-case). Дальше везде один `accountId`: `vk-buddy`.

### Шаг 2. Создать агента + binding

**CLI (предпочтительно):**

```powershell
$id = "vk-buddy"
$ws = "$env:USERPROFILE\.openclaw\workspaces\$id"
New-Item -ItemType Directory -Force -Path $ws, "$ws\memory" | Out-Null

openclaw agents add $id `
  --non-interactive `
  --workspace $ws `
  --bind "vk:$id"
```

**Или вручную** — добавить в `agents.list`:

```json
{
  "id": "vk-buddy",
  "name": "vk-buddy",
  "workspace": "C:\\Users\\Admin\\.openclaw\\workspaces\\vk-buddy",
  "agentDir": "C:\\Users\\Admin\\.openclaw\\agents\\vk-buddy\\agent",
  "identity": { "name": "Виктор", "emoji": "💙" }
}
```

Папки:

```powershell
New-Item -ItemType Directory -Force -Path `
  "$env:USERPROFILE\.openclaw\agents\vk-buddy\agent", `
  "$env:USERPROFILE\.openclaw\agents\vk-buddy\sessions"
```

### Шаг 3. Минимальный воркспейс

Создать в `workspaces/<id>/`:

- `IDENTITY.md` — имя, emoji
- `SOUL.md` — миссия, поведение
- `AGENTS.md` — каналы, user_key = `vk-<user_id>`
- `USER.md` — VK user id владельца (не Telegram id!)
- `MEMORY.md` — может быть пустым

### Шаг 4. Токен → файл (не в JSON, не в shell)

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.openclaw\secrets" | Out-Null
# Файл: ~/.openclaw/secrets/vk-buddy.token — одна строка, токен vk1.a....
```

Записывать токен **через Write/редактор файла**, не через API-запросы с токеном в URL.

### Шаг 5. Канал VK — структура `accounts.<id>`

```json
"channels": {
  "vk": {
    "enabled": true,
    "accounts": {
      "vk-buddy": {
        "name": "Виктор",
        "enabled": true,
        "tokenFile": "C:\\Users\\Admin\\.openclaw\\secrets\\vk-buddy.token",
        "dmPolicy": "pairing",
        "allowFrom": ["734640241"]
      }
    }
  }
}
```

`allowFrom` — **VK user id**, не Telegram. После pairing id виден в ответе бота: `Your VK user id: ...`

Опционально owner-команды:

```json
"commands": {
  "ownerAllowFrom": ["telegram:1038917447", "vk:734640241"]
}
```

### Шаг 6. Binding (обязательно!)

Если не сделал через `agents add --bind`:

```json
{
  "type": "route",
  "agentId": "vk-buddy",
  "match": { "channel": "vk", "accountId": "vk-buddy" }
}
```

Проверка:

```powershell
openclaw agents bindings
```

Ожидаемо: `vk-buddy <- vk accountId=vk-buddy`

### Шаг 7. Валидация (правильный тест)

```powershell
openclaw config validate
openclaw gateway restart
# подождать ~10 сек
openclaw channels status --probe
openclaw agents list
```

**Успех:**

```
VK vk-buddy (...): enabled, configured, running, mode:longpoll, token:tokenFile, works
```

**НЕ** использовать `groups.getById` как единственный тест — он не проверяет OpenClaw routing.

### Шаг 8. Pairing (полный flow)

1. Пользователь пишет в **личку сообщества VK** (не человеку)
2. Бот отвечает кодом, например `NRK5RS64`, и VK user id
3. Владелец:

```powershell
openclaw pairing list
openclaw pairing approve vk          # последний pending
openclaw pairing approve vk NRK5RS64 # или с кодом
```

4. Обновить `allowFrom` и `USER.md` реальным VK user id из pairing-сообщения
5. Пользователь пишет снова — агент отвечает

### Шаг 9. Smoke-тест агента

```powershell
openclaw agent --agent vk-buddy --session-key test-1 --message "привет"
```

---

## Чеклист (копировать при выполнении)

```
[ ] plugins.entries.vk.enabled = true
[ ] Новый агент в agents.list (НЕ main)
[ ] workspaces/<id>/ + SOUL.md, AGENTS.md, IDENTITY.md, USER.md
[ ] Токен в ~/.openclaw/secrets/<accountId>.token
[ ] channels.vk.accounts.<accountId> (НЕ плоский channels.vk.token для multi-agent)
[ ] bindings: agentId ↔ vk accountId
[ ] openclaw config validate
[ ] openclaw gateway restart
[ ] openclaw channels status --probe → works
[ ] openclaw agents bindings → маршрут есть
[ ] pairing list → pairing approve vk
[ ] allowFrom = VK user id (не Telegram)
[ ] Пользователь получил ответ в VK
```

---

## Требования к VK-сообществу

В [управлении сообществом](https://vk.com/manage):

1. Сообщения сообщества — включены
2. Long Poll API — включён
3. Типы событий → «Входящие сообщения»
4. Токен с правами: `messages`, `manage`, `photos`, `docs`

---

## Troubleshooting

| Симптом | Причина | Действие |
|---|---|---|
| `access not configured` + pairing code | Первый контакт, dmPolicy=pairing | `openclaw pairing approve vk` |
| Отвечает main, не новый агент | Нет binding | Добавить bindings |
| `configured: true, running: false` | Токен / Long Poll | probe lastError, перевыпустить токен |
| VK id в allowFrom не тот | Перепутали с Telegram | Взять id из pairing-сообщения бота |
| Shell блокирует команды с токеном | Утечка credentials | Писать tokenFile через файловый редактор |

---

## Архитектура (итог)

```
VK сообщество (Long Poll)
        ↓
channels.vk.accounts.vk-buddy
        ↓
bindings → agentId: vk-buddy
        ↓
workspaces/vk-buddy/ (SOUL, память, сессии)
        ↓
agents/vk-buddy/sessions/
```

`main` в этой цепочке **не участвует**.

---

## Стоимость / scope

- Одноразовая настройка: ~5–10 мин, без LLM-токенов если делать через конфиг
- Не спавнить субагентов для этой задачи — достаточно прямого редактирования `openclaw.json` + CLI validate/restart
