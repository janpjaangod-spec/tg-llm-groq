from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter
import random
import time
import re

from bot_groq.config.settings import settings
from bot_groq.services.database import (
    db_add_chat_message, db_load_person, db_save_person,
    db_get_chat_tail, db_get_last_activity, log_chat_event
)
from bot_groq.services.llm import llm_text, ai_bit, post_filter
from bot_groq.core.profiles import update_person_profile, person_prompt_addon
from bot_groq.core.relations import get_manipulation_context, find_alliance_opportunities
from bot_groq.core.style_analysis import get_style_adaptation_prompt

router = Router()

async def should_respond(message: Message, bot_username: str) -> tuple[bool, str]:
    """
    Определяет, должен ли бот ответить на сообщение.
    Возвращает (should_respond, reason).
    """
    if message.chat.type == "private":
        return True, "private_chat"
    
    # Проверяем режим бота
    system_profile = db_load_person(message.chat.id, 0) or {}
    bot_mode = system_profile.get("bot_mode", "toxic")
    
    if bot_mode == "silent":
        return False, "silent_mode"
    
    text = (message.text or "").lower()
    
    # Прямые обращения к боту
    if f"@{bot_username}" in text:
        return True, "direct_mention"
    
    # Реплай на сообщение бота
    if message.reply_to_message and message.reply_to_message.from_user.is_bot:
        return True, "reply_to_bot"
    
    # Ключевые слова
    if any(keyword.lower() in text for keyword in settings.name_keywords_list):
        return True, "keyword_trigger"
    
    # Вопросы боту
    question_patterns = [
        r'\bбот\b.*\?',
        r'\bлеха\b.*\?', 
        r'\bлёха\b.*\?',
        r'что думаешь',
        r'как считаешь',
        r'твое мнение'
    ]
    
    if any(re.search(pattern, text) for pattern in question_patterns):
        return True, "question_to_bot"
    
    # Случайные ответы с заданной вероятностью
    if random.randint(1, 100) <= settings.response_chance:
        return True, "random_response"
    
    # AI-bit анализ (более умный анализ контекста). Асинхронно с таймаутом.
    try:
        import asyncio
        bit = asyncio.create_task(ai_bit("roast", context=message.text or ""))
        result = await asyncio.wait_for(bit, timeout=0.5)
        if result and isinstance(result, str) and len(result) > 3:
            return True, "ai_bit_trigger"
    except Exception:
        pass
    
    return False, "no_trigger"

