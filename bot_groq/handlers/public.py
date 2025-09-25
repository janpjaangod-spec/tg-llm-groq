from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
import random
import time

from bot_groq.config.settings import settings
from bot_groq.services.database import db_load_person, db_save_person, db_get_chat_tail
from bot_groq.services.llm import llm_text
from bot_groq.core.profiles import get_user_profile_for_display

router = Router()

@router.message(Command("start", "help"))
async def cmd_help(message: Message):
    """Показывает справку по командам."""
    if message.chat.type == "private":
        # В приватном чате - полная справка
        text = (
            "🤖 <b>Леха - твой токсичный друг</b>\n\n"
            "Я умею:\n"
            "• Общаться в групповых чатах\n"
            "• Запоминать информацию о пользователях\n"
            "• Анализировать фото и изображения\n"
            "• Быть токсичным (но в меру)\n\n"
            "Команды:\n"
            "/help - эта справка\n"  
            "/info - информация обо мне\n"
            "/forget - забыть информацию о тебе\n\n"
            "Добавь меня в группу и я начну общаться!"
        )
    else:
        # В группе - краткая справка
        responses = [
            "Чё надо? Я тут общаюсь с нормальными людьми.",
            "Справка? Лучше спроси что-то по делу.",
            "Команды? Просто пиши нормально, я пойму.",
            "Помощь? Сам себе помоги сначала."
        ]
        text = random.choice(responses)
    
    await message.reply(text, parse_mode="HTML" if message.chat.type == "private" else None)

@router.message(Command("info"))
async def cmd_info(message: Message):
    """Показывает информацию о боте."""
    responses = [
        "Я Леха, местный токсичный бот. Люблю поспорить и подколоть.",
        "Леха на связи. Готов обсудить всё что угодно, но предупреждаю - я не сахарный.",
        "Бот Леха, версия 'злой язык'. Общаюсь как есть, без прикрас.",
        "Токсичный Леха к вашим услугам. Если нужен политкорректный бот - вам не сюда."
    ]
    
    await message.reply(random.choice(responses))

@router.message(Command("forget"))
async def cmd_forget(message: Message):
    """Позволяет пользователю удалить свой профиль."""
    try:
        # Загружаем текущий профиль
        profile = db_load_person(message.chat.id, message.from_user.id)
        
        if not profile:
            responses = [
                "Да я тебя и так не помню особо.",
                "Забыть тебя? Так ты уже никто для меня.",
                "Какую информацию забыть? У меня про тебя и так пусто."
            ]
            await message.reply(random.choice(responses))
            return
        
        # Очищаем профиль (сохраняем пустой)
        empty_profile = {}
        db_save_person(message.chat.id, message.from_user.id, empty_profile)
        
        responses = [
            "Готово, стёр тебя из памяти. Теперь мы не знакомы.",
            "Забыл. Хотя честно говоря, запоминать особо нечего было.",
            "Информация удалена. Начинаем знакомство с чистого листа.",
            "Всё стёрто. Теперь ты для меня просто очередной анон."
        ]
        
        await message.reply(random.choice(responses))
        
    except Exception as e:
        await message.reply("Что-то пошло не так при удалении данных.")

@router.message(Command("me"))
async def cmd_me(message: Message):
    """Показывает профиль пользователя (упрощенная версия /who)."""
    if message.chat.type == "private":
        await message.reply("В личных сообщениях я профили не веду.")
        return
    
    try:
        profile = get_user_profile_for_display(
            message.chat.id,
            message.from_user.id, 
            message.from_user
        )
        
        if not any(profile.values()):
            responses = [
                "Пока про тебя знаю немного. Пообщаемся - узнаю больше.",
                "Ты для меня пока загадка. Расскажи что-нибудь о себе.",
                "Информации маловато. Давай знакомиться!"
            ]
            await message.reply(random.choice(responses))
            return
        
        text_parts = []
        
        if profile.get('name'):
            text_parts.append(f"Зову тебя: {profile['name']}")
        
        if profile.get('likes') and profile['likes'] != "—":
            text_parts.append(f"Любишь: {profile['likes']}")
            
        if profile.get('dislikes') and profile['dislikes'] != "—":
            text_parts.append(f"Не любишь: {profile['dislikes']}")
        
        if profile.get('tone'):
            tone_desc = {
                "дружелюбно": "дружески",
                "колко": "с подковыркой", 
                "нейтрально": "без особых эмоций"
            }
            text_parts.append(f"Ко мне относишься {tone_desc.get(profile['tone'], profile['tone'])}")
        
        if text_parts:
            response = "Вот что я про тебя помню:\n" + "\n".join([f"• {part}" for part in text_parts])
        else:
            response = "Пока про тебя ничего интересного не знаю."
        
        await message.reply(response)
        
    except Exception as e:
        await message.reply("Ошибка при получении твоего профиля.")

