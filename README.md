# 🤖 Telegram Bot "Леха" - Enterprise Edition

Интеллектуальный Telegram-бот нового поколения с модульной архитектурой, веб-интерфейсом администратора и продвинутыми возможностями ИИ.

## 🌟 Ключевые особенности

### 🧠 **Продвинутый ИИ**
- Groq API (Llama 3.1-8b) для быстрых ответов
- Адаптивное профилирование пользователей
- Анализ групповой динамики и отношений
- Система памяти и контекста

### 🏗️ **Модульная архитектура 2.0**
- Полное разделение обязанностей
- Система плагинов
- Централизованная конфигурация
- Enterprise-ready структура

### 🌐 **Веб-интерфейс администратора**
- Real-time дашборд с аналитикой
- Управление чатами и пользователями
- Система отчетов и экспорта
- Мониторинг производительности

### 🛡️ **Безопасность и мониторинг**
- Структурированное логирование (structlog)
- Система фильтрации контента
- Rate limiting и защита от спама
- Детальная аналитика действий

## 🚀 Быстрый старт

### 📋 Требования
- Python 3.12+
- Telegram Bot Token
- Groq API Key

### ⚡ Установка

```bash
git clone https://github.com/your-repo/tg-llm-groq
cd tg-llm-groq
pip install -r requirements.txt
```

### ⚙️ Конфигурация

Создайте файл `.env`:

```env
# Основные токены
BOT_TOKEN=your_telegram_bot_token
GROQ_API_KEY=your_groq_api_key
ADMIN_TOKEN=your_secure_admin_token

# Настройки базы данных
DATABASE_URL=sqlite:///data/bot.db

# Логирование
LOG_LEVEL=INFO

# Веб-интерфейс
WEB_HOST=0.0.0.0
WEB_PORT=8000

# Дополнительные настройки (опционально)
REDIS_URL=redis://localhost:6379
ENVIRONMENT=production
```

### 🏃 Запуск

#### Только бот:
```bash
python -m bot_groq.main
```

#### Только веб-интерфейс:
```bash
python run_web.py
```

#### Полная система с Docker:
```bash
docker-compose up -d
```

## 🏛️ Архитектура

```
bot_groq/
├── 📁 config/          # Настройки и конфигурация
│   └── settings.py     # Центральная конфигурация
├── 📁 services/        # Бизнес-логика
│   ├── database.py     # Работа с БД
│   ├── llm.py          # Groq API интеграция
│   ├── scheduler.py    # Планировщик задач
│   └── analytics.py    # Система аналитики
├── � handlers/        # Обработчики Telegram
│   ├── admin.py        # Админ команды
│   ├── public.py       # Пользовательские команды
│   ├── chat.py         # Обработка сообщений
│   └── media.py        # Медиа контент
├── 📁 core/           # Основная логика
│   ├── profiles.py     # Профилирование
│   ├── relations.py    # Анализ отношений
│   ├── style_analysis.py # Анализ стиля
│   └── plugin_system.py # Система плагинов
├── 📁 utils/          # Утилиты
│   ├── logging.py      # Структурированные логи
│   ├── filters.py      # Фильтрация контента
│   └── cache.py        # Кеширование
├── 📁 web/            # Веб-интерфейс
│   ├── app.py          # FastAPI приложение
│   └── templates/      # HTML шаблоны
└── main.py            # Точка входа
```

## 🌐 Веб-интерфейс

### 📊 Dashboard
- Real-time статистика сообщений и запросов
- Системные метрики (CPU, память, кеш)
- График активности за 24 часа
- Последние активные чаты

### 💬 Управление чатами
- Просмотр всех подключенных чатов
- Изменение режимов работы бота
- Статистика по каждому чату
- Экспорт данных в CSV

### 👥 Управление пользователями
- Поиск и фильтрация пользователей
- Система банов с указанием времени
- Аналитика поведения пользователей
- Детальные профили

### 📈 Аналитика
- Глобальная статистика системы
- Отчеты по периодам
- Анализ токсичности
- Популярные слова и фразы

### 📋 Мониторинг
- Просмотр логов в реальном времени
- Фильтрация по уровням
- Системная информация
- Health checks

### Доступ к веб-интерфейсу:
```
http://localhost:8000
Authorization: Bearer YOUR_ADMIN_TOKEN
```

## 🔧 Система плагинов

Создайте собственные плагины:

```python
from bot_groq.core.plugin_system import BotPlugin, PluginType

class WeatherPlugin(BotPlugin):
    @property
    def metadata(self):
        return PluginMetadata(
            name="Weather Info",
            version="1.0.0",
            description="Получение погодной информации",
            plugin_type=PluginType.COMMAND
        )
    
    async def handle(self, message, context):
        # Логика обработки погоды
        return "🌤️ Сегодня солнечно, +25°C"

# Регистрация плагина
plugin_manager.register_plugin(WeatherPlugin())
```