async def generate_contextual_response(message: Message, trigger_reason: str) -> str:
    """Генерирует контекстуальный ответ на сообщение."""
    
    # Получаем историю сообщений для контекста (используем настройку)
    history = db_get_chat_tail(message.chat.id, limit=settings.history_turns)
    
    # Обновляем профиль пользователя
    bot_info = await message.bot.get_me()
    update_person_profile(message, bot_info.username)
    
    # Базовый промпт
    prompt_parts = [
        f"Сообщение пользователя: {message.text}",
        f"Причина ответа: {trigger_reason}"
    ]
    
    # Добавляем персональную информацию
    personal_addon = person_prompt_addon(message.chat.id, message.from_user.id)
    if personal_addon:
        prompt_parts.append(personal_addon)
    
    # Анализ стиля пользователя
    user_messages = [msg.get('content', '') for msg in history 
                     if msg.get('user_id') == str(message.from_user.id)][-5:]
    
    if user_messages:
        style_prompt = get_style_adaptation_prompt(user_messages, "toxic")
        prompt_parts.append(f"СТИЛЬ АДАПТАЦИИ: {style_prompt}")
    
    # Контекст манипуляций для групп
    if message.chat.type in ["group", "supergroup"]:
        manipulation_context = get_manipulation_context(message.chat.id)
        if manipulation_context:
            prompt_parts.append(manipulation_context)
    
    # Контекст последних сообщений – берём больше и используем правильный ключ 'content'
    if len(history) > 1:
        recent_context = []
        # Откидываем системные / пустые
        for msg in history[-min(12, len(history)):]:
            content = msg.get('content')
            if not content:
                continue
            if content.startswith('[ФОТО]'):
                content = '[image]'
            username = msg.get('username') or f"U{msg.get('user_id','?')}"
            role = msg.get('role')
            prefix = 'бот' if role == 'assistant' else username
            recent_context.append(f"{prefix}: {content[:400]}")
        if recent_context:
            prompt_parts.append("КОНТЕКСТ (последние сообщения, новое в конце):\n" + "\n".join(recent_context[-10:]))
    
    # Финальный промпт
    full_prompt = "\n\n".join(prompt_parts)
    
    # Генерируем ответ
    response = await llm_text(full_prompt, max_tokens=0)
    
    if response:
        # Применяем пост-фильтр
        filtered_response = post_filter(response)
        return filtered_response
    
    # Fallback ответы если LLM не работает
    fallback_responses = {
        "direct_mention": [
            "Что хотел?",
            "Слушаю внимательно.",
            "Да, я здесь.",
            "Обращаешься ко мне?"
        ],
        "reply_to_bot": [
            "Продолжаем диалог.",
            "И что на это сказать?",
            "Интересная мысль.",
            "Понятно."
        ],
        "question_to_bot": [
            "Хороший вопрос.",
            "Дай подумать...",
            "А что ты сам думаешь?",
            "Сложный случай."
        ],
        "keyword_trigger": [
            "Услышал свое имя.",
            "Кто-то меня звал?",
            "Я тут.",
            "Что случилось?"
        ],
        "random_response": [
            "Просто хотел сказать привет.",
            "Заскучал без общения.",
            "Решил вклиниться в беседу.",
            "А я что думаю..."
        ]
    }
    
    responses = fallback_responses.get(trigger_reason, ["Понятно."])
    return random.choice(responses)

@router.message(F.text)
async def handle_text_message(message: Message):
    """Обработчик текстовых сообщений."""
    try:
        # Сохраняем сообщение в базу данных
        log_chat_event(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            text=message.text or "",
            timestamp=time.time(),
            is_bot=False
        )
        
        # Обновляем профиль пользователя
        bot_info = await message.bot.get_me()
        update_person_profile(message, bot_info.username)
        
        # Определяем, нужно ли отвечать
        should_resp, reason = await should_respond(message, bot_info.username)
        
        if should_resp:
            # Генерируем и отправляем ответ
            response = await generate_contextual_response(message, reason)
            
            if response and response.strip():
                await message.reply(response)
                
                # Сохраняем ответ бота в историю
                log_chat_event(
                    chat_id=message.chat.id,
                    user_id=bot_info.id,
                    username=bot_info.username,
                    text=response,
                    timestamp=time.time(),
                    is_bot=True
                )
        
    except Exception as e:
        # Логируем ошибку, но не показываем пользователю
        print(f"Error handling message: {e}")

@router.message(F.new_chat_members)
async def handle_new_members(message: Message):
    """Обработчик новых участников группы."""
    try:
        new_members = message.new_chat_members or []
        
        for member in new_members:
            if member.is_bot:
                continue  # Игнорируем ботов
            
            # Проверяем режим бота
            system_profile = db_load_person(message.chat.id, 0) or {}
            bot_mode = system_profile.get("bot_mode", "toxic")
            
            if bot_mode == "silent":
                continue
            
            # Генерируем приветствие
            welcome_prompts = [
                f"Новый участник {member.first_name} присоединился к группе. Поприветствуй его в своем токсичном стиле.",
                f"В группу зашел {member.first_name}. Сделай ему 'теплый' прием.",
                f"Новичок {member.first_name} в чате. Покажи ему местные порядки."
            ]
            
            try:
                response = await llm_text(random.choice(welcome_prompts), max_tokens=100)
                
                if response:
                    await message.reply(response)
                else:
                    # Fallback приветствия
                    fallback_welcomes = [
                        f"О, {member.first_name} подтянулся. Посмотрим, что за фрукт.",
                        f"Новенький! {member.first_name}, добро пожаловать в наш уютный хаос.",
                        f"Еще один храбрец, {member.first_name}. Надеюсь, нервы крепкие.",
                        f"Привет, {member.first_name}! Сразу предупреждаю - тут жестко."
                    ]
                    await message.reply(random.choice(fallback_welcomes))
                    
            except Exception:
                # Простое приветствие если что-то пошло не так
                await message.reply(f"Привет, {member.first_name}!")
    
    except Exception as e:
        print(f"Error handling new members: {e}")