@router.message(Command("mood"))
async def cmd_mood(message: Message):
    """Показывает настроение бота."""
    # Получаем режим бота из системного профиля
    system_profile = db_load_person(message.chat.id, 0) or {}
    bot_mode = system_profile.get("bot_mode", "toxic")
    
    mood_responses = {
        "toxic": [
            "Настроение? Отличное! Готов кого-нибудь потроллить.",
            "Сегодня особенно язвительный. Берегитесь!",
            "В ударе! Шутки будут особенно колкими.",
            "Настроение боевое. Кто хочет поспорить?"
        ],
        "friendly": [
            "Настроение прекрасное! Готов помочь и поболтать.",
            "Сегодня добрый день, хочется всех обнять!",
            "Позитивно настроен! Давайте общаться.",
            "Хорошее настроение! Есть вопросы?"
        ],
        "neutral": [
            "Настроение нормальное. Работаю в штатном режиме.",
            "Обычное состояние. Ни хорошо, ни плохо.",
            "Стабильно. Готов к общению.",
            "Нейтрально настроен. Что обсуждаем?"
        ],
        "silent": [
            "...",
            "Тс-с-с.",
            "Режим тишины.",
            "*молчит*"
        ]
    }
    
    responses = mood_responses.get(bot_mode, mood_responses["toxic"])
    await message.reply(random.choice(responses))

@router.message(Command("ask"))
async def cmd_ask(message: Message):
    """Задать прямой вопрос боту."""
    try:
        # Извлекаем вопрос из команды
        question = message.text[4:].strip() if len(message.text) > 4 else ""
        
        if not question:
            responses = [
                "А вопрос где? Не телепат же я.",
                "Задай вопрос после команды, гений.",
                "Что спросить хотел? Используй: /ask твой вопрос"
            ]
            await message.reply(random.choice(responses))
            return
        
        # Генерируем ответ через LLM
        prompt = f"Пользователь спрашивает: {question}\nОтветь в своем токсичном стиле, но по существу."
        
        response = await llm_text(prompt, max_tokens=150)
        
        if response:
            await message.reply(response)
        else:
            await message.reply("Хм, что-то я завис. Попробуй переформулировать вопрос.")
            
    except Exception as e:
        await message.reply("Ошибка при обработке вопроса. Попробуй позже.")

@router.message(Command("random"))
async def cmd_random(message: Message):
    """Случайная фраза от бота."""
    random_phrases = [
        "Жизнь - штука интересная, но недолгая.",
        "Лучший способ предсказать будущее - это создать его. Или разрушить настоящее.",
        "Оптимист видит стакан наполовину полным. Пессимист - наполовину пустым. Реалист просто пьет.",
        "Если не можешь их победить - присоединяйся. Если не можешь присоединиться - троль их.",
        "Счастье не в деньгах, а в их количестве.",
        "Идеальных людей нет. Есть только те, кто еще не показал свою сущность.",
        "Сарказм - это способ дарить людям мудрость бесплатно.",
        "Иногда лучше молчать и показаться дураком, чем заговорить и развеять сомнения.",
        "Критика - это когда тебе говорят правду, которую ты не хочешь слышать.",
        "Не все герои носят плащи. Некоторые просто говорят неудобную правду."
    ]
    
    await message.reply(random.choice(random_phrases))

@router.message(Command("stats"))
async def cmd_stats_public(message: Message):
    """Публичная версия статистики (ограниченная)."""
    try:
        # Получаем только базовую статистику
        history = db_get_chat_tail(message.chat.id, limit=100)
        
        if not history:
            await message.reply("Статистики пока нет, слишком мало сообщений.")
            return
        
        total_messages = len(history)
        unique_users = len(set(msg.get('user_id') for msg in history if msg.get('user_id')))
        
        # Простая статистика активности за последние дни
        current_time = time.time()
        day_ago = current_time - 24 * 3600
        week_ago = current_time - 7 * 24 * 3600
        
        day_messages = len([m for m in history if m.get('timestamp', 0) > day_ago])
        week_messages = len([m for m in history if m.get('timestamp', 0) > week_ago])
        
        text = (
            f"📊 Краткая статистика чата:\n"
            f"💬 Сообщений (последние 100): {total_messages}\n"
            f"👥 Уникальных пользователей: {unique_users}\n"
            f"📅 За последний день: {day_messages}\n"
            f"📈 За последнюю неделю: {week_messages}"
        )
        
        await message.reply(text)
        
    except Exception as e:
        await message.reply("Ошибка при получении статистики.")

# Обработчик упоминаний бота
@router.message(F.text.contains("@") | F.text.contains("леха") | F.text.contains("лёха"))
async def handle_mentions(message: Message):
    """Обрабатывает упоминания бота в сообщениях."""
    if message.chat.type == "private":
        return  # В приватных чатах не нужно
    
    text = (message.text or "").lower()
    bot_username = (await message.bot.get_me()).username
    
    # Проверяем, упоминают ли бота
    mentioned = False
    
    if f"@{bot_username}" in text:
        mentioned = True
    elif any(keyword in text for keyword in ["леха", "лёха", "бот"]):
        mentioned = True
    
    if not mentioned:
        return
    
    # Проверяем режим бота
    system_profile = db_load_person(message.chat.id, 0) or {}
    bot_mode = system_profile.get("bot_mode", "toxic")
    
    if bot_mode == "silent":
        return  # В тихом режиме не отвечаем на упоминания
    
    try:
        # Генерируем ответ на упоминание
        prompt = f"Тебя упомянули в сообщении: '{message.text}'\nОтветь коротко в своем стиле."
        
        response = await llm_text(prompt, max_tokens=100)
        
        if response:
            await message.reply(response)
            
    except Exception:
        # Если LLM не работает, используем заготовленные ответы
        mention_responses = [
            "Что хотел?",
            "Слушаю.",
            "Да, я тут.",
            "Чё надо?",
            "Зову - отвечаю."
        ]
        await message.reply(random.choice(mention_responses))
