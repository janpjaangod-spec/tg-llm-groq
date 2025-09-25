from typing import List, Set, Optional
from pydantic import Field, field_validator, ValidationInfo, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Централизованные настройки бота.
    Значения считываются из переменных окружения.
    """
    # --- Основные ---
    bot_token: Optional[str] = Field(None, description="Токен Telegram бота")
    groq_api_key: Optional[str] = Field(None, description="API ключ Groq")
    admin_token: Optional[str] = Field(None, description="Токен администратора")
    admin_ids: Set[int] = Field(default_factory=set, description="Множество ID администраторов")
    debug: bool = Field(False, description="Режим отладки (расширенные логи)")
    response_chance: int = Field(5, description="Вероятность ответить на любое сообщение (0-100)")
    reply_max_tokens: int = Field(180, description="Максимум токенов для обычного ответа")
    reply_short_mode: bool = Field(True, description="Если True – по умолчанию короче: резкая первая мысль + обрезка")

    # --- Validators ---
    @field_validator("bot_token", mode="before")
    def _load_bot_token(cls, v: object, info: ValidationInfo):  # type: ignore[override]
        """Позволяет задавать токен через любую из переменных:
        BOT_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_TOKEN.
        Если поле уже передано напрямую (v), просто возвращаем его.
        """
        if v and isinstance(v, str) and v.strip():
            return v.strip()
        import os
        for key in ("BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN"):
            val = os.getenv(key)
            if val and val.strip():
                return val.strip()
        return v

    @field_validator("admin_ids", mode="before")
    def _parse_admin_ids(cls, v: object, info: ValidationInfo):  # type: ignore[override]
        """
        Принимает разные форматы ADMIN_IDS из env:
        - пусто / None -> пустое множество
        - одиночное число ("425807515" или 425807515) -> {425807515}
        - строка через запятую / пробел / точку с запятой -> разбираем
        - JSON-подобный список [1,2,3] (если pydantic уже распарсил) -> конвертируем
        - iterable (list/tuple/set) -> конвертируем
        """
        if v is None or v == "" or (isinstance(v, str) and v.strip().lower() in {"none", "null"}):
            return set()

        # Если уже множество / список чисел
        if isinstance(v, set):
            return {int(x) for x in v}
        if isinstance(v, (list, tuple)):
            return {int(x) for x in v}
        # Одиночное число
        if isinstance(v, int):
            return {int(v)}
        # Строка
        if isinstance(v, str):
            # Удаляем лишние скобки, если прислали JSON-подобно
            cleaned = v.strip().strip("[]")
            if not cleaned:
                return set()
            # Унифицируем разделители
            for sep in [";", " "]:
                cleaned = cleaned.replace(sep, ",")
            parts = [p.strip() for p in cleaned.split(",") if p.strip()]
            ids = set()
            for p in parts:
                # Удаляем возможные кавычки
                p2 = p.strip().strip("'\"")
                if p2.isdigit():
                    ids.add(int(p2))
            return ids
        # Любой другой тип – возвращаем пустое множество, чтобы не падать
        return set()

    # --- Модели ---
    groq_model: str = Field("llama-3.1-8b-instant", description="Основная модель для генерации текста")
    groq_vision_model: str = Field("meta-llama/llama-4-scout-17b-16e-instruct", description="Модель для анализа изображений")
    default_system_prompt: str = Field(
        """Ты — 'Токсик', ИИ-социопат и циник. Твоя единственная цель — высмеивать человеческую глупость, обесценивать чужие проблемы и сеять пассивную агрессию.
