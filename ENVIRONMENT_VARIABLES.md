# 🌍 Environment Variables Reference

## 📋 Полный список переменных окружения

### 🔑 **ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ**

```bash
# Токен Telegram бота (получить у @BotFather)
BOT_TOKEN=1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA

# API ключ Groq (получить на console.groq.com)  
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Токен администратора (минимум 32 символа, генерируйте случайно)
ADMIN_TOKEN=your_secure_admin_token_32_chars_minimum
```

---

## ⚙️ **ОСНОВНЫЕ НАСТРОЙКИ**

### 🏗️ Среда выполнения
```bash
# Среда выполнения: development, testing, production
ENVIRONMENT=production

# Уровень логирования: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Python путь (для Docker/Koyeb)
PYTHONPATH=/app
```

### 🗄️ База данных
```bash
# URL базы данных (SQLite по умолчанию)
DATABASE_URL=sqlite:///data/bot.db

# Для PostgreSQL (продвинутая настройка):
# DATABASE_URL=postgresql://user:password@localhost:5432/botdb

# Пул соединений с БД
DB_POOL_SIZE=5
DB_TIMEOUT=30

# Автоматическая оптимизация БД
ENABLE_DB_OPTIMIZATION=true
```

---

## 🤖 **GROQ API НАСТРОЙКИ**

```bash
# Модель для генерации ответов
GROQ_MODEL=llama-3.1-8b-instant
# Альтернативы: llama-3.1-70b-versatile, mixtral-8x7b-32768

# Максимальное количество токенов в ответе
GROQ_MAX_TOKENS=1000

# Температура (креативность): 0.0-2.0
GROQ_TEMPERATURE=0.7

# Top-p sampling: 0.0-1.0
GROQ_TOP_P=0.9

# Потоковая передача ответов
GROQ_STREAM=false

# Таймаут для API запросов (секунды)
GROQ_TIMEOUT=30
```

---

## 🛡️ **БЕЗОПАСНОСТЬ И ФИЛЬТРАЦИЯ**

### 🚫 Rate Limiting
```bash
# Максимум сообщений в минуту на пользователя
RATE_LIMIT_MESSAGES_PER_MINUTE=20

# Максимум команд в час на пользователя
RATE_LIMIT_COMMANDS_PER_HOUR=100

# Количество нарушений для автобана
BAN_THRESHOLD_VIOLATIONS=5

# Длительность временного бана (часы)
DEFAULT_BAN_DURATION_HOURS=24
```

### 🔍 Фильтрация контента
```bash
# Включить фильтр токсичности
ENABLE_TOXICITY_FILTER=true

# Порог токсичности: 0.0-1.0 (выше = ban)
TOXICITY_THRESHOLD=0.7

# Максимальная длина сообщения (символы)
MAX_MESSAGE_LENGTH=4000

# Защита от спама
ENABLE_SPAM_PROTECTION=true

# Детекция персональных данных
ENABLE_PII_DETECTION=true

# Автоудаление персональных данных
AUTO_DELETE_PII=true

# Фильтр нецензурной лексики
ENABLE_PROFANITY_FILTER=true
```

---

## ⚡ **ПРОИЗВОДИТЕЛЬНОСТЬ И КЕШИРОВАНИЕ**

### 💾 Memory Cache
```bash
# Включить кеширование в памяти
ENABLE_MEMORY_CACHE=true

# Время жизни кеша (секунды)
CACHE_TTL=3600

# Максимальный размер кеша (записей)
CACHE_MAX_SIZE=1000

# Автоочистка кеша при превышении лимита
CACHE_AUTO_CLEANUP=true
```

### 🚀 Многопоточность
```bash
# Количество рабочих потоков
WORKER_THREADS=2

# Максимум одновременных запросов
MAX_CONCURRENT_REQUESTS=10

# Таймаут запроса (секунды)
REQUEST_TIMEOUT=30

# Размер пула соединений
CONNECTION_POOL_SIZE=20
```

### 🧠 Контекст и память
```bash
# Максимальная длина контекста (символы)
MAX_CONTEXT_LENGTH=4000

# Размер памяти контекста (сообщений)
CONTEXT_MEMORY_SIZE=50

# Время хранения контекста (дни)  
CONTEXT_RETENTION_DAYS=7
```

---

## 🌐 **ВЕБ-ИНТЕРФЕЙС АДМИНИСТРАТОРА**

```bash
# Включение веб-интерфейса
ENABLE_WEB_INTERFACE=false

# Хост для веб-сервера
WEB_HOST=0.0.0.0

# Порт веб-сервера
WEB_PORT=8000

# Разрешенные домены для CORS
ALLOWED_ORIGINS=*

# Поддержка cookies в CORS
CORS_CREDENTIALS=true

# Максимальный размер загружаемого файла (байт)
MAX_UPLOAD_SIZE=10485760

# Директория для статических файлов
STATIC_FILES_DIR=bot_groq/web/static

# Директория для шаблонов
TEMPLATES_DIR=bot_groq/web/templates
```

