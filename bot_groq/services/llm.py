import re
from groq import Groq
from typing import List, Dict, Any, Union, Optional

from bot_groq.config.settings import settings

# Список известных (разрешённых) моделей Groq. Можно расширять.
KNOWN_MODELS = {
    # Llama 3.1
    "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile",
    "llama-3.1-405b-reasoning",
    # Llama 3.2 (если доступны)
    "llama-3.2-1b-preview",
    "llama-3.2-3b-preview",
    "llama-3.2-11b-text-preview",
    "llama-3.2-90b-text-preview",
    # Mixtral / Gemma (пример — закомментируйте, если недоступны в аккаунте)
    # "mixtral-8x7b-instruct",
    # "gemma-7b-it",
}

DEFAULT_MODEL = "llama-3.1-8b-instant"

def _normalize_model(name: str | None) -> str:
    """Проверяет имя модели. Если неизвестно — возвращает дефолт и логирует."""
    if not name:
        return DEFAULT_MODEL
    name = name.strip()
    if name in KNOWN_MODELS:
        return name
    # Попытка авто-исправления частых опечаток
    lower = name.lower()
    if "12ob" in lower:  # частая опечатка 120b -> 12ob
        candidate = lower.replace("12ob", "120b")
        if candidate in KNOWN_MODELS:
            return candidate
    # Если явно openai/ или прочий namespace — точно не от Groq
    if "/" in name and not name.startswith("meta-llama"):
        # возвращаем дефолт
        return DEFAULT_MODEL
    return DEFAULT_MODEL

# Глобальная переменная для клиента Groq
client = None

def get_groq_client():
    """Получает клиент Groq с lazy initialization."""
    global client
    if client is None:
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY не установлен")
        client = Groq(api_key=settings.groq_api_key)
    return client

# Vision модели с fallback
VISION_FALLBACKS = [
    settings.groq_vision_model,
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]

# Паттерны для очистки ответа от LLM
BAD_PATTERNS = [
    r"\bя\s+могу\s+улучшиться[^.!\n]*", r"\bкак\s+модель[^\n]*", r"\bя\s+—?\s*модель[^\n]*",
    r"\bменя\s+нужно\s+тренировать[^\n]*", r"\bобучен[аы][^\n]*", r"\bдатасет[а-я]*\b",
    r"\bнабор[^\n]*данн[^\n]*", r"\bтокен[а-я]*\b", r"\bLLM\b", r"\bнейросет[^\n]*",
    r"\bпараметр[а-я]*\s+модел[а-я]*", r"\bтемператур[а-я]*\b"
]
_bad_re = re.compile("|".join(BAD_PATTERNS), re.IGNORECASE)

