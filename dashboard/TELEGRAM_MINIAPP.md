# Telegram Mini App — Фельпик Dashboard

Мобильная версия дашборда для открытия **внутри Telegram** (телефон и десктоп).

## Что доступно в Mini App

- **Kanban** — задачи, фильтры, drag-and-drop
- **Календарь** — день / неделя / месяц
- Нижняя навигация: Задачи · Календарь · Новая задача
- Синхронизация цветов с темой Telegram

Чат, Grafana и topology в mini-режиме скрыты (нужен полный дашборд в браузере).

## Быстрый старт

### 1. Локальный preview (без Telegram)

```powershell
cd C:\Users\Admin\.openclaw\workspace\dashboard
.\start_dashboard.ps1
```

Откройте: http://127.0.0.1:18790/miniapp

### 2. Telegram (нужен HTTPS)

Telegram открывает Mini App только по **публичному HTTPS URL**.

```powershell
cd C:\Users\Admin\.openclaw\workspace\dashboard
.\setup_telegram_miniapp.ps1
```

Скрипт:
1. Запускает dashboard на `0.0.0.0:18790`
2. Поднимает **Cloudflare Tunnel** (если установлен `cloudflared`)
3. Регистрирует кнопку меню бота (`setChatMenuButton`)

Или вручную с своим URL:

```powershell
.\setup_telegram_miniapp.ps1 -PublicUrl "https://xxxx.trycloudflare.com" -SkipTunnel
```

### 3. BotFather

В [@BotFather](https://t.me/BotFather):

1. Выберите бота (например Golden Hour)
2. **Bot Settings → Menu Button → Configure**
3. URL: `https://ВАШ-ДОМЕН/miniapp`

Либо: `/setmenubutton` → URL mini app

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `TELEGRAM_BOT_TOKEN` | Токен бота для проверки `initData` |
| `TELEGRAM_MINIAPP_BOT_TOKEN` | Отдельный токен (если нужен другой бот) |
| `TELEGRAM_MINIAPP_URL` | Публичный URL (информационно) |
| `TELEGRAM_MINIAPP_MENU_TEXT` | Текст кнопки меню (по умолчанию: 📋 Задачи) |

Токен читается из `C:\Users\Admin\.openclaw\.env`.

## API

| Маршрут | Описание |
|---------|----------|
| `GET /miniapp` | Dashboard в режиме Telegram |
| `GET /api/telegram/config` | Статус конфигурации |
| `POST /api/telegram/auth` | Проверка `initData` от Telegram WebApp |

## Файлы

| Файл | Роль |
|------|------|
| `telegram-miniapp.js` | SDK, тема, нижняя навигация |
| `telegram-miniapp.css` | Мобильная вёрстка |
| `setup_telegram_miniapp.ps1` | Туннель + menu button |
| `set_telegram_menu_button.ps1` | Только переименовать кнопку меню |

## Режим отображения

Mini App открывается в **компактной панели** (не на весь экран): в коде не вызывается `expand()` и `requestFullscreen()`.

Если панель всё ещё на весь экран — полностью закройте miniapp и откройте снова через кнопку меню слева от поля ввода (не через inline-кнопки в чате).

## Ограничения

- **HTTPS обязателен** для Telegram (локальный `http://127.0.0.1` только для разработки в браузере)
- Чат с gateway из Mini App не работает без публичного `wss://` gateway
- Для продакшена лучше VPS + nginx + Let's Encrypt вместо trycloudflare

## Связь с Golden Hour

Репозиторий [Golden-Hour](https://github.com/margoshkagt-star/Golden-Hour) — агент тайм-менеджмента в Telegram. Mini App дополняет бота визуальным Kanban/календарём поверх task-pool OpenClaw.