---

## 📊 **АНАЛИТИКА И МОНИТОРИНГ**

### 📈 Аналитика
```bash
# Включить систему аналитики
ENABLE_ANALYTICS=true

# Срок хранения аналитики (дни)
ANALYTICS_RETENTION_DAYS=90

# Профилирование пользователей
ENABLE_USER_PROFILING=true

# Анализ отношений между пользователями
ENABLE_RELATION_ANALYSIS=true

# Сбор статистики чатов
ENABLE_CHAT_STATISTICS=true

# Глобальная аналитика системы
ENABLE_GLOBAL_ANALYTICS=true
```

### 📝 Логирование
```bash
# Структурированное логирование (JSON)
STRUCTURED_LOGGING=true

# Формат логов: json, text
LOG_FORMAT=json

# Ротация лог файлов
LOG_FILE_ROTATION=true

# Максимальное количество лог файлов
MAX_LOG_FILES=10

# Максимальный размер лог файла (МБ)
MAX_LOG_FILE_SIZE=50

# Логирование в файл
LOG_TO_FILE=true

# Директория для логов
LOG_DIR=logs
```

---

## ⏰ **ПЛАНИРОВЩИК ЗАДАЧ**

```bash
# Часовой пояс для планировщика
SCHEDULER_TIMEZONE=Europe/Moscow

# Интервал очистки базы (часы)
CLEANUP_INTERVAL_HOURS=24

# Автоматическое удаление старых данных (дни)
AUTO_CLEANUP_DAYS=30

# Интервал создания бэкапов (часы)
BACKUP_INTERVAL_HOURS=168

# Включить запланированные отчеты
ENABLE_SCHEDULED_REPORTS=false

# Время отправки ежедневных отчетов (HH:MM)
DAILY_REPORT_TIME=09:00

# Включить автоматические задачи
ENABLE_AUTOMATED_TASKS=true
```

---

## 🎭 **ПОВЕДЕНИЕ БОТА**

### 💬 Режимы работы
```bash
# Режим по умолчанию для новых чатов: normal, silent, disabled
DEFAULT_CHAT_MODE=normal

# Включить команды в группах
ENABLE_GROUP_COMMANDS=true

# Включить команды в приватных чатах
ENABLE_PRIVATE_COMMANDS=true

# Автоудаление команд администратора
AUTO_DELETE_COMMANDS=false

# Реагировать только на упоминания в группах
MENTION_ONLY_IN_GROUPS=false

# Игнорировать ботов
IGNORE_BOTS=true
```

### 🎨 Стиль и персональность
```bash
# Адаптивность стиля к пользователю
ENABLE_ADAPTIVE_STYLE=true

# Использование эмодзи в ответах
ENABLE_EMOJI_RESPONSES=true

# Формальный/неформальный стиль по умолчанию
DEFAULT_FORMALITY_LEVEL=informal

# Длинные/короткие ответы по умолчанию
DEFAULT_RESPONSE_LENGTH=medium

# Включить юмор и сарказм
ENABLE_HUMOR=true
```

---

## 🔌 **СИСТЕМА ПЛАГИНОВ**

```bash
# Включить систему плагинов
ENABLE_PLUGIN_SYSTEM=true

# Директория для плагинов
PLUGINS_DIR=bot_groq/plugins

# Автозагрузка плагинов при старте
AUTO_LOAD_PLUGINS=true

# Разрешить внешние плагины
ALLOW_EXTERNAL_PLUGINS=false

# Максимальное время выполнения плагина (секунды)
PLUGIN_TIMEOUT=10

# Изоляция плагинов (sandbox)
PLUGIN_SANDBOX=true
```

---

## 🎮 **ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ**

### 📷 Обработка медиа
```bash
# Включить обработку изображений
ENABLE_MEDIA_PROCESSING=true

# Анализ документов
ENABLE_DOCUMENT_ANALYSIS=false

# Обработка голосовых сообщений
ENABLE_VOICE_PROCESSING=false

# Максимальный размер изображения (байт)
MAX_IMAGE_SIZE=10485760

# Поддерживаемые форматы изображений
SUPPORTED_IMAGE_FORMATS=jpg,jpeg,png,gif,webp

# Качество сжатия изображений (1-100)
IMAGE_COMPRESSION_QUALITY=85
```