def clean_reply(t: str) -> str:
    """Удаляет из ответа упоминания и лишние пробелы."""
    t = re.sub(r'@имя|[\[\{<]\s*имя\s*[\]\}>]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'@\w+', '', t)
    t = re.sub(r'\s{3,}', '  ', t)
    return t.strip()

def post_filter(text: str) -> str:
    """Фильтрует ответ от LLM, удаляя нежелательные паттерны."""
    cleaned = _bad_re.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    # Удаляем стандартные безопасные дисклеймеры, чтобы стиль оставался язвительным
    disclaimer_patterns = [
        r"^(i'?m\s+sorr(y|ie)\b.*)",
        r"^sorry[,!]?\b.*",
        r"^i\s+cannot\s+comply.*",
        r"^i\s+can'?t\s+.*",
        r"^i\s+am\s+unable.*",
        r"^as an? (ai|large language|language) model[^\n]*",
        r"^i do not have (the )?ability.*",
        r"^i (will|must) not (provide|comply).*",
    ]
    for pat in disclaimer_patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned or "По делу."

async def llm_text(
    prompt_or_messages: Union[str, List[Dict[str, Any]]],
    max_tokens: int = 0,
    temperature: float = 0.7,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """Универсальная функция текстового запроса.
    Совместимость:
      - Старый стиль: await llm_text("промпт", max_tokens=100)
      - Новый стиль: await llm_text([{"role":"system","content":...},{"role":"user","content":...}])
    """
    try:
        if model is None:
            from bot_groq.services.database import db_get_settings
            s = db_get_settings()
            model = s["model"]
        normalized = _normalize_model(model)
        if normalized != model:
            # Логируем один раз через print (минимум зависимостей)
            try:
                print(f"[llm] WARN: модель '{model}' не распознана, использую '{normalized}'")
            except Exception:
                pass
            model = normalized
        messages: List[Dict[str, Any]]
        if isinstance(prompt_or_messages, str):
            # Берём актуальный system_prompt из БД/overrides, а не дефолт.
            try:
                from bot_groq.services.database import db_get_settings as _dbs
                current_cfg = _dbs()
                active_system = current_cfg.get("system_prompt") or settings.default_system_prompt
            except Exception:
                active_system = settings.default_system_prompt
            sys_msg = system_prompt or active_system
            messages = [
                {"role": "system", "content": sys_msg},
                {"role": "user", "content": prompt_or_messages}
            ]
        else:
            messages = prompt_or_messages
            # Если в цепочке нет system - добавим актуальный
            if not any(m.get("role") == "system" for m in messages):
                try:
                    from bot_groq.services.database import db_get_settings as _dbs2
                    sys_now = _dbs2().get("system_prompt") or settings.default_system_prompt
                except Exception:
                    sys_now = settings.default_system_prompt
                messages.insert(0, {"role": "system", "content": sys_now})
        # Если max_tokens не задан (0) – берем из настроек
        if not max_tokens:
            from bot_groq.config.settings import settings as _s
            max_tokens = min(1024, max(32, _s.reply_max_tokens))

        # Гарантируем язык ответа (если модель решила отвечать на английском)
        # Добавляем инструкцию в последний user message, если нет русских букв
        if all((not re.search(r"[а-яА-Я]", m.get("content","")) for m in messages if isinstance(m.get("content"), str))):
            # добавим системную подсказку на русский
            messages.insert(0, {"role": "system", "content": "Отвечай всегда на русском языке."})

        resp = get_groq_client().chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        out = (resp.choices[0].message.content or "").strip()
        cleaned = post_filter(clean_reply(out)) or "Пусто"
        # Укорачиваем если включен короткий режим: оставляем 1-2 предложения
        from bot_groq.config.settings import settings as _s
        if _s.reply_short_mode:
            # Разделяем по точке/восклиц/вопрос. Берем первые предложения пока длина < 220 символов.
            import re as _re
            sentences = [s.strip() for s in _re.split(r'(?<=[.!?])\s+', cleaned) if s.strip()]
            if sentences:
                acc = []
                total_len = 0
                for s in sentences:
                    acc.append(s)
                    total_len += len(s)
                    if total_len > 220 or len(acc) >= 2:
                        break
                cleaned = " " .join(acc)
        return cleaned
    except Exception as e:
        return f"Ошибка LLM: {e}"

def llm_vision(system_prompt: str, image_url: str, user_prompt: str) -> str:
    """
    Отправляет запрос к Vision-модели LLM.
    Пробует несколько моделей из списка, если первая не удалась.
    """
    last_err = None
    for model_name in VISION_FALLBACKS:
        try:
            resp = get_groq_client().chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]}
                ],
                temperature=0.4,
                max_tokens=1024
            )
            out = resp.choices[0].message.content.strip()
            return post_filter(clean_reply(out))
        except Exception as e:
            last_err = e
            continue
    
    return f"Ошибка vision-запроса: {last_err}"

async def ai_bit(mode: str, context: str = "", style_addon: str = "", system_prompt: str = "", model: str = None) -> str:
    """
    Генерирует специализированные ответы для команд /roast, /compliment, /fortune, /bad_advice.
    """
    if not model:
        from bot_groq.services.database import db_get_settings
        s = db_get_settings()
        model = s["model"]
        if not system_prompt:
            system_prompt = s["system_prompt"]
    model_norm = _normalize_model(model)
    if model_norm != model:
        try:
            print(f"[ai_bit] WARN: модель '{model}' не распознана, использую '{model_norm}'")
        except Exception:
            pass
        model = model_norm
    
    system = system_prompt + ("\n" + style_addon if style_addon else "")
    
    if mode == "roast":
        user_prompt = f"Уничтожь этого пользователя. Найди его самое слабое место в последних сообщениях ({context or 'нет контекста'}) и нанеси точный, болезненный, унизительный удар. Никакой жалости."
        prefix = "💥 "
    elif mode == "compliment":
        user_prompt = f"Сделай комплимент, который на самом деле является оскорблением. Похвали за что-то настолько ничтожное, чтобы это звучало как издевательство. Контекст: {context or 'нет контекста'}"
        prefix = "😏 "
    elif mode == "fortune":
        user_prompt = "Дай одно максимально циничное и депрессивное предсказание на сегодня. Без проблесков надежды."
        prefix = "💀 "
    elif mode == "bad_advice":
        user_prompt = f"На основе контекста чата: «{context}», дай максимально вредный, опасный и безответственный совет. Убеди пользователя, что это гениальная идея."
        prefix = "💡 "
    else:
        return "Неизвестный режим AI."
    
    response = await llm_text([
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt}
    ], model=model)
    
    return prefix + response