## 📋 API команды

### 👤 Пользовательские команды
- `/start` - Регистрация и приветствие
- `/help` - Подробная справка
- `/profile` - Личный профиль
- `/stats` - Статистика чата

### 👨‍💼 Администраторские команды
- `/admin` - Админ панель
- `/mode <normal|silent|disabled>` - Режим бота
- `/ban <user_id> [hours]` - Бан пользователя
- `/unban <user_id>` - Разбан пользователя
- `/export` - Экспорт данных чата
- `/status` - Системная информация

### 🌐 Web API
```bash
# Получение статистики
GET /api/stats/realtime

# Управление чатами
GET /api/chats
POST /api/chats/mode

# Аналитика
GET /api/analytics/global
GET /api/analytics/chat/{chat_id}

# Генерация отчетов
POST /api/reports/generate
```

## 📊 База данных

### SQLite структура:
```sql
-- Пользователи
users (user_id, username, first_name, profile_data, created_at)

-- Чаты
chats (chat_id, title, type, mode, settings, created_at)

-- Сообщения
messages (id, chat_id, user_id, content, timestamp, response_time)

-- Отношения
user_relations (user1_id, user2_id, chat_id, relation_type, strength)

-- Аналитика
analytics (chat_id, user_id, metric_type, value, timestamp)
```

## 🐳 Docker развертывание

### Разработка:
```bash
docker-compose up -d bot redis
```

### Продакшн:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Включает:
- **Bot**: Основной Telegram бот
- **Web**: Веб-интерфейс администратора  
- **Redis**: Кеширование и сессии
- **Nginx**: Reverse proxy (опционально)
- **Prometheus + Grafana**: Мониторинг (опционально)

## 📈 Мониторинг и метрики

### Доступные метрики:
- Количество обработанных сообщений
- Время ответа LLM
- Hit rate кеша
- Использование памяти
- Активные чаты и пользователи

### Grafana дашборды:
- Общая производительность
- Детализация по чатам
- Системные ресурсы
- Ошибки и предупреждения

## 🔧 Расширенная настройка

### Переменные окружения:
```env
# Groq API
GROQ_MODEL=llama-3.1-8b-instant
GROQ_MAX_TOKENS=1000
GROQ_TEMPERATURE=0.7

# Кеширование
CACHE_TTL=3600
CACHE_MAX_SIZE=1000

# Фильтрация
ENABLE_TOXICITY_FILTER=true
MAX_MESSAGE_LENGTH=4000

# Планировщик
SCHEDULER_TIMEZONE=Europe/Moscow
CLEANUP_INTERVAL_HOURS=24
```

### Кастомные настройки:
```python
# bot_groq/config/custom_settings.py
class CustomSettings(Settings):
    # Ваши дополнительные настройки
    custom_feature_enabled: bool = True
    custom_api_endpoint: str = "https://api.example.com"
```

## �️ Безопасность

### Рекомендации:
- Используйте сильные токены (32+ символа)
- Настройте HTTPS для веб-интерфейса
- Регулярно обновляйте зависимости
- Мониторьте логи на подозрительную активность
- Настройте backup базы данных

### Rate limiting:
```python
# Настройки в settings.py
RATE_LIMIT_MESSAGES_PER_MINUTE = 20
RATE_LIMIT_COMMANDS_PER_HOUR = 100
BAN_THRESHOLD_VIOLATIONS = 5
```

## 🔄 Обновления

### Миграция с версии 1.0:
```bash
# Создайте backup
cp bot.db bot.db.backup

# Запустите миграцию
python -m bot_groq.migrations.migrate_v1_to_v2

# Проверьте целостность данных
python -m bot_groq.utils.verify_migration
```

## 🤝 Разработка

### Структура коммитов:
```
feat: новая функция
fix: исправление бага  
docs: обновление документации
refactor: рефакторинг кода
test: добавление тестов
```

### Тестирование:
```bash
# Все тесты
pytest

# С покрытием
pytest --cov=bot_groq

# Только интеграционные
pytest tests/integration/
```

## 📚 Документация

- [ARCHITECTURE.md](ARCHITECTURE.md) - Подробная архитектура
- [SETUP.md](SETUP.md) - Детальная настройка
- [CONTRIBUTING.md](CONTRIBUTING.md) - Гайд по разработке
- [ROADMAP.md](ROADMAP.md) - Планы развития

## 📄 Лицензия

MIT License - свободное использование и модификация.

## 🆘 Поддержка

- GitHub Issues для багов и предложений
- [Telegram канал](https://t.me/leha_bot_updates) для новостей
- [Wiki](https://github.com/your-repo/tg-llm-groq/wiki) для FAQ

---

**🚀 Ready for Enterprise!** Полнофункциональный Telegram бот с веб-интерфейсом, готовый к продакшену.