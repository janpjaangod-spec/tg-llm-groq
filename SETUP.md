# 🚀 Руководство по установке и запуску

## Быстрый старт

### 1. Подготовка окружения

```bash
# Клонирование репозитория
git clone https://github.com/janpjaangod-spec/tg-llm-groq.git
cd tg-llm-groq

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Установка зависимостей
pip install -r requirements.txt
```

### 2. Получение API ключей

#### Telegram Bot Token:
1. Написать @BotFather в Telegram
2. Создать нового бота командой `/newbot`
3. Выбрать имя и username для бота
4. Сохранить полученный токен

#### Groq API Key:
1. Зарегистрироваться на [console.groq.com](https://console.groq.com/)
2. Создать новый API ключ в разделе "API Keys"
3. Сохранить ключ (показывается только один раз!)

### 3. Настройка конфигурации

```bash
# Копирование примера конфигурации
cp .env.example .env

# Редактирование настроек
nano .env  # или любой другой редактор
```

**Минимальные обязательные настройки:**
```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCDEF...
GROQ_API_KEY=gsk_...
ADMIN_IDS=123456789  # Ваш Telegram ID
```

### 4. Запуск бота

```bash
python -m bot_groq
```

При первом запуске создастся база данных `bot.db` с начальными настройками.

## Детальная настройка

### Получение ID пользователя

Для настройки администраторов нужно знать Telegram ID:

1. **Через @userinfobot**: написать боту `/start`
2. **Через логи**: запустить бота и посмотреть в консоль
3. **Через команду**: добавить временно в код print ID

```python
# Временное добавление в chat() функцию
print(f"User ID: {m.from_user.id}, Chat ID: {m.chat.id}")
```

### Настройка моделей

#### Рекомендуемые модели:
- **Для тестирования**: `llama-3.1-8b-instant` (быстро, дешево)
- **Для продакшена**: `llama-3.1-70b-versatile` (качественно, медленнее)
- **Для экспериментов**: `mixtral-8x7b-32768` (длинный контекст)

#### Vision модели:
- `meta-llama/llama-4-scout-17b-16e-instruct` (по умолчанию)
- `meta-llama/llama-4-maverick-17b-128e-instruct` (резерв)

### Настройка поведения

#### Уровни токсичности:
- **0**: Почти нейтральный, редкий сарказм
- **1**: Легкий сарказм, подтрунивание
- **2**: Средняя токсичность, колкости
- **3**: Максимальная токсичность, жесткий троллинг

#### Автоматическая активность:
```bash
# Консервативные настройки
AUTO_CHIME_PROB=0.005        # 0.5% вероятность
AUTO_CHIME_COOLDOWN=1800     # 30 минут между вбросами

# Активные настройки  
AUTO_CHIME_PROB=0.02         # 2% вероятность
AUTO_CHIME_COOLDOWN=600      # 10 минут между вбросами

# Тестовые настройки
AUTO_CHIME_PROB=0.1          # 10% вероятность
AUTO_CHIME_COOLDOWN=60       # 1 минута между вбросами
```

## Развертывание в продакшене

### Docker (рекомендуется)

```bash
# Создание Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

CMD ["python", "-m", "bot_groq"]
EOF

# Сборка и запуск
docker build -t toxik-bot .
docker run -d --name toxik-bot --env-file .env toxik-bot
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  bot:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    depends_on:
      - redis
      
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

### Systemd Service (Linux)

```bash
# Создание сервиса
sudo tee /etc/systemd/system/toxik-bot.service << EOF
[Unit]
Description=Toxik Telegram Bot
After=network.target

[Service]
Type=simple
User=toxik
WorkingDirectory=/opt/toxik-bot
Environment=PATH=/opt/toxik-bot/venv/bin
ExecStart=/opt/toxik-bot/venv/bin/python -m bot_groq
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Запуск сервиса
sudo systemctl daemon-reload
sudo systemctl enable toxik-bot
sudo systemctl start toxik-bot

# Просмотр логов
sudo journalctl -u toxik-bot -f
```

## Мониторинг и отладка

### Просмотр логов

```bash
# В Docker
docker logs -f toxik-bot

# Systemd
sudo journalctl -u toxik-bot -f

# Напрямую
python bot_groq.py
```

### Основные проблемы и решения

#### "TELEGRAM_BOT_TOKEN is not set"
- Проверить файл `.env`
- Убедиться что токен корректный
- Проверить права доступа к файлу

#### "GROQ_API_KEY is not set"  
- Проверить API ключ в консоли Groq
- Убедиться что квота не исчерпана
- Проверить формат ключа (должен начинаться с `gsk_`)

#### Бот не отвечает в группе
- Добавить бота как администратора
- Проверить настройки `NAME_KEYWORDS`
- Убедиться что бот может читать сообщения

#### Высокое потребление API
- Уменьшить `AUTO_CHIME_PROB`
- Увеличить `AUTO_CHIME_COOLDOWN`
- Использовать более дешевую модель

#### База данных заблокирована
```bash
# Поиск процесса использующего БД
lsof bot.db

# Перезапуск бота
sudo systemctl restart toxik-bot
```

### Полезные команды для отладки

```bash
# Проверка размера БД
du -h bot.db

# Бэкап БД
cp bot.db bot.db.backup.$(date +%Y%m%d)

# Просмотр структуры БД
sqlite3 bot.db ".schema"

# Статистика сообщений
sqlite3 bot.db "SELECT COUNT(*) FROM chat_history"

# Активные пользователи
sqlite3 bot.db "SELECT COUNT(DISTINCT user_id) FROM person_profile"
```

## Обновление бота

### Стандартное обновление
```bash
# Остановка бота
sudo systemctl stop toxik-bot  # или docker stop toxik-bot

# Бэкап данных
cp bot.db bot.db.backup.$(date +%Y%m%d)

# Обновление кода
git pull origin main
pip install -r requirements.txt

# Запуск бота
sudo systemctl start toxik-bot  # или docker start toxik-bot
```

### Обновление с миграциями
```bash
# Проверка версии БД
sqlite3 bot.db "SELECT * FROM settings LIMIT 1"

# Выполнение миграций (если есть)
python migrate.py

# Перезапуск
sudo systemctl restart toxik-bot
```

## Безопасность

### Рекомендации:
- 🔒 Не храните `.env` в git
- 🔑 Регулярно меняйте API ключи
- 👥 Ограничьте список администраторов
- 📊 Мониторьте использование API
- 🛡️ Используйте файерволл для ограничения доступа
- 💾 Делайте регулярные бэкапы БД

### Настройка файерволла (UFW):
```bash
# Только исходящие соединения
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH для администрирования
sudo ufw allow ssh

# Включить файерволл
sudo ufw enable
```

## Поддержка

При возникновении проблем:

1. 📖 Проверьте логи бота
2. 🔍 Поищите решение в Issues на GitHub
3. 📝 Создайте новый Issue с детальным описанием
4. 💬 Включите в Issue релевантные логи (без секретных данных!)

### Информация для баг-репорта:
```bash
# Версия Python
python --version

# Версии зависимостей
pip freeze

# Логи (последние 50 строк)
tail -50 /var/log/toxik-bot.log

# Системная информация
uname -a
```