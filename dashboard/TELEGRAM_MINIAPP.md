# Telegram Mini App — полная инструкция

Мобильная версия **Фельпик Dashboard** для открытия **внутри Telegram** (телефон и десктоп): Kanban, календарь, создание задач.

Репозиторий агента: [Golden-Hour](https://github.com/margoshkagt-star/Golden-Hour).

---

## Содержание

1. [Что нужно заранее](#1-что-нужно-заранее)
2. [Файлы в репозитории](#2-файлы-в-репозитории)
3. [Создать бота в Telegram](#3-создать-бота-в-telegram)
4. [Настроить токен](#4-настроить-токен)
5. [Локальный preview (без Telegram)](#5-локальный-preview-без-telegram)
6. [HTTPS для Telegram](#6-https-для-telegram)
7. [Привязать Mini App к боту](#7-привязать-mini-app-к-боту)
8. [Проверка](#8-проверка)
9. [API backend](#9-api-backend)
10. [Продакшен (VPS)](#10-продакшен-vps)
11. [Устранение неполадок](#11-устранение-неполадок)

---

## 1. Что нужно заранее

| Требование | Зачем |
|------------|--------|
| **Python 3.10+** | `backend.py` |
| **OpenClaw** + gateway `:18789` | задачи, snapshot, task-pool |
| **Telegram-бот** | Mini App открывается только из бота |
| **Публичный HTTPS URL** | Telegram не открывает `http://127.0.0.1` внутри приложения |
| **cloudflared** (для dev) или VPS + nginx | туннель или постоянный домен |

Mini App **не требует** отдельного домена в BotFather как «Web App» — достаточно **Menu Button** с URL `https://…/miniapp`.

---

## 2. Файлы в репозитории

Все файлы лежат в папке `dashboard/`:

| Файл | Назначение |
|------|------------|
| `TELEGRAM_MINIAPP.md` | Эта инструкция |
| `telegram-miniapp.env.example` | Шаблон переменных для `.env` |
| `telegram-miniapp.js` | SDK Telegram WebApp, тема, нижняя навигация, auth |
| `telegram-miniapp.css` | Мобильная вёрстка (класс `html.tg-miniapp`) |
| `setup_telegram_miniapp.ps1` | **Главный скрипт**: dashboard + туннель + menu button |
| `set_telegram_menu_button.ps1` | Только обновить кнопку меню (URL уже известен) |
| `start_dashboard.ps1` | Запуск backend (`-Lan` для туннеля) |
| `backend.py` | Роуты `/miniapp`, `/api/telegram/*`, раздача JS/CSS |
| `dashboard.html` | Подключает miniapp-режим (`?miniapp=1`, `tg-miniapp`) |

### Маршруты backend

| URL | Описание |
|-----|----------|
| `GET /miniapp` | Dashboard в режиме Telegram (инжект `tg-miniapp`) |
| `GET /dashboard.html?miniapp=1` | То же через query-параметр |
| `GET /telegram-miniapp.js` | Скрипт miniapp |
| `GET /telegram-miniapp.css` | Стили miniapp |
| `GET /api/telegram/config` | `{ hasBotToken, publicUrl, miniappPath }` |
| `POST /api/telegram/auth` | Проверка `initData` от Telegram WebApp |

---

## 3. Создать бота в Telegram

1. Откройте [@BotFather](https://t.me/BotFather).
2. `/newbot` → имя и username (например `GoldenHourBot`).
3. Сохраните **токен** вида `123456789:AAH…` — он понадобится в `.env`.
4. (Опционально) `/setdescription`, `/setabouttext` — описание для пользователей.

**Mini App через Menu Button** (рекомендуется):

- BotFather → ваш бот → **Bot Settings** → **Menu Button** → **Configure**
- Или команда `/setmenubutton`
- URL задаётся скриптом `setup_telegram_miniapp.ps1` автоматически

**Не путать** с inline-кнопкой `web_app` в сообщении — для постоянного доступа используйте **кнопку меню** слева от поля ввода.

---

## 4. Настроить токен

Скопируйте шаблон:

```powershell
cd dashboard
copy telegram-miniapp.env.example $env:USERPROFILE\.openclaw\.env
# Отредактируйте .env — вставьте TELEGRAM_BOT_TOKEN
```

Минимум в `%USERPROFILE%\.openclaw\.env`:

```env
TELEGRAM_BOT_TOKEN=ваш_токен_от_BotFather
```

Опционально:

```env
TELEGRAM_MINIAPP_URL=https://xxxx.trycloudflare.com
TELEGRAM_MINIAPP_MENU_TEXT=📋 Задачи
```

Переменная `OPENCLAW_HOME` переопределяет путь к `.env` (по умолчанию `%USERPROFILE%\.openclaw`).

---

## 5. Локальный preview (без Telegram)

Только для разработки UI в браузере:

```powershell
cd dashboard
.\start_dashboard.ps1
```

Откройте: **http://127.0.0.1:18790/miniapp**

В браузере SDK Telegram не загрузится полностью — нижняя навигация и вёрстка всё равно работают.

---

## 6. HTTPS для Telegram

Telegram открывает Mini App **только по HTTPS** с валидным сертификатом.

### Вариант A — Cloudflare Quick Tunnel (разработка)

```powershell
winget install Cloudflare.cloudflared
```

Запуск вручную:

```powershell
cloudflared tunnel --url http://127.0.0.1:18790
```

В логе появится URL вида `https://random-name.trycloudflare.com`.

### Вариант B — свой домен + nginx + Let's Encrypt

См. [раздел 10](#10-продакшен-vps).

---

## 7. Привязать Mini App к боту

### Автоматически (рекомендуется)

```powershell
cd dashboard
.\setup_telegram_miniapp.ps1
```

Скрипт:

1. Запускает dashboard на `0.0.0.0:18790` (`start_dashboard.ps1 -Lan`)
2. Поднимает **cloudflared** (если установлен)
3. Вызывает Telegram API `setChatMenuButton` с URL `https://…/miniapp`

Если туннель уже есть:

```powershell
.\setup_telegram_miniapp.ps1 -PublicUrl "https://xxxx.trycloudflare.com" -SkipTunnel
```

Только обновить кнопку меню:

```powershell
.\set_telegram_menu_button.ps1 -PublicUrl "https://xxxx.trycloudflare.com"
```

Параметры:

| Параметр | Описание |
|----------|----------|
| `-Port` | Порт dashboard (по умолчанию 18790) |
| `-PublicUrl` | Готовый HTTPS URL без `/miniapp` |
| `-BotToken` | Токен (иначе из `.env`) |
| `-MenuText` | Текст кнопки меню |
| `-SkipTunnel` | Не запускать cloudflared |
| `-SkipMenu` | Не трогать menu button |

### Вручную через BotFather

1. Узнайте публичный URL, например `https://xxxx.trycloudflare.com`
2. Mini App URL: **`https://xxxx.trycloudflare.com/miniapp`**
3. BotFather → Menu Button → вставьте этот URL

### Вручную через API

```http
POST https://api.telegram.org/bot<TOKEN>/setChatMenuButton
Content-Type: application/json

{
  "menu_button": {
    "type": "web_app",
    "text": "📋 Задачи",
    "web_app": { "url": "https://xxxx.trycloudflare.com/miniapp" }
  }
}
```

---

## 8. Проверка

1. **Backend**: http://127.0.0.1:18790/api/telegram/config → `"hasBotToken": true`
2. **Mini App URL** в браузере по HTTPS: страница Kanban/календарь
3. **Telegram**: откройте чат с ботом → кнопка меню слева от поля ввода → Mini App
4. Задачи синхронизируются с `memory/task-pool/active.json` OpenClaw

### Что доступно в Mini App

- Kanban (список и колонки)
- Календарь (день / неделя / месяц)
- Нижняя навигация: Задачи · Календарь · Новая задача
- Тема следует за Telegram (светлая/тёмная)

### Что скрыто в Mini App

- Чат с gateway (нужен публичный `wss://` gateway)
- Grafana, topology, inbox — только в полном дашборде

### Режим панели

Mini App **не разворачивается на весь экран** (`expand()` не вызывается). Если открылось на весь экран — закройте и откройте снова через **Menu Button**, не через inline-кнопку в чате.

---

## 9. API backend

### `GET /api/telegram/config`

```json
{
  "hasBotToken": true,
  "publicUrl": "https://xxxx.trycloudflare.com",
  "miniappPath": "/miniapp",
  "dashboardPath": "/dashboard.html?miniapp=1"
}
```

### `POST /api/telegram/auth`

Тело: `{ "initData": "<строка из Telegram.WebApp.initData>" }`

При валидном токене бота backend проверяет HMAC (алгоритм Telegram WebApp) и возвращает:

```json
{ "ok": true, "user": { "id": 123, "first_name": "..." }, "telegram_id": 123 }
```

Без токена auth пропускается (локальная разработка).

---

## 10. Продакшен (VPS)

1. Разверните dashboard на сервере (`python backend.py --host 0.0.0.0 --port 18790`).
2. Nginx reverse proxy + Let's Encrypt:

```nginx
server {
    listen 443 ssl;
    server_name dash.example.com;
    ssl_certificate     /etc/letsencrypt/live/dash.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dash.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:18790;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

3. В `.env`: `TELEGRAM_MINIAPP_URL=https://dash.example.com`
4. `.\set_telegram_menu_button.ps1 -PublicUrl "https://dash.example.com"`

Для trycloudflare URL **меняется при каждом перезапуске** туннеля — для продакшена нужен постоянный домен.

---

## 11. Устранение неполадок

| Проблема | Решение |
|----------|---------|
| Кнопка меню не появилась | Проверьте токен в `.env`, запустите `set_telegram_menu_button.ps1` |
| «Failed to load» в Telegram | URL должен быть HTTPS; dashboard слушает `0.0.0.0` (`-Lan`) |
| Пустой Kanban | Запущен ли gateway OpenClaw? Есть ли `task-pool/active.json`? |
| `hasBotToken: false` | Добавьте `TELEGRAM_BOT_TOKEN` в `.env`, перезапустите backend |
| trycloudflare не стартует | `winget install Cloudflare.cloudflared`, смотрите `cloudflared-miniapp.err.log` |
| Mini App на весь экран | Открывайте через Menu Button, не inline web_app |
| Задачи не сохраняются | Backend должен писать в workspace OpenClaw; проверьте права на `memory/task-pool/` |

Логи:

- `dashboard/backend.out.log`, `backend.err.log`
- `dashboard/cloudflared-miniapp.log`, `cloudflared-miniapp.err.log`

---

## Быстрая шпаргалка

```powershell
# 1. Токен в .env
# 2. Всё в одном:
cd dashboard
.\setup_telegram_miniapp.ps1

# 3. В Telegram: чат с ботом → кнопка меню → Mini App
```

Связь с Golden Hour: бот ведёт тайм-менеджмент в Telegram, Mini App даёт визуальный Kanban и календарь поверх task-pool OpenClaw.
