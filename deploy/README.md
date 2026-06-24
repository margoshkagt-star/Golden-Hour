# Golden Hour — Deployment Guide

Деплой автоматически запускается при push в ветку **`deploy`** и только в неё.

## Что разворачивается

Полноценный OpenClaw-агент «Золотой час»:
- **OpenClaw CLI** (`npm i -g openclaw@latest`) + **Ollama** (локальная fallback-модель);
- конфиг `openclaw.json` с провайдерами **MiniMax** (primary) + **Ollama** (fallback);
- агенты **golden-hour** (main) + **code-writer** (субагент), tools allow/deny;
- Telegram-канал, все `customCommands`, per-user сессии;
- все скиллы из `skills/` (auto-discovery OpenClaw — настройка не нужна).

## Архитектура деплоя

```
GitHub push → deploy branch
        ↓
GitHub Actions (deploy.yml)  ── echo <sha> ──┐
        ↓ SSH (ForceCommand → ssh-deploy-wrapper.sh)
Server: ssh-deploy-wrapper.sh  (вытаскивает только 40-hex SHA)
        ↓ sudo (одна разрешённая команда)
run-deploy.sh  (root)
        ↓
  [backup users/+config] → [git reset --hard] → [fix perms]
        → [sync openclaw.json + unit] → [restart] → [health check]
        ↓ fail
  [auto rollback кода и конфига к прошлому коммиту]
```

## Требования к серверу

- Ubuntu 22.04 LTS / Debian 12+
- Node.js ≥ 18 (ставит setup-скрипт)
- Пользователь для деплоя (например `ubuntu`) с SSH-доступом
- RAM: ~1 ГБ для бота + **~6–8 ГБ** для локальной 7b-модели Ollama
  (или `llama3.2:3b` / `INSTALL_OLLAMA=0` на маленьком VPS)

## Первичная настройка сервера (один раз)

```bash
# Клонировать репозиторий
git clone -b deploy https://github.com/margoshkagt-star/Golden-Hour.git /opt/golden-hour
cd /opt/golden-hour

# Запустить setup (от root). Ставит OpenClaw, Ollama, конфиг, сервис, firewall.
sudo bash deploy/setup-server.sh

# Переопределить параметры при необходимости:
# SSH_PORT=47822 DEPLOY_SUDO_USER=ubuntu \
# OLLAMA_FALLBACK_MODEL=llama3.2:3b INSTALL_OLLAMA=1 \
#   sudo bash deploy/setup-server.sh
```

После setup:
1. Заполнить `/opt/golden-hour/.env` — `MINIMAX_API_KEY` и `TELEGRAM_BOT_TOKEN`
   (`OPENCLAW_GATEWAY_TOKEN` генерируется автоматически).
2. Добавить deploy-ключ с `ForceCommand` в `~ubuntu/.ssh/authorized_keys` (инструкции выведет setup).
3. `sudo systemctl start golden-hour`
4. Проверить: `openclaw doctor`, `ollama list`, `journalctl -u golden-hour -f`.

## Ключ деплоя (обязательно — ForceCommand)

Сгенерировать отдельный ключ только для деплоя:
```bash
ssh-keygen -t ed25519 -C "deploy@golden-hour" -f ~/.ssh/golden_hour_deploy
```

В `~/.ssh/authorized_keys` на сервере добавить с ForceCommand (указывает на **обёртку**):
```
command="/opt/golden-hour/deploy/ssh-deploy-wrapper.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA... deploy@golden-hour
```

Модель привилегий (defense-in-depth):
- ключ деплоя может вызвать **только** `ssh-deploy-wrapper.sh` (ForceCommand);
- обёртка извлекает из запроса **только** 40-hex SHA, игнорируя всё остальное;
- обёртка вызывает `run-deploy.sh` через `sudo` — единственная разрешённая в sudoers команда;
- оба скрипта `root:root`, `chmod 555` — deploy-пользователь не может их изменить.

Итог: даже при компрометации GitHub Actions или ключа на сервере нельзя выполнить
произвольную команду — только задеплоить коммит из `origin/deploy`.

> **Рекомендация по безопасности.** `DEPLOY_SUDO_USER` (по умолчанию `ubuntu`) —
> это обычный интерактивный аккаунт с sudo. Для строгой изоляции заведите
> отдельного пользователя только под деплой:
> `DEPLOY_SUDO_USER=ghdeploy sudo bash deploy/setup-server.sh`. Тогда NOPASSWD-правило
> на `run-deploy.sh` и ForceCommand-ключ привязаны к аккаунту без интерактивного входа,
> и компрометация `ubuntu` не даёт доступа к деплою (и наоборот).

## GitHub Secrets (Settings → Secrets and Variables → Actions)

| Secret | Описание |
|--------|----------|
| `SERVER_HOST` | IP или hostname сервера |
| `SERVER_USER` | SSH-пользователь (например, `ubuntu`) |
| `SSH_PRIVATE_KEY` | Приватный deploy-ключ (см. выше) |
| `SSH_PORT` | SSH-порт сервера *(default: `47822`)* |

## Модели

| Роль | Модель | Провайдер | Ключ |
|------|--------|-----------|------|
| primary | `MiniMax-M3` | MiniMax (`api.minimax.io/anthropic`) | `MINIMAX_API_KEY` |
| fallback | `qwen2.5:7b-instruct` | локальный Ollama (`127.0.0.1:11434`) | — |

Fallback срабатывает **только** при сбое MiniMax. Конфиг моделей —
[`deploy/openclaw.config.json5`](openclaw.config.json5) (`models.providers`).

