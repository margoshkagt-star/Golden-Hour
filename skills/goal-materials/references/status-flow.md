# Status flow

```
       ┌──────┐
       │ new  │
       └──┬───┘
          │ (pick или status working)
          ▼
       ┌──────┐        ┌───────────┐
       │working│───────▶│ understood│
       └──┬───┘        └─────┬─────┘
          │                  │
          │                  │ (status archived)
          │                  ▼
          │              ┌──────────┐
          │              │ archived │
          │              └──────────┘
          ▼
       ┌──────┐
       │ stuck │
       └──┬───┘
          │ (вернулся разбирать)
          ▼
       (обратно в working или в understood)
```

Допустимые переходы:
- `new` → `working`
- `working` → `understood` | `stuck`
- `stuck` → `working` | `understood`
- `understood` → `archived`

Каждый переход пишется в `status_history`. Переходы в `understood` / `stuck` / `archived` дополнительно пишут строку в `users/<user_key>/progress.md`.