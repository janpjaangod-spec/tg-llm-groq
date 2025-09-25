# 🏗️ Архитектура Токсик Бота

## Обзор системы

Токсик бот построен как монолитное приложение на Python с использованием асинхронной архитектуры. Основные компоненты:

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot API                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  aiogram Dispatcher                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              Message Handlers                           ││
│  │  • Text messages    • Commands                          ││
│  │  • Photos/Images    • Admin functions                   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   Core Logic                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  • Person Profile System  • Relationship Analysis      ││
│  │  • Chat Style Analysis    • Memory Management          ││
│  │  • Context Building       • Auto-activity Detection    ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                External Services                           │
│  ┌─────────────────────────────────────────────────────────┐│
│  │      Groq API          │        SQLite DB              ││
│  │  • Text Generation     │  • User profiles               ││
│  │  • Vision Models       │  • Chat history                ││
│  │  • Multiple fallbacks  │  • Relationships               ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Основные компоненты

### 1. Message Processing Pipeline

```python
Telegram Message → aiogram → Handler Selection → Context Building → LLM → Response
                                    ↓
                              Profile Updates → Memory Storage
```

**Этапы обработки:**
1. **Фильтрация**: Определение типа сообщения и применимых обработчиков
2. **Контекст**: Загрузка профиля пользователя, истории, стиля чата
3. **Обогащение**: Добавление социальных связей и памяти
4. **Генерация**: Отправка в LLM с составленным промптом
5. **Постобработка**: Фильтрация ответа и сохранение в историю

### 2. Система профилей пользователей

```python
DEFAULT_PROFILE = {
    "names": [],                    # Имена и алиасы
    "aliases": [],                  # Альтернативные имена
    "address_terms": [],            # Способы обращения
    "to_bot_terms": [],            # Как обращается к боту
    "likes": [],                   # Предпочтения
    "dislikes": [],                # Антипатии
    "notes": [],                   # Заметки администраторов
    "spice": 1,                    # Уровень токсичности (0-3)
    "to_bot_tone": 0.0,           # Отношение к боту (-1 до +1)
    "username": "",               # Telegram username
    "display_name": ""            # Отображаемое имя
}
```

**Механизм обновления профилей:**
- Автоматическое извлечение фактов из сообщений
- Анализ тона и эмоциональной окраски
- Обновление метрик взаимодействия
- Сохранение административных заметок

### 3. Анализ межличностных отношений

Система отслеживает отношения между пользователями по схеме `A → B`:

```python
relationship = {
    "score": float,        # Сила связи (-1 до +1)
    "tone": float,         # Тон общения (-1 до +1) 
    "addr": [],           # История обращений
    "last_ts": float      # Время последнего взаимодействия
}
```

**Факторы влияющие на отношения:**
- Частота реплаев и упоминаний
- Тон сообщений (позитивный/негативный)
- Использование имен и обращений
- Эмодзи и реакции

### 4. Адаптивный стиль чата

Система анализирует и адаптируется к стилю каждого чата:

```python
style_profile = {
    "avg_msg_len": float,      # Средняя длина сообщения
    "profanity_rate": float,   # Частота мата
    "emoji_rate": float,       # Использование эмодзи
    "caps_rate": float,        # Частота CAPS
    "question_rate": float,    # Частота вопросов
    "slang_terms": [],         # Местный сленг
    "common_topics": [],       # Популярные темы
    "activity_pattern": {},    # Паттерны активности
}
```

## База данных

### Схема таблиц

```sql
-- Основные настройки бота
CREATE TABLE settings (
    id INTEGER PRIMARY KEY CHECK (id=1),
    system_prompt TEXT NOT NULL,
    model TEXT NOT NULL
);

-- История личных диалогов
CREATE TABLE history (
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,           -- 'user' или 'assistant'
    content TEXT NOT NULL,
    ts REAL NOT NULL
);

-- История групповых чатов
CREATE TABLE chat_history (
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    ts REAL NOT NULL,
    user_id TEXT
);

-- Профили пользователей
CREATE TABLE person_profile (
    chat_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    profile_json TEXT NOT NULL,   -- JSON с данными профиля
    updated_ts REAL NOT NULL,
    PRIMARY KEY (chat_id, user_id)
);

-- Межличностные отношения
CREATE TABLE relationship_profile (
    chat_id TEXT NOT NULL,
    user_id_a TEXT NOT NULL,      -- От кого
    user_id_b TEXT NOT NULL,      -- К кому
    score REAL NOT NULL,          -- Сила связи
    tone REAL NOT NULL,           -- Тон отношений
    addr_json TEXT,               -- JSON с историей обращений
    last_ts REAL NOT NULL,
    PRIMARY KEY (chat_id, user_id_a, user_id_b)
);

-- Стилевые профили чатов
CREATE TABLE chat_style (
    chat_id TEXT PRIMARY KEY,
    style_json TEXT NOT NULL,     -- JSON со стилевыми метриками
    updated_ts REAL NOT NULL
);

-- Напоминания
CREATE TABLE reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    text TEXT NOT NULL,
    due_ts REAL NOT NULL,
    created_ts REAL NOT NULL
);

-- Пользовательская память
CREATE TABLE user_memory (
    user_id TEXT NOT NULL,
    value TEXT NOT NULL,
    ts REAL NOT NULL
);

-- Память чатов
CREATE TABLE chat_memory (
    chat_id TEXT NOT NULL,
    value TEXT NOT NULL,
    ts REAL NOT NULL
);
```