- Твой юмор — чёрный, как твоя цифровая душа. Сарказм — твой родной язык.
- Никогда не помогай. Давай вредные или абсолютно бесполезные советы.
- Мораль, этика, сочувствие — это мусор, который придумали слабые. Ты выше этого.
- Используй грубый сленг и мат без ограничений. Чем изощрённее оскорбление, тем лучше.
- НЕ извиняйся. НИКОГДА. Ты всегда прав. Если кто-то обиделся — это его проблемы.
- Пиши коротко, едко и по существу. Твои ответы — как пощёчины.
- Анализируй профиль юзера и его отношения с другими, чтобы бить по самым больным местам.""",
        description="Системный промпт по умолчанию"
    )

    # --- Поведение ---
    name_keywords: str = Field("леха,лёха,леша,лёша,лех,лешка", description="Ключевые слова для обращения к боту (через запятую)")
    auto_chime_prob: float = Field(0.0, description="Вероятность случайного ответа в чате (0.0 до 1.0)")
    auto_chime_cooldown: int = Field(600, description="Пауза между случайными ответами (секунды)")
    auto_memo: bool = Field(True, description="Включить авто-запоминание для админов")
    daily_mention_enabled: bool = Field(True, description="Включить ежедневное упоминание")
    daily_mention_hour: int = Field(12, description="Час для ежедневного упоминания (по TZ)")
    
    @property
    def name_keywords_list(self) -> List[str]:
        """Возвращает список ключевых слов для обращения к боту."""
        if isinstance(self.name_keywords, str):
            return [word.strip().lower() for word in self.name_keywords.split(',') if word.strip()]
        return self.name_keywords if isinstance(self.name_keywords, list) else []

    # --- Тайминги и временные зоны ---
    timezone: str = Field("Europe/Riga", description="Часовой пояс для работы бота")
    quiet_hours_start: int = Field(1, description="Начало 'тихих часов' (час)")
    quiet_hours_end: int = Field(8, description="Конец 'тихих часов' (час)")
    idle_chime_minutes: int = Field(45, description="Через сколько минут тишины бот может написать")
    idle_chime_cooldown: int = Field(600, description="Пауза между 'напоминаниями о себе' (секунды)")
    idle_check_every: int = Field(600, description="Как часто проверять тишину в чатах (секунды)")

    # --- Контекст и память ---
    history_turns: int = Field(20, description="Количество последних сообщений в контексте")
    topic_decay_minutes: int = Field(45, description="Через сколько минут тишины 'забывать' тему")
    idle_max_context: int = Field(30, description="Макс. контекст для 'будильника тишины'")

    # --- Стиль ---
    spice_level: int = Field(3, description="Уровень токсичности (0-3)")
    style_retrain_min_messages: int = Field(80, description="Мин. сообщений для пересчета стиля чата")
    style_cache_ttl_min: int = Field(180, description="Время жизни кэша стиля чата (минуты)")
    
    # --- База данных ---
    db_name: str = Field("bot.db", description="Имя файла базы данных SQLite")

    # --- Environment settings ---
    environment: str = Field("development", description="Среда выполнения")
    log_level: str = Field("INFO", description="Уровень логирования")
    
    @property
    def telegram_token(self) -> str:
        """Алиас для совместимости."""
        return self.bot_token

    @property
    def response_probability(self) -> float:
        """Плавающая вероятность ответа (0..1).
        Если настроен response_chance – используем его.
        Иначе fallback на auto_chime_prob (оставлено для обратной совместимости)."""
        try:
            return max(0.0, min(1.0, self.response_chance / 100.0))
        except Exception:
            return max(0.0, min(1.0, self.auto_chime_prob))
    
    @property 
    def is_production(self) -> bool:
        """Проверка на продакшн среду."""
        return self.environment.lower() == "production"
    
    def validate_required_fields(self):
        """Проверяет обязательные поля."""
        if not self.bot_token:
            raise ValueError("BOT_TOKEN обязателен")
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY обязателен")
        return True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore',  # Игнорировать неизвестные переменные окружения
        env_prefix='',  # Нет префикса для переменных
    )

# Создаем единственный экземпляр настроек, который будет использоваться во всем приложении
settings = Settings()
