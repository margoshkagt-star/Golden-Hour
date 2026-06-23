# team-tasks — message templates

Short Telegram messages. Agent sends to each entry in `notifications.recipients`.

## team_created

```
👥 Команда «{goal}» создана. Owner: {username}.
```

## member_joined

```
➕ {username} вступил(а) в команду «{goal}».
```

## member_left

```
➖ {username} вышел(а) из команды «{goal}».
{auto_submitted_tasks? «Таски на проверке: {ids}» : ""}
```

## task_added

```
📋 Новая таска: «{title}» (команда «{goal}»).
```

## task_taken

```
🔧 {assignee} взял(а): «{title}».
```

## task_submitted

```
📤 «{title}» сдана на проверку. Owner — подтвердите.
```

## task_approved

```
✅ «{title}» принята!
```

## overdue digest (cron / on list)

```
⏰ Просрочено в «{goal}»: {task titles joined by «, »}.
```
