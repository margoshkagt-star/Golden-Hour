# Пример работы скилла task-triage

## Вход

```
1. Подготовить презентацию для инвесторов
2. Забрать заказ из пункта выдачи
3. Пробежать 5 км
4. Выучить главу 3 по ML
5. Разобрать почту
6. Написать статью в блог
7. Сходить к стоматологу (запись на пятницу)
8. Оплатить хостинг (до 20-го)
9. Спланировать отпуск (когда-нибудь)
10. Запустить новый скилл для ассистента
```

## Выход (фрагмент)

```json
{
  "tasks": [
    {
      "id": "t_001",
      "title": "Подготовить презентацию для инвесторов",
      "weight": 9,
      "weight_label": "critical",
      "weight_breakdown": {
        "base_importance": 5,
        "deadline_score": 0,
        "category_boost": 2,
        "context_keywords": 2
      },
      "categories": ["работа", "проект:startup", "срочное"],
      "difficulty": 5,
      "subtasks": [
        {"title": "Сформулировать 3 ключевых тезиса", "estimated_difficulty": 2, "acceptance": "Список из 3 пунктов одобрен"},
        {"title": "Собрать метрики роста", "estimated_difficulty": 2, "acceptance": "Графики готовы"},
        {"title": "Сделать драфт слайдов", "estimated_difficulty": 3, "acceptance": "12 слайдов собраны"},
        {"title": "Прогнать с таймингом", "estimated_difficulty": 1, "acceptance": "Укладывается в 10 минут"}
      ],
      "confidence": "high"
    },
    {
      "id": "t_007",
      "title": "Сходить к стоматологу",
      "weight": 8,
      "weight_label": "high",
      "weight_breakdown": {
        "base_importance": 3,
        "deadline_score": 4,
        "category_boost": 1,
        "context_keywords": 0
      },
      "categories": ["здоровье"],
      "difficulty": 1,
      "subtasks": [],
      "deadline": "2026-06-19",
      "confidence": "high",
      "reasoning": "Запись в пятницу, пользователь обычно откладывает мед. визиты — boost +1."
    },
    {
      "id": "t_009",
      "title": "Спланировать отпуск",
      "weight": 2,
      "weight_label": "low",
      "categories": ["путешествия", "личное развитие"],
      "difficulty": 3,
      "subtasks": [],
      "confidence": "medium",
      "reasoning": "Дедлайн не указан, помечено 'когда-нибудь' — фоновый приоритет."
    }
  ],
  "new_categories": [
    {"name": "проект:startup", "emoji": "🚀", "reason": "Упомянут инвесторский трек"}
  ],
  "summary": "Горит: t_001 (разбить на 4 шага и начать сегодня), t_007 (запись в пятницу, не откладывать). Средний приоритет: t_002, t_003, t_010. Фон: t_009."
}
```
