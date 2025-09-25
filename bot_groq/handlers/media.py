from aiogram import Router, F
from aiogram.types import Message, PhotoSize
import random
import time
import base64
import aiohttp
import tempfile
import os

from bot_groq.config.settings import settings
from bot_groq.services.database import db_add_chat_message, db_load_person, log_chat_event
from bot_groq.services.llm import llm_vision, llm_text
from bot_groq.core.profiles import update_person_profile

router = Router()

async def download_photo(photo: PhotoSize, bot) -> str:
    """Скачивает фото и возвращает путь к временному файлу."""
    try:
        # Получаем файл
        file = await bot.get_file(photo.file_id)
        
        # Создаем временный файл
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_path = temp_file.name
        temp_file.close()
        
        # Скачиваем файл
        file_url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    with open(temp_path, 'wb') as f:
                        f.write(await response.read())
                    return temp_path
                else:
                    os.unlink(temp_path)
                    return None
                    
    except Exception as e:
        print(f"Error downloading photo: {e}")
        return None

def cleanup_temp_file(file_path: str):
    """Удаляет временный файл."""
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
    except Exception:
        pass

@router.message(F.photo)
async def handle_photo(message: Message):
    """Обработчик фотографий."""
    try:
        # Сохраняем сообщение в базу
        log_chat_event(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            text=f"[ФОТО] {message.caption or ''}",
            timestamp=time.time(),
            is_bot=False
        )
        
        # Обновляем профиль пользователя
        bot_info = await message.bot.get_me()
        update_person_profile(message, bot_info.username)
        
        # Проверяем режим бота
        system_profile = db_load_person(message.chat.id, 0) or {}
        bot_mode = system_profile.get("bot_mode", "toxic")
        
        if bot_mode == "silent":
            return
        
        # Определяем, нужно ли анализировать фото
        should_analyze = False
        reason = ""  # для логирования

        if message.chat.type == "private":
            should_analyze = True
            reason = "private"
        elif message.caption and f"@{bot_info.username}" in message.caption.lower():
            should_analyze = True; reason = "mention"
        elif message.caption and any(keyword.lower() in message.caption.lower() for keyword in settings.name_keywords_list):
            should_analyze = True; reason = "keyword"
        elif random.randint(1, 100) <= max(1, settings.response_chance // 2):
            should_analyze = True; reason = "random"

        if not should_analyze:
            if settings.debug:
                print(f"[vision] skip photo chat={message.chat.id} reason=no_trigger caption={message.caption!r}")
            return
        else:
            if settings.debug:
                print(f"[vision] analyze photo chat={message.chat.id} reason={reason} caption={message.caption!r}")
        
        # Анализируем фото
        photo = message.photo[-1]  # Берем самое большое разрешение
        temp_file_path = await download_photo(photo, message.bot)
        
        if not temp_file_path:
            await message.reply("Не могу скачать фото для анализа.")
            return
        
        try:
            # Строим промпт – добавляем последние текстовые сообщения как фон (до 5)
            from bot_groq.services.database import db_get_chat_tail
            tail = db_get_chat_tail(message.chat.id, limit=8)
            last_texts = []
            for h in tail[-8:]:
                c = h.get('content')
                if not c or c.startswith('[ФОТО]'):
                    continue
                last_texts.append(c[:120])
                if len(last_texts) >= 5:
                    break
            context_snip = (" | ".join(last_texts)) if last_texts else "ничего полезного"

            vision_prompt = (
                "Ты видишь новое фото в чате. Опиши СУТЬ максимально колко и едко."
                " Если на фото документы/текст – НЕ переписывай полностью, просто съязви."
                f" Контекст последних сообщений: {context_snip}."
            )
            if message.caption:
                vision_prompt += f" Пользователь добавил подпись: '{message.caption[:150]}'"

            # Превращаем локальный файл в data URL (Groq поддерживает image_url с URL. data: может быть не поддержан – если не сработает, останется fallback на путь)
            data_url = None
            try:
                with open(temp_file_path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode('ascii')
                    data_url = f"data:image/jpeg;base64,{b64}"
            except Exception:
                pass

            image_ref = data_url or temp_file_path

            response = llm_vision(
                system_prompt="Ты токсично комментируешь фотографии. Пиши по-русски, язвительно, коротко.",
                image_url=image_ref,
                user_prompt=vision_prompt
            )
            
            if response:
                await message.reply(response)
                
                # Сохраняем ответ бота
                log_chat_event(
                    chat_id=message.chat.id,
                    user_id=bot_info.id,
                    username=bot_info.username,
                    text=response,
                    timestamp=time.time(),
                    is_bot=True
                )
            else:
                # Fallback ответы на фото
                photo_responses = [
                    "Интересное фото. Что хотел показать?",
                    "Вижу картинку, но что это должно означать?",
                    "Фотка зачетная, но смысл?",
                    "И что мне с этим делать?",
                    "Красиво. И что дальше?"
                ]
                await message.reply(random.choice(photo_responses))
                
        finally:
            cleanup_temp_file(temp_file_path)
    
    except Exception as e:
        print(f"Error handling photo: {e}")

@router.message(F.sticker)
async def handle_sticker(message: Message):
    """Обработчик стикеров."""
    try:
        # Сохраняем в базу
        log_chat_event(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            text=f"[СТИКЕР] {message.sticker.emoji if message.sticker.emoji else ''}",
            timestamp=time.time(),
            is_bot=False
        )
        
        # Обновляем профиль пользователя  
        bot_info = await message.bot.get_me()
        update_person_profile(message, bot_info.username)
        
        # Проверяем режим бота
        system_profile = db_load_person(message.chat.id, 0) or {}
        bot_mode = system_profile.get("bot_mode", "toxic")
        
        if bot_mode == "silent":
            return
        
        # Реагируем на стикеры реже
        if random.randint(1, 100) <= 15:  # 15% шанс
            
            emoji = message.sticker.emoji or "🤔"
            sticker_set = message.sticker.set_name or "unknown"
            
            try:
                sticker_prompt = f"Пользователь отправил стикер с эмодзи {emoji}. Прокомментируй это в токсичном стиле."
                response = await llm_text(sticker_prompt, max_tokens=0)
                
                if response:
                    await message.reply(response)
                else:
                    # Fallback ответы на стикеры
                    sticker_responses = [
                        "Стикер говорит сам за себя.",
                        "Картинка стоит тысячи слов. Но не этот стикер.",
                        "Эмоции через стикеры? Оригинально.",
                        "Понятно, без слов.",
                        f"Хороший стикер с {emoji}"
                    ]
                    await message.reply(random.choice(sticker_responses))
                    
            except Exception:
                pass  # Просто игнорируем если что-то не так
    
    except Exception as e:
        print(f"Error handling sticker: {e}")

@router.message(F.animation)
async def handle_gif(message: Message):
    """Обработчик GIF-анимаций."""
    try:
        # Сохраняем в базу
        log_chat_event(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            text=f"[GIF] {message.caption or ''}",
            timestamp=time.time(),
            is_bot=False
        )
        
        # Обновляем профиль пользователя
        bot_info = await message.bot.get_me()
        update_person_profile(message, bot_info.username)
        
        # Проверяем режим бота
        system_profile = db_load_person(message.chat.id, 0) or {}
        bot_mode = system_profile.get("bot_mode", "toxic")
        
        if bot_mode == "silent":
            return
        
        # Реагируем на GIF еще реже
        if random.randint(1, 100) <= 10:  # 10% шанс
            
            try:
                gif_prompt = "Пользователь отправил GIF-анимацию"
                if message.caption:
                    gif_prompt += f" с подписью '{message.caption}'"
                gif_prompt += ". Прокомментируй это саркастично."
                
                response = await llm_text(gif_prompt, max_tokens=0)
                
                if response:
                    await message.reply(response)
                else:
                    # Fallback ответы на GIF
                    gif_responses = [
                        "Анимация зачетная.",
                        "GIF в тему.",
                        "Движущиеся картинки - это современно.",
                        "Хорошая реакция в GIF формате.",
                        "Понятно без слов."
                    ]
                    await message.reply(random.choice(gif_responses))
                    
            except Exception:
                pass
    
    except Exception as e:
        print(f"Error handling GIF: {e}")

@router.message(F.video)
async def handle_video(message: Message):
    """Обработчик видео."""
    try:
        # Сохраняем в базу
        log_chat_event(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            text=f"[ВИДЕО] {message.caption or ''}",
            timestamp=time.time(),
            is_bot=False
        )
        
        # Обновляем профиль пользователя
        bot_info = await message.bot.get_me()
        update_person_profile(message, bot_info.username)
        
        # Проверяем режим бота
        system_profile = db_load_person(message.chat.id, 0) or {}
        bot_mode = system_profile.get("bot_mode", "toxic")
        
        if bot_mode == "silent":
            return
        
        # Реагируем на видео редко
        if random.randint(1, 100) <= 8:  # 8% шанс
            
            try:
                video_prompt = "Пользователь отправил видео"
                if message.caption:
                    video_prompt += f" с подписью '{message.caption}'"
                video_prompt += ". Прокомментируй это в токсичном стиле."
                
                response = await llm_text(video_prompt, max_tokens=80)
                
                if response:
                    await message.reply(response) 
                else:
                    # Fallback ответы на видео
                    video_responses = [
                        "Видос интересный.",
                        "Кино смотрим?",
                        "Что за фильм прислал?",
                        "Видео в тему или просто так?",
                        "Надо будет посмотреть когда время будет."
                    ]
                    await message.reply(random.choice(video_responses))
                    
            except Exception:
                pass
    
    except Exception as e:
        print(f"Error handling video: {e}")

@router.message(F.voice)
async def handle_voice(message: Message):
    """Обработчик голосовых сообщений."""
    try:
        # Сохраняем в базу
        log_chat_event(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            text=f"[ГОЛОСОВОЕ СООБЩЕНИЕ] Длительность: {message.voice.duration}с",
            timestamp=time.time(),
            is_bot=False
        )
        
        # Обновляем профиль пользователя
        bot_info = await message.bot.get_me()
        update_person_profile(message, bot_info.username)
        
        # Проверяем режим бота
        system_profile = db_load_person(message.chat.id, 0) or {}
        bot_mode = system_profile.get("bot_mode", "toxic")
        
        if bot_mode == "silent":
            return
        
        # Реагируем на войсы редко
        if random.randint(1, 100) <= 12:  # 12% шанс
            
            duration = message.voice.duration
            
            try:
                voice_prompt = f"Пользователь отправил голосовое сообщение длительностью {duration} секунд. Прокомментируй это саркастично."
                response = await llm_text(voice_prompt, max_tokens=80)
                
                if response:
                    await message.reply(response)
                else:
                    # Fallback ответы на войсы
                    if duration < 10:
                        voice_responses = [
                            "Короткий войс - хорошо, не люблю длинные речи.",
                            "Быстро и по делу.",
                            "Коротко и ясно."
                        ]
                    elif duration > 60:
                        voice_responses = [
                            "Долго говоришь. Надеюсь, там что-то важное.",
                            "Целая лекция в войсе.",
                            "Много слов. Надо будет послушать когда время будет."
                        ]
                    else:
                        voice_responses = [
                            "Войс принят.",
                            "Голосовое сообщение получено.",
                            "Буду слушать.",
                            "Интересно, что там наговорил."
                        ]
                    
                    await message.reply(random.choice(voice_responses))
                    
            except Exception:
                pass
    
    except Exception as e:
        print(f"Error handling voice: {e}")

@router.message(F.document)
async def handle_document(message: Message):
    """Обработчик документов."""
    try:
        # Сохраняем в базу
        doc_name = message.document.file_name or "unknown"
        doc_size = message.document.file_size or 0
        
        log_chat_event(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            text=f"[ДОКУМЕНТ] {doc_name} ({doc_size} байт) {message.caption or ''}",
            timestamp=time.time(),
            is_bot=False
        )
        
        # Обновляем профиль пользователя
        bot_info = await message.bot.get_me()
        update_person_profile(message, bot_info.username)
        
        # Проверяем режим бота
        system_profile = db_load_person(message.chat.id, 0) or {}
        bot_mode = system_profile.get("bot_mode", "toxic")
        
        if bot_mode == "silent":
            return
        
        # Реагируем на документы редко
        if random.randint(1, 100) <= 5:  # 5% шанс
            
            try:
                doc_prompt = f"Пользователь отправил документ '{doc_name}'"
                if message.caption:
                    doc_prompt += f" с подписью '{message.caption}'"
                doc_prompt += ". Прокомментируй это в токсичном стиле."
                
                response = await llm_text(doc_prompt, max_tokens=80)
                
                if response:
                    await message.reply(response)
                else:
                    # Fallback ответы на документы
                    doc_responses = [
                        "Документик интересный.",
                        "Что за файл прислал?",
                        "Буду изучать на досуге.",
                        "Документы - это серьезно.",
                        "Надеюсь, там что-то полезное."
                    ]
                    await message.reply(random.choice(doc_responses))
                    
            except Exception:
                pass
    
    except Exception as e:
        print(f"Error handling document: {e}")
