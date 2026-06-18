# status

```bash
> materials status m_a1b2c3d4 understood
# status → understood
# + строка в users/<user_key>/progress.md

> materials status m_a1b2c3d4 stuck
# status → stuck
# + строка в users/<user_key>/progress.md

> materials history m_a1b2c3d4
# история статусов

# callback (из кнопки)
> [callback_data: mat:status:m_8a1f2c3d:understood]
# → эффект как у status understood
# → confirm: "✅ Засчитано"
# → редактирует исходное сообщение, убирает кнопки
```