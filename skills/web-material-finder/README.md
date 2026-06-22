# web-material-finder

Паттерн саб-агента для поиска и генерации учебных материалов. Используется в связке со скиллом [`goal-materials`](../goal-materials/).

## 5 режимов

| Режим | Иконка | Когда | Инструмент |
|---|---|---|---|
| `topic` | 🔍 | Поиск по теме словами | web |
| `source` | 🔗 | Поиск вокруг URL/файла | web |
| `file` | 📄 | Поиск внутри PDF/DOCX/PPTX | python-парсеры |
| `image` | 🎨 | AI-генерация картинки | image_generate |
| `draw` | 📐 | Точные чертежи/графики | matplotlib/graphviz/schemdraw/tikz |

## Зачем нужен

Вместо `inline web_search` (5-30 сек, бот висит) — саб-агент через `sessions_spawn(mode="run")`:
- Бот сразу отвечает placeholder-ом
- Саб-агент работает в фоне
- Результат приходит пушем
- Бот редактирует сообщение на результат с inline-кнопками

## Установка

Скопировать в `<workspace>/skills/web-material-finder/`. Скилл автоматически подхватится OpenClaw.

## Использование

См. `SKILL.md` — там полный TASK_PROMPT, шаблоны Python-скриптов, формат JSON-ответа.

Краткий пример:
```python
sessions_spawn(
  task = TASK_PROMPT,
  taskName = f"matfind_{goal}_{slug}_{ts}",
  mode = "run",
  context = "isolated",
  toolsAllow = ["web_search", "web_fetch", "read_file", "exec", "write", "image_generate"]
)
```

## Зависимости

```bash
pip install PyPDF2 python-docx python-pptx matplotlib
# опционально:
pip install graphviz schemdraw
# + системный graphviz
```

## Известные ограничения

- **AI image gen** (`mode: image`) ломает текст в картинках — для чертежей с подписями используй `mode: draw` (matplotlib)
- **PDF сканы** без текстового слоя не парсятся
- `openai/gpt-image-2` не сконфигурирован по умолчанию (нужен `OPENAI_API_KEY`); используется `minimax/image-01`

## Примеры

См. `examples/`:
- `cube.py` — 3D куб с диагональю и углом α
- `pptx_create.py` — создание тестового PPTX
- `pptx_parse.py` — парсинг PPTX

## Лицензия

MIT