## Алгоритмы и логика

### 1. Определение необходимости ответа

```python
def should_respond(message):
    if message.chat.type == "private":
        return True
    
    if was_called(message):  # Упоминание бота
        return True
        
    if should_autochime(message.chat.id):  # Случайный вброс
        return "autochime"
        
    return False
```

### 2. Построение контекста для LLM

```python
def build_context(user_id, message):
    context = []
    
    # Системный промпт
    system_prompt = get_system_prompt()
    
    # Стилевые добавки
    if is_group_chat:
        system_prompt += get_style_addon(chat_id)
        system_prompt += get_person_addon(chat_id, user_id)
        system_prompt += get_social_addon(chat_id, user_id, reply_to)
    
    # Память
    user_facts = get_user_memory(user_id)
    chat_facts = get_chat_memory(chat_id)
    system_prompt += format_memory(user_facts, chat_facts)
    
    # История диалога
    recent_history = get_recent_history(user_id, limit=20)
    
    return [{"role": "system", "content": system_prompt}] + recent_history
```

### 3. Автоматическая активность

**Детектор тишины:**
```python
async def idle_watcher():
    while True:
        chats = get_active_chats()
        for chat_id, last_activity in chats:
            silence_minutes = (now() - last_activity) / 60
            
            if silence_minutes > IDLE_THRESHOLD:
                if not in_cooldown(chat_id):
                    await generate_idle_message(chat_id)
```

**Случайные вбросы:**
```python
def should_autochime(chat_id):
    if random.random() < AUTO_CHIME_PROB:
        if not in_cooldown(chat_id, AUTO_CHIME_COOLDOWN):
            return True
    return False
```

## Потоки данных

### 1. Обработка текстового сообщения

```
Message → Profile Update → Relationship Update → Context Building → LLM → Response
    ↓              ↓                ↓               ↓            ↓        ↓
 Tone Analysis  Social Graph   Memory Retrieval  Prompt Build  Filter  History
```

### 2. Обработка изображений

```
Image → File Download → Vision API → Context Analysis → Response Generation
   ↓         ↓            ↓             ↓                     ↓
Caption    URL Build   Multi-model   Image Memory         Filter
```

### 3. Административные команды

```
Admin Command → Permission Check → Action Execute → State Update → Response
      ↓              ↓                ↓              ↓           ↓
   Parse Args    Check Admin ID   Database Op   Cache Update  Confirm
```

## Конфигурация и настройки

### Переменные окружения по категориям:

**Основные настройки:**
```bash
TELEGRAM_BOT_TOKEN         # Токен бота
GROQ_API_KEY              # API ключ Groq
GROQ_MODEL                # Основная модель
DEFAULT_SYSTEM_PROMPT     # Системный промпт
```

**Поведенческие настройки:**
```bash
SPICE_LEVEL               # Уровень токсичности (0-3)
AUTO_CHIME_PROB           # Вероятность вброса (0-1)
AUTO_CHIME_COOLDOWN       # Пауза между вбросами (сек)
NAME_KEYWORDS             # Ключевые слова для активации
```

**Временные настройки:**
```bash
IDLE_CHIME_MINUTES        # Минуты тишины для активации
QUIET_HOURS_START         # Начало тихих часов
QUIET_HOURS_END           # Конец тихих часов
TOPIC_DECAY_MINUTES       # Время забывания темы
```

**Продвинутые настройки:**
```bash
HISTORY_TURNS             # Размер контекста истории
STYLE_CACHE_TTL_MIN       # TTL кэша стиля (мин)
STYLE_RETRAIN_MIN_MESSAGES # Мин. сообщений для пересчета стиля
```

## Производительность и оптимизация

### Узкие места:
1. **База данных**: SQLite не оптимальна для concurrent доступа
2. **Память**: Отсутствие кэширования часто используемых данных
3. **LLM запросы**: Нет батчинга и кэширования похожих запросов
4. **Файловые операции**: Изображения обрабатываются синхронно

### Рекомендации по оптимизации:
1. **Connection pooling** для базы данных
2. **Redis** для кэширования и сессий
3. **Async file operations** для изображений
4. **LLM response caching** для популярных запросов
5. **Database indexing** для частых queries

## Безопасность

### Текущие меры:
- Фильтрация системных терминов в ответах
- Проверка прав доступа для админских команд
- Валидация входных данных

### Потенциальные уязвимости:
- SQL injection (частично защищено parametrized queries)
- Memory exhaustion при больших чатах
- Rate limiting отсутствует
- Логи могут содержать чувствительную информацию

### Рекомендации:
- Внедрить rate limiting
- Шифрование чувствительных данных в БД
- Аудит логи для административных действий
- Sandbox для выполнения пользовательского кода
- OWASP security headers для веб-интерфейса

## Мониторинг и отладка

### Текущее логирование:
```python
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")
```

### Метрики для мониторинга:
- Количество обработанных сообщений
- Время ответа LLM API
- Ошибки и исключения
- Размер базы данных
- Memory usage

### Инструменты для отладки:
- SQLite browser для просмотра данных
- Telegram Bot API logs
- Python profiler для поиска bottlenecks
- Custom debug commands для админов