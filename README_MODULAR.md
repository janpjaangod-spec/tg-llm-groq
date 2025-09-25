# Модульная версия бота Леха

## Структура проекта

```
bot_groq/
├── config/          # Конфигурация
│   └── settings.py  # Centralized settings management
├── services/        # Сервисы
│   ├── database.py  # Database operations
│   ├── llm.py      # Groq LLM integration
│   └── scheduler.py # Background tasks
├── handlers/        # Обработчики сообщений
│   ├── admin.py    # Admin commands
│   ├── public.py   # Public commands
│   ├── chat.py     # Chat message handlers
│   └── media.py    # Media handlers
├── core/           # Бизнес-логика
│   ├── profiles.py # User profiling
│   ├── relations.py # Group dynamics
│   └── style_analysis.py # Communication style analysis
└── main.py         # Entry point
```

## Запуск

```bash
# Устанавливаем зависимости
pip install -r requirements.txt

# Запускаем модульную версию
python run_modular.py

# Или напрямую
python -m bot_groq.main
```

## Преимущества модульной архитектуры

- ✅ Разделение ответственности
- ✅ Легкость тестирования
- ✅ Масштабируемость
- ✅ Читаемость кода
- ✅ Централизованная конфигурация
- ✅ Оптимизированная база данных
- ✅ Улучшенная обработка ошибок

## Новые функции

- **Профилирование пользователей**: запоминание предпочтений, стиля общения
- **Анализ групповой динамики**: понимание отношений между участниками
- **Адаптивный стиль ответов**: подстройка под манеру общения пользователя
- **Расширенная медиа поддержка**: анализ изображений через Groq Vision
- **Админ панель**: статистика, управление режимами, отладка