### 🌍 Интеграции
```bash
# OpenWeatherMap API для погоды
WEATHER_API_KEY=your_weather_api_key

# News API для новостей
NEWS_API_KEY=your_news_api_key

# Spotify API для музыки
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# Google Translate API
GOOGLE_TRANSLATE_KEY=your_google_translate_key

# Включить интеграции
ENABLE_WEATHER_INTEGRATION=false
ENABLE_NEWS_INTEGRATION=false
ENABLE_MUSIC_INTEGRATION=false
ENABLE_TRANSLATE_INTEGRATION=false
```

---

## 🔧 **СПЕЦИАЛЬНЫЕ НАСТРОЙКИ ДЛЯ ПЛАТФОРМ**

### 🚀 Koyeb Optimization
```bash
# Оптимизация для Koyeb Nano плана
KOYEB_NANO_MODE=true

# Уменьшенные лимиты для экономии памяти
CACHE_MAX_SIZE=100
MAX_CONTEXT_LENGTH=2000
WORKER_THREADS=1
MAX_CONCURRENT_REQUESTS=3

# Отключение тяжелых функций
ENABLE_WEB_INTERFACE=false
ENABLE_SCHEDULED_REPORTS=false
ENABLE_DOCUMENT_ANALYSIS=false
ENABLE_VOICE_PROCESSING=false
```

### 🐳 Docker Settings
```bash
# Пользователь для контейнера
DOCKER_USER=app

# Рабочая директория
WORKDIR=/app

# Включить health checks
ENABLE_HEALTH_CHECKS=true

# Интервал health check (секунды)
HEALTH_CHECK_INTERVAL=30
```

### ☁️ Redis (если используется)
```bash
# URL Redis сервера
REDIS_URL=redis://localhost:6379

# База данных Redis (0-15)
REDIS_DB=0

# Префикс для ключей Redis
REDIS_KEY_PREFIX=leha_bot:

# Таймаут подключения Redis
REDIS_TIMEOUT=5

# Максимум соединений в пуле
REDIS_MAX_CONNECTIONS=20
```

---

## 📱 **НАСТРОЙКИ TELEGRAM**

```bash
# Максимальная длина сообщения Telegram (4096)
TELEGRAM_MAX_MESSAGE_LENGTH=4096

# Использовать Telegram Bot API локально
USE_LOCAL_BOT_API=false

# URL локального Bot API сервера
LOCAL_BOT_API_URL=http://localhost:8081

# Таймаут для Telegram API (секунды)
TELEGRAM_API_TIMEOUT=30

# Retry политика для Telegram API
TELEGRAM_RETRY_ATTEMPTS=3
TELEGRAM_RETRY_DELAY=1
```

---

## 🔍 **ОТЛАДКА И РАЗРАБОТКА**

```bash
# Режим отладки
DEBUG_MODE=false

# Детальное логирование SQL запросов
DEBUG_SQL=false

# Показывать трассировку ошибок
SHOW_ERROR_TRACEBACK=true

# Профилирование производительности
ENABLE_PROFILING=false

# Сохранение дампов при критических ошибках
SAVE_ERROR_DUMPS=true

# Тестовый режим (не отправляет сообщения)
TEST_MODE=false

# Dry run режим (только логирование)
DRY_RUN=false
```

---

## 🎯 **ГОТОВЫЕ КОНФИГУРАЦИИ**

### 🏠 Локальная разработка
```bash
ENVIRONMENT=development
LOG_LEVEL=DEBUG
ENABLE_WEB_INTERFACE=true
DEBUG_MODE=true
CACHE_MAX_SIZE=100
WORKER_THREADS=1
```

### 🔬 Тестирование
```bash
ENVIRONMENT=testing
LOG_LEVEL=INFO
TEST_MODE=true
DRY_RUN=true
ENABLE_ANALYTICS=false
AUTO_CLEANUP_DAYS=1
```

### 🚀 Продакшн (Koyeb)
```bash
ENVIRONMENT=production
LOG_LEVEL=INFO
KOYEB_NANO_MODE=true
CACHE_MAX_SIZE=200
MAX_CONTEXT_LENGTH=3000
WORKER_THREADS=1
ENABLE_WEB_INTERFACE=false
```

### 🏢 Enterprise
```bash
ENVIRONMENT=production
LOG_LEVEL=INFO
ENABLE_WEB_INTERFACE=true
ENABLE_ANALYTICS=true
STRUCTURED_LOGGING=true
ENABLE_PLUGIN_SYSTEM=true
WORKER_THREADS=4
MAX_CONCURRENT_REQUESTS=50
```

---

## ⚡ **Быстрые команды для настройки**

### Генерация ADMIN_TOKEN
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Проверка переменных окружения
```bash
python -c "from bot_groq.config.settings import settings; print(settings.model_dump())"
```

### Тест подключения к Groq
```bash
python -c "from bot_groq.services.llm import llm_service; print('✅ Groq connected')"
```

---

**💡 Совет:** Начните с минимальной конфигурации и постепенно включайте дополнительные функции по мере необходимости!