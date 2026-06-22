---
name: "pokazyvat-prognoz-pogody"
description: "Показывает прогноз погоды на день в утреннем брифе golden-hour (через wttr.in)"
---

<!-- source: ts=2026-06-17T16:48:17+03:00 user_id=1038917447 -->

# pokazyvat-prognoz-pogody

## Цель
Добавить в `goal-checkin-notifier` утренний блок с погодой: текущая температура, «feels like», осадки, ветер — на день. Источник: `wttr.in` (бесплатный, без API-ключа, до 1M запросов/день).

## Триггер
- **Авто:** срабатывает из `daily-plan` / `goal-checkin-notifier` при генерации утреннего брифа (`morning_brief`) в `users/<user_key>/plans/YYYY-MM-DD.json`.
- **Вручную:** команда «погода сегодня» / «прогноз на завтра» в golden-hour сессии.

## Логика
1. **Получить координаты пользователя** из `users/<user_key>/profile.md` → поле `location` (формат: `city, country` или `lat,lon`). Если поля нет — fallback на `Moscow` + предупреждение.
2. **Запрос к wttr.in:**
   ```bash
   curl -s "wttr.in/<location>?format=j1&lang=ru"
   ```
   `j1` = JSON-формат, `lang=ru` = русский. Таймаут 5 сек.
3. **Парсинг JSON:** из ответа берём `data.current_condition[0]` (текущая погода) + `data.weather[0]` (сегодня: max/min temp, осадки, ветер).
4. **Форматирование строки:**
   ```
   🌤 Погода в <location>:
   • Сейчас: <temp_C>°C (ощущается <FeelsLikeC>°C), <weatherDesc>
   • Сегодня: max <maxtempC>° / min <mintempC>°, осадки <chanceofrain>%, ветер <windspeedKmph> км/ч
   ```
5. **Вставка в `morning_brief`** (JSON) — поле `weather_block` рядом с `tasks` / `goals`.
6. **Кэш:** сохранять последний прогноз в `users/<user_key>/.cache/weather_<date>.json` (1 день, чтобы не дёргать API каждые 5 мин).

## Вход / Выход
- **Вход:** `user_key`, текущая дата, `location` (из профиля).
- **Выход:** строка-блок для `morning_brief.weather_block` + кэш-файл.

## Примеры
### Пример 1 (Москва, утро буднего дня)
**Запрос:** (авто) goal-checkin-notifier генерит morning_brief для user_key=tg-1038917447
**Результат:** в JSON появляется
```json
"weather_block": "🌤 Погода в Moscow:\n• Сейчас: 12°C (ощущается 10°C), Облачно\n• Сегодня: max 15° / min 8°, осадки 20%, ветер 12 км/ч"
```

## Что НЕ делает
- ❌ Не делает прогноз на несколько дней (только сегодня).
- ❌ Не использует API-ключ (только публичный wttr.in).
- ❌ Не хранит историю погоды.
- ❌ Не шлёт уведомления сам (только встраивается в morning_brief).

## Зависимости
- skills: `goal-checkin-notifier`, `daily-plan`, `user-profile`
- tools: `exec` (curl)
- внешние: `wttr.in` (бесплатный, без ключа)
- данные: `users/<user_key>/profile.md:location` (если нет — fallback Moscow)
