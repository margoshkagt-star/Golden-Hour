# add

```bash
# явная цель
> materials add --type problem --goal g_ege_math_profile --tags параметры,hard
  Найдите все a, при которых уравнение x² + ax + 1 = 0 имеет два
  различных корня, оба меньше 2.

# цель из profile.md
> materials add --type link
  https://stepik.org/lesson/12345

# с источником
> materials add --type theory --source учебник атанасян
  Теорема синусов: a/sin A = 2R
```

Результат:
1. Новый файл в `users/<user_key>/materials/<goal_id>/<type>/...md`
2. Запись в `users/<user_key>/materials/index.json`
3. Inline-кнопки: [Открыть] [Добавить ещё]