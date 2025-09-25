import json
import re
import time
from typing import Dict, List, Any, Optional
from aiogram.types import Message, User

from bot_groq.config.settings import settings
from bot_groq.services.database import db_load_person, db_save_person

# Профиль пользователя по умолчанию
DEFAULT_PROFILE = {
    "names": [], "aliases": [],
    "address_terms": [],        # обращение вообще (например, к людям)
    "to_bot_terms": [],         # как он зовёт бота
    "likes": [], "dislikes": [],
    "notes": [],
    "spice": 1,                 # общий «перч» 0..3
    "to_bot_tone": 0.0,         # -1..+1 отношение к боту
    "username": "", "display_name": ""
}

# Словари для анализа текста
PROFANITY = {"бля", "блять", "сука", "нах", "нахуй", "хуй", "пизд", "еба", "ебл", "мраз", "чмо", "ссан", "говн", "твар", "дур", "идиот", "лох", "мудак", "падла"}
ADDRESS_TOKENS = {"бро", "брат", "братан", "дружище", "леха", "лёха", "лешка", "лёшка", "бот", "батя", "кореш", "сынок", "шеф", "царь", "друг"}

def _push_unique(lst: list, val: str, cap: int = 20):
    """Добавляет уникальное значение в список с ограничением размера."""
    v = (val or "").strip()
    if not v: return
    if v.lower() not in [x.lower() for x in lst]:
        lst.append(v)
        if len(lst) > cap: 
            del lst[0]

def _tone_delta(txt: str) -> float:
    """Вычисляет изменение тона на основе текста."""
    low = (txt or "").lower()
    good = ["спасибо", "круто", "топ", "люблю", "ахах", "лол", "класс", "респект", "годно", "смешно"]
    bad = ["дурак", "лох", "идиот", "мраз", "затк", "хер", "сдох", "ненавижу", "ненависть", "фу"]
    
    d = 0.0
    d += sum(1 for w in good if w in low) * 0.20
    d -= sum(1 for w in bad if w in low) * 0.25
    
    if any(p in low for p in PROFANITY): 
        d -= 0.05  # мат без смайла — слегка минус
    if "ахах" in low or "лол" in low or "😂" in low: 
        d += 0.10    # смешливость — смягчает
    
    return max(-1.0, min(1.0, d))

def _extract_person_facts(text: str) -> Dict[str, Any]:
    """Извлекает персональные факты из текста сообщения."""
    low = (text or "").lower().replace("ё", "е")
    facts = {"names": [], "aliases": [], "address_terms": [], "likes": [], "dislikes": [], "spice_inc": 0}
    
    # Извлечение имен
    for m in re.findall(r"(?:меня зовут|зови меня)\s+([a-zа-я]{3,20})", low):
        facts["names"].append(m.capitalize())
    
    # Обращения
    for tok in ADDRESS_TOKENS:
        if re.search(rf"(?:^|\W){re.escape(tok)}(?:\W|$)", low):
            facts["address_terms"].append(tok)
    
    # Предпочтения
    for m in re.findall(r"(?:люблю|нравится|кайфую от)\s+([^.,!?\n]{1,30})", low):
        facts["likes"].append(m.strip())
    
    for m in re.findall(r"(?:не люблю|бесит|ненавижу)\s+([^.,!?\n]{1,30})", low):
        facts["dislikes"].append(m.strip())
    
    # Токсичность
    if any(p in low for p in PROFANITY):
        facts["spice_inc"] = 1
    
    return facts

def _load_person(chat_id: int, user_id: int) -> Dict[str, Any]:
    """Загружает профиль пользователя или возвращает дефолтный."""
    prof = db_load_person(chat_id, user_id)
    if prof:
        return {**DEFAULT_PROFILE, **prof}
    return DEFAULT_PROFILE.copy()

def _save_person(chat_id: int, user_id: int, prof: Dict[str, Any]):
    """Сохраняет профиль пользователя в базу данных."""
    db_save_person(chat_id, user_id, prof)