@router.message(F.left_chat_member)
async def handle_left_member(message: Message):
    """Обработчик ушедших участников группы."""
    try:
        left_member = message.left_chat_member
        
        if not left_member or left_member.is_bot:
            return
        
        # Проверяем режим бота
        system_profile = db_load_person(message.chat.id, 0) or {}
        bot_mode = system_profile.get("bot_mode", "toxic")
        
        if bot_mode == "silent":
            return
        
        # Только 50% шанс отреагировать на уход
        if random.randint(1, 100) > 50:
            return
        
        try:
            farewell_prompt = f"Участник {left_member.first_name} покинул группу. Прокомментируй его уход в токсичном стиле."
            response = await llm_text(farewell_prompt, max_tokens=80)
            
            if response:
                await message.reply(response)
            else:
                # Fallback прощания
                fallback_farewells = [
                    f"Ну и пошел {left_member.first_name}. Слабак.",
                    f"Еще один не выдержал наших порядков.",
                    f"И туда ему дорога.",
                    f"Видимо, {left_member.first_name} оказался не готов к реальности."
                ]
                await message.reply(random.choice(fallback_farewells))
                
        except Exception:
            pass  # Просто молчим если что-то не так
    
    except Exception as e:
        print(f"Error handling left member: {e}")

@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=(
    "member", "restricted", "left", "kicked"
)))
async def handle_chat_member_update(update: ChatMemberUpdated):
    """Обработчик изменений статуса участников."""
    try:
        old_status = update.old_chat_member.status
        new_status = update.new_chat_member.status
        user = update.new_chat_member.user
        
        # Реагируем только на значимые изменения
        if old_status == "member" and new_status in ["left", "kicked"]:
            # Участник был удален/исключен
            print(f"User {user.first_name} was removed from chat {update.chat.id}")
            
        elif old_status in ["left", "kicked"] and new_status == "member":
            # Участник вернулся
            print(f"User {user.first_name} returned to chat {update.chat.id}")
            
    except Exception as e:
        print(f"Error handling chat member update: {e}")

# Обработчик для обнаружения неактивности
@router.message(F.text)
async def check_chat_activity(message: Message):
    """Проверяет активность чата и может инициировать разговор при затишье."""
    try:
        # Получаем последнюю активность
        last_activity = db_get_last_activity(message.chat.id)
        current_time = time.time()
        
        # Если прошло больше часа без активности бота
        if last_activity and (current_time - last_activity) > 3600:
            
            # Проверяем режим бота
            system_profile = db_load_person(message.chat.id, 0) or {}
            bot_mode = system_profile.get("bot_mode", "toxic")
            
            if bot_mode == "silent":
                return
            
            # 10% шанс "разбудить" чат
            if random.randint(1, 100) <= 10:
                
                idle_prompts = [
                    "Что-то тихо стало в чате. Все живы?",
                    "Засыпаете? А я тут скучаю.",
                    "Долго молчим. Что случилось?",
                    "Тишина... Подозрительно."
                ]
                
                try:
                    response = await llm_text(
                        "Чат был неактивен больше часа. Инициируй разговор в своем токсичном стиле.",
                        max_tokens=80
                    )
                    
                    if response:
                        await message.reply(response)
                    else:
                        await message.reply(random.choice(idle_prompts))
                        
                except Exception:
                    await message.reply(random.choice(idle_prompts))
    
    except Exception as e:
        print(f"Error checking chat activity: {e}")
