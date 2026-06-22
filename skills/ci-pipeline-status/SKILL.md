---
name: "ci-pipeline-status"
description: "Показывает статус CI-пайплайна (GitHub Actions / GitLab CI) для текущего репо с диагностикой флакающих тестов"
---

<!-- source: ts=2026-06-16T18:00:00 user_id=2 -->

<!-- source: ts=2026-06-16T18:00:00+03:00 user_id=2 -->
# ci-pipeline-status

## Цель
По запросу пользователя показывает текущий статус CI-пайплайна (последние 5 запусков) для указанного репо + краткую диагностику флакающих тестов (если есть).

## Триггер
- **Вручную:** «проверь CI», «статус пайплайна», «как там тесты?».

## Логика
1. Прочитать `origin` репо (через `git remote get-url origin`) — определить GitHub/GitLab.
2. Если GitHub:
   ```bash
   curl -s -H "Authorization: token $GITHUB_TOKEN" \
        "https://api.github.com/repos/<owner>/<repo>/actions/runs?per_page=5"
   ```
3. Если GitLab:
   ```bash
   curl -s -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
        "https://gitlab.com/api/v4/projects/<id>/pipelines?per_page=5"
   ```
4. Распарсить JSON, вывести:
   ```
   🔧 CI Pipeline: <repo>
   • run #<id> — <status> — <branch> — <duration> — <commit_msg>
   ...
   ✅ Все зелёные / ❌ N красных
   ```
5. **Если есть failed run** — скачать логи (`curl .../logs` для GitHub) → найти повторяющиеся имена тестов → пометить как «флакающие» (если тот же тест failed в 2+ последних запусках).
6. Сохранить статус в `memory/ci-status-<repo>-<date>.md` для истории.

## Вход / Выход
- **Вход:** имя репо (или cwd).
- **Выход:** plain-text отчёт + лог-файл (если были failures).

## Примеры
### Пример 1
**Запрос:** «проверь CI для Golden-Hour»
**Результат:**
```
🔧 CI Pipeline: margoshkagt-star/Golden-Hour
• run #1234 — success — main — 2m 14s — "fix: ..."
• run #1233 — success — main — 1m 58s — "docs: ..."
• run #1232 — failure — main — 3m 02s — "wip: ..."
⚠️ 1 флакающий тест: tests/test_weather.py::test_get_forecast
```

## Что НЕ делает
- ❌ Не запускает CI сам (только показывает статус).
- ❌ Не делает re-run упавших jobs (только подсказывает).
- ❌ Не редактирует workflow-файлы.
- ❌ Не работает с self-hosted runners (только cloud).

## Зависимости
- skills: `note-to-file`
- tools: `exec` (curl), `read`
- внешние: GitHub API / GitLab API (нужен token в env: `GITHUB_TOKEN` / `GITLAB_TOKEN`)
- данные: `memory/ci-status-*.md`
