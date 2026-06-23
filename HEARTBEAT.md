# Heartbeat — периодические проверки

## Soul Guardian
- Выполни: `python skills/soul-guardian/scripts/soul_guardian.py check --actor heartbeat --output-format alert`
- Если есть вывод — это security alert: сообщи владельцу воркспейса (не в Telegram пользователям бота), кратко что изменилось
- `SOUL.md` и `AGENTS.md` при drift восстанавливаются автоматически (mode: restore)

## ClawSec Advisory (лёгкая проверка)
- Прочитай `skills/clawsec-suite/HEARTBEAT.md` и выполни проверку advisory feed, если прошло >6ч с прошлой проверки
- При совпадении установленных скиллов с advisory — уведомить владельца, удаление только с явного одобрения

## Pomodoro tick
- Выполни: `node scripts/pomodoro-tick.mjs`
- Если в JSON есть `results` с `notifications` — отправь соответствующим пользователям `message` + `buttons` из каждого уведомления
