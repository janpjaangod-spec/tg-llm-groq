import re
from groq import Groq
from typing import List, Dict, Any

from bot_groq.config.settings import settings

# Инициализация клиента Groq
client = Groq(api_key=settings.groq_api_key)

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
    return cleaned or "По делу."

def llm_text(messages: List[Dict[str, Any]], model: str) -> str:
    """
    Отправляет текстовый запрос к LLM и возвращает отфильтрованный ответ.
    """
    try:
        resp = client.chat.completions.create(
            model=model, 
            messages=messages, 
            temperature=0.7,
            max_tokens=2048
        )
        out = resp.choices[0].message.content.strip()
        return post_filter(clean_reply(out))
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
            resp = client.chat.completions.create(
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
    
    response = llm_text([
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt}
    ], model)
    
    return prefix + response