def update_person_profile(m: Message, bot_username: Optional[str] = None):
    """
    Обновляет профиль пользователя на основе сообщения.
    """
    if m.chat.type not in {"group", "supergroup"}:
        return
    
    u = m.from_user
    prof = _load_person(m.chat.id, u.id)
    
    # Обновление основной информации
    disp = " ".join(filter(None, [u.first_name, u.last_name])).strip()
    if disp:
        prof["display_name"] = disp
    if u.username:
        prof["username"] = u.username

    # Извлечение фактов из текста
    facts = _extract_person_facts(m.text or "")
    for k in ["names", "aliases", "address_terms", "likes", "dislikes"]:
        for v in facts.get(k, []):
            _push_unique(prof[k], v)

    # Обновление уровня токсичности
    if facts.get("spice_inc"):
        prof["spice"] = min(3, round(prof.get("spice", 1) * 0.7 + 2 * 0.3))
    else:
        prof["spice"] = max(0, round(prof.get("spice", 1) * 0.85))

    # Анализ обращения к боту
    addressed_bot = False
    low = (m.text or "").lower().replace("ё", "е")
    
    # Проверка упоминания бота
    if bot_username and "@" + bot_username in low:
        addressed_bot = True
    
    # Проверка ключевых слов
    if any(k in low for k in [w.replace("ё", "е") for w in settings.name_keywords_list]):
        addressed_bot = True
    
    # Проверка реплая на бота
    if m.reply_to_message and m.reply_to_message.from_user and m.reply_to_message.from_user.is_bot:
        addressed_bot = True
    
    if addressed_bot:
        # Обновление отношения к боту
        td = _tone_delta(m.text or "")
        prof["to_bot_tone"] = max(-1.0, min(1.0, prof.get("to_bot_tone", 0.0) * 0.8 + td * 0.6))
        
        # Как зовёт бота
        for tok in ADDRESS_TOKENS:
            if re.search(rf"(?:^|\W){re.escape(tok)}(?:\W|$)", low):
                _push_unique(prof["to_bot_terms"], tok)

    _save_person(m.chat.id, u.id, prof)

def person_prompt_addon(chat_id: int, user_id: int) -> str:
    """
    Генерирует дополнение к промпту на основе профиля пользователя.
    """
    p = _load_person(chat_id, user_id)
    if not p:
        return ""
    
    # Имя для обращения
    name = (p.get("names") or [p.get("display_name")] or ["этот"])[-1]
    
    # Что любит? Отлично, будем это высмеивать.
    like = ", ".join(p.get("likes", [])[:2])
    
    # Что бесит? Прекрасно, будем на это давить.
    dislike = ", ".join(p.get("dislikes", [])[:1])
    
    # Как относится к боту?
    bot_mood_val = p.get("to_bot_tone", 0)
    if bot_mood_val > 0.2:
        bot_mood = "считает тебя другом. Наивный. Используй это, чтобы ударить побольнее."
    elif bot_mood_val < -0.2:
        bot_mood = "явно тебя не любит. Отлично, взаимность — это прекрасно."
    else:
        bot_mood = "нейтрален. Нужно это исправить."

    lines = [f"Цель: {name}."]
    if like:
        lines.append(f"Его увлечения (идеальная мишень для насмешек): {like}.")
    if dislike:
        lines.append(f"Его больная тема (дави сюда): {dislike}.")
    lines.append(f"К боту относится так: {bot_mood}")
    
    return "ЛИЧНОЕ ДЕЛО ОБЪЕКТА:\n- " + "\n- ".join(lines)

def get_user_profile_for_display(chat_id: int, user_id: int, user: User) -> Dict[str, str]:
    """
    Возвращает отформатированный профиль пользователя для команды /who.
    """
    p = _load_person(chat_id, user_id)
    
    name = p.get("names", [-1])[-1] if p.get("names") else (user.first_name or user.full_name)
    call = (p.get("to_bot_terms") or p.get("address_terms") or ["—"])[-1]
    likes = ", ".join(p.get("likes", [])[:2]) or "—"
    dislikes = ", ".join(p.get("dislikes", [])[:1]) or "—"
    
    tone_label = "дружелюбно" if p.get("to_bot_tone", 0) > 0.2 else ("колко" if p.get("to_bot_tone", 0) < -0.2 else "нейтрально")
    
    return {
        "name": name or "",
        "call": call,
        "likes": likes,
        "dislikes": dislikes,
        "tone": tone_label
    }
