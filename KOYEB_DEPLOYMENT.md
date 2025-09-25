# 🚀 Развертывание Telegram Bot "Леха" на Koyeb

## 📋 Подготовка к развертыванию

### 1. Структура проекта для Koyeb
```
tg-llm-groq/
├── bot_groq/              # Основной код бота
├── requirements.txt       # Python зависимости
├── .env.example          # Пример переменных окружения
├── koyeb.toml            # Конфигурация Koyeb
├── Procfile              # Процессы для запуска
└── .python-version       # Версия Python
```

### 2. Настройка переменных окружения в Koyeb

В панели Koyeb → Settings → Environment Variables добавьте:

#### 🔑 **Обязательные переменные:**
```bash
BOT_TOKEN=1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_TOKEN=your_secure_admin_token_32_chars_min
```

#### ⚙️ **Основные настройки:**
```bash
# Среда выполнения
ENVIRONMENT=production
LOG_LEVEL=INFO
PYTHONPATH=/app

# База данных (автоматически создается)
DATABASE_URL=sqlite:///data/bot.db

# Безопасность
RATE_LIMIT_MESSAGES_PER_MINUTE=20
RATE_LIMIT_COMMANDS_PER_HOUR=100
BAN_THRESHOLD_VIOLATIONS=5
```

#### 🤖 **Настройки ИИ:**
```bash
# Groq API конфигурация
GROQ_MODEL=llama-3.1-8b-instant
GROQ_MAX_TOKENS=1000
GROQ_TEMPERATURE=0.7
GROQ_TOP_P=0.9
GROQ_STREAM=false

# Контекст и память
MAX_CONTEXT_LENGTH=4000
CONTEXT_MEMORY_SIZE=50
AUTO_CLEANUP_DAYS=30
```

#### 🌐 **Веб-интерфейс (опционально):**
```bash
# Веб-сервер настройки
WEB_HOST=0.0.0.0
WEB_PORT=8000
ENABLE_WEB_INTERFACE=false

# CORS настройки
ALLOWED_ORIGINS=*
CORS_CREDENTIALS=true
```

#### 📊 **Кеширование и производительность:**
```bash
# Memory cache
CACHE_TTL=3600
CACHE_MAX_SIZE=1000
ENABLE_MEMORY_CACHE=true

# Database optimization
DB_POOL_SIZE=5
DB_TIMEOUT=30
ENABLE_DB_OPTIMIZATION=true
```

#### 🛡️ **Фильтрация и безопасность:**
```bash
# Content filtering
ENABLE_TOXICITY_FILTER=true
TOXICITY_THRESHOLD=0.7
MAX_MESSAGE_LENGTH=4000
ENABLE_SPAM_PROTECTION=true

# Personal data protection
ENABLE_PII_DETECTION=true
AUTO_DELETE_PII=true
```

#### 📈 **Аналитика и мониторинг:**
```bash
# Analytics
ENABLE_ANALYTICS=true
ANALYTICS_RETENTION_DAYS=90
ENABLE_USER_PROFILING=true

# Logging
STRUCTURED_LOGGING=true
LOG_FORMAT=json
LOG_FILE_ROTATION=true
MAX_LOG_FILES=10
```

#### ⏰ **Планировщик задач:**
```bash
# Scheduler
SCHEDULER_TIMEZONE=Europe/Moscow
CLEANUP_INTERVAL_HOURS=24
BACKUP_INTERVAL_HOURS=168
ENABLE_SCHEDULED_REPORTS=false
```

#### 🔧 **Дополнительные настройки:**
```bash
# Bot behavior
DEFAULT_CHAT_MODE=normal
ENABLE_GROUP_COMMANDS=true
ENABLE_PRIVATE_COMMANDS=true
AUTO_DELETE_COMMANDS=false

# Performance
WORKER_THREADS=2
MAX_CONCURRENT_REQUESTS=10
REQUEST_TIMEOUT=30

# Features
ENABLE_MEDIA_PROCESSING=true
ENABLE_DOCUMENT_ANALYSIS=false
ENABLE_VOICE_PROCESSING=false
```

### 3. Создание Procfile для Koyeb

Основной процесс (только бот):
```
web: python -m bot_groq.main
```

Или с веб-интерфейсом:
```
web: python -m bot_groq.main
worker: python run_web.py
```

### 4. Koyeb конфигурация (koyeb.toml)

```toml
[build]
buildpack = "python"

[deploy]
# Основной сервис - Telegram Bot
[[deploy.services]]
name = "leha-bot"
type = "web"
instance_type = "nano"
regions = ["fra"]
port = 8080
env = [
  "ENVIRONMENT=production",
  "PYTHONPATH=/app"
]

# Health check
[deploy.services.health_check]
grace_period = "30s"
interval = "30s"
restart_limit = 5
path = "/health"

# Scaling
[deploy.services.scaling]
min = 1
max = 1
```

### 5. Файл .python-version
```
3.12
```

## 🚀 Пошаговое развертывание на Koyeb

### Шаг 1: Подготовка репозитория
```bash
# Клонируйте репозиторий
git clone https://github.com/your-username/tg-llm-groq
cd tg-llm-groq

# Убедитесь что все файлы на месте
ls -la
```