### Локальная модель (Ollama)
- Ставится и тянется в `setup-server.sh` при `INSTALL_OLLAMA=1` (по умолчанию).
- Сменить модель: `OLLAMA_FALLBACK_MODEL=...` при setup **и** правка id в
  `openclaw.config.json5` (`models.providers.ollama.models[].id`).
- Маленький VPS: `llama3.2:3b` (~2 ГБ) или `INSTALL_OLLAMA=0` (тогда fallback
  недоступен, пока Ollama не поднимут вручную).
- Ollama — отдельный сервис; лимит `MemoryMax=512M` бота его не ограничивает.

## Субагенты

| Агент | Роль | Tools |
|-------|------|-------|
| `golden-hour` | main: диалог, планирование, запуск своих node-скриптов, файлы пользователей | read/write/edit/exec/process, message, cron, sessions_*, goals; **deny** media-gen |
| `code-writer` | изолированная генерация кода (по скиллу `coder`) | read/write/edit/apply_patch/exec/process; **deny** message/cron/sessions/goals |

**Добавить новый субагент:** объект в `agents.list` + его `id` в
`golden-hour.subagents.allowAgents` (скелет-комментарий есть в конфиге).

> Примечание: в отличие от дженерик-доки `skills/coder/architecture.md`, main
> **сохраняет** `exec/write` — бот сам запускает `daily-plan.mjs` и пишет
> `profile.md`/`tasks.yaml`. Делегация кода — на уровне скилла + AGENTS.md.

## Порты

| Порт | Назначение | Переопределение |
|------|-----------|-----------------|
| `47822` | SSH сервера | Секрет `SSH_PORT` |
| `47854` | Gateway control-plane (только loopback, наружу не публикуется) | `.env`: `OPENCLAW_GATEWAY_PORT` |
| `47832` | Внутренний порт приложения / health-check | `.env`: `APP_PORT` |
| `47843` | Webhook-порт (нужен только в webhook-режиме; дефолт — long-poll) | `.env`: `WEBHOOK_PORT` |

Telegram работает в режиме long-poll (исходящие соединения), поэтому в UFW
открыт **только** SSH-порт. Gateway слушает loopback и доступен лишь через
SSH-туннель (`ssh -N -L 47854:127.0.0.1:47854 ...`).

## Обязательные переменные `.env`

| Переменная | Назначение |
|------------|-----------|
| `MINIMAX_API_KEY` | ключ primary-модели *(обязательно)* |
| `TELEGRAM_BOT_TOKEN` | токен бота *(обязательно)* |
| `OPENCLAW_GATEWAY_TOKEN` | токен control-plane *(генерируется автоматически)* |
| `OLLAMA_FALLBACK_MODEL` | id локальной модели |
| `OPENCLAW_GATEWAY_PORT` / `OPENCLAW_GATEWAY_BIND` | порт/бинд gateway |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google Calendar *(опц.)* |

## Защита пользовательских данных при деплое

```
/opt/golden-hour/
  users/           ← git-ignored, НИКОГДА не трогается git reset
  data/teams/      ← git-ignored, НИКОГДА не трогается git reset
  memory/          ← git-ignored, НИКОГДА не трогается git reset
  .env             ← git-ignored, chmod 600, owner golden-hour
```

`run-deploy.sh` перед каждым деплоем:
1. Создаёт `tar.gz`-бэкап в `/var/backups/golden-hour/` (последние 10)
2. Использует `git reset --hard` только для tracked-файлов (untracked не трогает)
3. **Никогда** не запускает `git clean`

## Graceful shutdown (защита от порченых файлов)

`golden-hour.service` имеет `TimeoutStopSec=30s` — systemd отправляет SIGTERM и ждёт 30 секунд перед SIGKILL.

**Приложение обязано** использовать атомарные записи:
```js
// НЕ делать:
await fs.writeFile(targetPath, data)

// Делать (атомарная запись — rename() атомарен на одной ФС):
const tmp = targetPath + '.tmp'
await fs.writeFile(tmp, data)
await fs.rename(tmp, targetPath)
```

## Откат

**Автоматически** — если health check после деплоя не прошёл, `run-deploy.sh` сам откатывается к предыдущему коммиту.

**Вручную:**
```bash
# На сервере
cd /opt/golden-hour
git log --oneline -5
git reset --hard <PREV_COMMIT>
sudo systemctl restart golden-hour
```

**Из бэкапа пользовательских данных:**
```bash
tar -xzf /var/backups/golden-hour/users-YYYYMMDD-HHMMSS.tar.gz \
  -C /opt/golden-hour
sudo systemctl restart golden-hour
```

## Мониторинг

```bash
# Статус сервиса
sudo systemctl status golden-hour

# Логи в реальном времени
sudo journalctl -u golden-hour -f

# Количество перезапусков (признак crash loop)
sudo systemctl show golden-hour --property=NRestarts

# Ресурсы
systemd-cgtop
```

## Многопользовательская работа

Бот обслуживает несколько пользователей через один процесс. Критично:

- Каждый пользователь изолирован в `users/tg-<id>/` — другие пользователи не имеют доступа
- Конкурентные записи в файлы **должны** использовать advisory lock или per-user очередь (см. C-3 в review)
- Ограничение памяти: `MemoryMax=512M`, `MemoryHigh=400M` (мягкий лимит с throttling)
- Лимит тасков: `TasksMax=256` (Node.js использует несколько потоков)
