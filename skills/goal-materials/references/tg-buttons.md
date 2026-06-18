# Telegram inline buttons

## Формат inline_keyboard

Telegram ожидает массив массивов кнопок:
```json
{"text": "Текст", "callback_data": "mat:..."}
```

Максимум 8 кнопок в ряду, лучше группировать по 2–3 в ряд.

## Наборы кнопок

### `pick` (выдача материала)
```
[[{"text":"✅ Разобрала","callback_data":"mat:status:<id>:understood"},
  {"text":"❌ Не поняла","callback_data":"mat:status:<id>:stuck"},
  {"text":"⏭ Пропустить","callback_data":"mat:status:<id>:archived"}]]
```

### `list` (у каждого материала)
```
[[{"text":"Открыть","callback_data":"mat:show:<id>"},
  {"text":"В работу","callback_data":"mat:status:<id>:working"},
  {"text":"🗑 В архив","callback_data":"mat:status:<id>:archived"}]]
```

### `add` (после подтверждения)
```
[[{"text":"Открыть","callback_data":"mat:show:<id>"},
  {"text":"Добавить ещё","callback_data":"mat:add:continue"}]]
```

### `search` (у найденных)
```
[[{"text":"Открыть","callback_data":"mat:show:<id>"},
  {"text":"В работу","callback_data":"mat:status:<id>:working"}]]
```

## Формат callback_data

```
mat:<action>:<id>[:<value>]
```

- `action` ∈ `status` | `show` | `add`
- `id` = `m_<8chars>`
- `value` = новый статус (только для `status`)

Примеры:
- `mat:status:m_8a1f2c3d:understood`
- `mat:status:m_b7e4d2a1:stuck`
- `mat:show:m_3c9f1e5b`
- `mat:add:continue`

## Обработка callback

Callback приходит в агента как входящее сообщение с полем `callback_data`. Агент:

1. Парсит `mat:<action>:<id>[:<value>]` (regex: `^mat:(\w+):([\w_]+)(?::(\w+))?$`)
2. Выполняет действие:
   - `status` → изменить статус, обновить `index.json` + `status_history` + строка в `users/<user_key>/progress.md`
   - `show` → отправить содержимое файла (без кнопок)
   - `add:continue` → предложить прислать следующий
3. Отвечает:
   - Для `status`/`show` — отредактировать исходное сообщение, убрав кнопки, добавив короткий confirm ("✅ Засчитано" / "📖 Открываю...")
   - Для `add:continue` — короткое сообщение "Присылай следующий материал"

Telegram ограничивает callback_data до 64 байт — наши `mat:status:m_xxxxxxxx:understood` (~32 байта) укладываются.