### Шаг 2: Создание приложения в Koyeb
1. Войдите в [Koyeb Dashboard](https://app.koyeb.com)
2. Нажмите "Create App"
3. Выберите "GitHub" как источник
4. Выберите ваш репозиторий `tg-llm-groq`
5. Укажите ветку `main`

### Шаг 3: Настройка сервиса
```yaml
Service name: leha-bot
Region: Frankfurt (fra)
Instance: Nano ($0/month с лимитами)
Port: 8080
Build command: (оставить пустым - Koyeb автоматически определит Python проект)
Run command: python -m bot_groq.main
```

### Шаг 4: Добавление переменных окружения
В разделе "Environment variables" добавьте все переменные из списка выше.

### Шаг 5: Развертывание
1. Нажмите "Deploy"
2. Ждите завершения сборки (3-5 минут)
3. Проверьте логи на ошибки

## 🔍 Проверка развертывания

### Проверка через логи Koyeb:
```bash
# В логах должно появиться:
✅ Bot started successfully
✅ Database initialized
✅ LLM service connected
✅ All handlers registered
🚀 Bot is ready to serve!
```

### Проверка в Telegram:
1. Найдите вашего бота
2. Отправьте `/start`
3. Проверьте ответ
4. Попробуйте команду `/admin` (для админов)

## 🛠️ Устранение проблем

### ❌ **TelegramConflictError**
```bash
# Причина: Бот уже запущен в другом месте
# Решение: Остановите все другие инстансы

# В логах найдите:
ERROR: Conflict: terminated by other getUpdates request

# Исправление:
1. Остановите старые деплоии
2. Подождите 30 секунд
3. Перезапустите на Koyeb
```

### ❌ **Groq API ошибки**
```bash
# Проверьте переменную GROQ_API_KEY
# Убедитесь что ключ действителен
# Проверьте лимиты API
```

### ❌ **Build ошибки**
```bash
# ERROR: failed to build: exit status 127
# bash: line 1: pip: command not found

# Решение: НЕ указывайте Build command
# Koyeb автоматически определит Python проект
# и установит зависимости из requirements.txt

# В настройках Koyeb:
Build command: (оставить ПУСТЫМ)
Run command: python -m bot_groq.main
```

### ❌ **Database ошибки**
```bash
# База данных создается автоматически
# Проверьте права доступа к /data
# Убедитесь что SQLite поддерживается
```

### ❌ **Memory/CPU лимиты**
```bash
# Koyeb Nano план имеет лимиты:
# - 512MB RAM
# - 0.1 CPU
# - 1GB трафика

# Оптимизация:
CACHE_MAX_SIZE=100          # Уменьшите кеш
MAX_CONCURRENT_REQUESTS=3   # Меньше параллельных запросов
WORKER_THREADS=1            # Один поток
```

## 📊 Мониторинг на Koyeb

### Доступные метрики:
- CPU использование
- Memory использование
- Network трафик
- HTTP requests
- Response time

### Настройка алертов:
1. Koyeb Dashboard → Monitoring
2. Настройте уведомления на email
3. Установите пороги для CPU > 80%, Memory > 400MB

## 🔄 Автоматическое обновление

### GitHub Actions (опционально):
```yaml
# .github/workflows/deploy.yml
name: Deploy to Koyeb
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Koyeb
        run: |
          # Koyeb автоматически подхватит изменения
          echo "Deployment triggered"
```

### Ручное обновление:
1. Push изменения в GitHub
2. Koyeb автоматически пересоберет
3. Проверьте логи развертывания

## 💰 Стоимость на Koyeb

### Nano план (Бесплатный):
- ✅ 512MB RAM
- ✅ 0.1 vCPU  
- ✅ 1GB исходящего трафика
- ✅ Подходит для небольших ботов

### Micro план ($7/месяц):
- ✅ 1GB RAM
- ✅ 0.5 vCPU
- ✅ 100GB трафика
- ✅ Рекомендуется для активных ботов

## 🎯 Оптимизация для Koyeb

### Конфигурация для экономии ресурсов:
```bash
# Минимальные настройки
CACHE_MAX_SIZE=50
MAX_CONTEXT_LENGTH=2000
WORKER_THREADS=1
ENABLE_WEB_INTERFACE=false
LOG_LEVEL=WARNING
ENABLE_ANALYTICS=false
```

### Конфигурация для производительности:
```bash
# Максимальные настройки  
CACHE_MAX_SIZE=1000
MAX_CONTEXT_LENGTH=4000
WORKER_THREADS=2
ENABLE_WEB_INTERFACE=true
LOG_LEVEL=INFO
ENABLE_ANALYTICS=true
```

## ✅ Готово!

После успешного развертывания:
1. ✅ Бот работает 24/7
2. ✅ Автоматические обновления из GitHub
3. ✅ Мониторинг через Koyeb Dashboard
4. ✅ Логи доступны в реальном времени
5. ✅ Безопасность через переменные окружения

**Ваш бот "Леха" готов к работе на Koyeb!** 🎉