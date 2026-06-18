# Notification templates

All messages in Russian, friendly, short. Use TG Markdown (`*bold*`, `_italic_`, `` `code` ``). Tone: тёплый, неформальный, как солнце-помощник, не как корпоративный бот.

## Morning brief

```
Доброе утро! 🌅

Сегодня {N} целей в работе:

1. *{goal_title}* (вес {weight}/5)
   {task_count} задач, первая — в {first_task_time}

2. *{goal_title_2}* (вес {weight_2}/5)
   ...

Главная по весу — *{top_goal_title}*. Начнём с неё?
```

## Task ping (kickoff + status check)

```
Пора за *{goal_title}* 🌅
{task_title}
≈{est_minutes} мин

Как настрой, начинаем?
```

Inline buttons: `[Начинаю] [Отложить 30м] [Пропустить]`

## Evening check-in

```
Как прошёл день? 🌅

{completed_count}/{total_count} задач сделано.

{goals_summary}

Что удалось, что застряло?
```

## Snooze confirmation

```
Ок, отложил *{task_title}* на {new_time}. Пингану ещё раз.
```

## Done confirmation

```
🎉 Засчитал: *{task_title}*.
{next_task_suggestion}
```

## Skip confirmation

```
Принял, пропускаем *{task_title}*. Вернёмся к нему завтра в обзоре.
```

## Quiet-hours fallback (if a ping got shifted)

```
{original_message}

(таймшифт — сейчас {new_time}, попали в тихие часы)
```
