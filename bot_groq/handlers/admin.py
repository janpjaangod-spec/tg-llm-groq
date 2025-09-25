from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
import json
import time
from typing import List

from bot_groq.config.settings import settings
from bot_groq.services.database import (
    db_get_chat_tail, db_clear_history, db_get_group_stats,
    db_load_person, db_save_person, db_get_all_groups,
    db_get_settings, db_set_system_prompt,
    db_runtime_set, db_runtime_get, db_runtime_all, db_runtime_delete
)
from bot_groq.core.profiles import get_user_profile_for_display
from bot_groq.core.relations import analyze_group_dynamics, get_group_tension_points
from bot_groq.config import reload_settings as _reload_settings
from bot_groq.services.database import db_set_model, db_get_settings as _db_get_settings_for_reload

router = Router()

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    # Используем поле admin_ids из настроек (множество int)
    return user_id in settings.admin_ids

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Показывает статистику группы (только для админов)."""
    if not is_admin(message.from_user.id):
        await message.reply("🚫 Команда доступна только администраторам")
        return
    
    try:
        # Базовая статистика из БД
        stats = db_get_group_stats(message.chat.id)
        
        # Динамика группы
        dynamics = analyze_group_dynamics(message.chat.id, limit=200)
        
        # Точки напряжения
        tensions = get_group_tension_points(message.chat.id)
        
        text_parts = [
            f"📊 <b>Статистика чата</b>",
            f"",
            f"💬 Всего сообщений: {stats.get('total_messages', 0)}",
            f"👥 Активных пользователей: {dynamics.get('active_users', 0)}",
            f"📈 Средняя активность: {dynamics.get('avg_activity', 0):.1f} сообщений/пользователь",
        ]
        
        # Топ активных пользователей
        if dynamics.get('most_active'):
            text_parts.append(f"\n🏆 <b>Самые активные:</b>")
            for i, (user_id, count) in enumerate(dynamics['most_active'][:5], 1):
                try:
                    member = await message.bot.get_chat_member(message.chat.id, user_id)
                    name = member.user.first_name or f"User_{user_id}"
                    text_parts.append(f"{i}. {name}: {count} сообщений")
                except:
                    text_parts.append(f"{i}. User_{user_id}: {count} сообщений")
        
        # Молчуны
        if dynamics.get('silent_users'):
            text_parts.append(f"\n😶 Молчунов: {len(dynamics['silent_users'])}")
        
        # Точки напряжения
        if tensions:
            text_parts.append(f"\n⚠️ <b>Точки напряжения:</b>")
            for tension in tensions[:3]:
                text_parts.append(f"• {tension}")
        
        await message.reply("\n".join(text_parts), parse_mode="HTML")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка получения статистики: {str(e)}")

@router.message(Command("who"))
async def cmd_who(message: Message):
    """Показывает профиль пользователя (только для админов)."""
    if not is_admin(message.from_user.id):
        await message.reply("🚫 Команда доступна только администраторам")
        return
    
    try:
        target_user = None
        
        # Определяем целевого пользователя
        if message.reply_to_message:
            target_user = message.reply_to_message.from_user
        else:
            # Ищем упоминание пользователя в тексте
            if message.entities:
                for entity in message.entities:
                    if entity.type == "mention":
                        username = message.text[entity.offset+1:entity.offset+entity.length]
                        try:
                            chat_member = await message.bot.get_chat_member(
                                message.chat.id, 
                                f"@{username}"
                            )
                            target_user = chat_member.user
                            break
                        except:
                            continue
        
        if not target_user:
            await message.reply("❓ Укажите пользователя через реплай или @упоминание")
            return
        
        # Получаем профиль
        profile = get_user_profile_for_display(
            message.chat.id, 
            target_user.id, 
            target_user
        )
        
        text_parts = [
            f"👤 <b>Досье на пользователя</b>",
            f"",
            f"📝 Имя: {profile['name']}",
            f"💬 Обращается: {profile['call']}",
            f"❤️ Любит: {profile['likes']}",
            f"💔 Не любит: {profile['dislikes']}",
            f"🎭 Отношение к боту: {profile['tone']}",
        ]
        
        # Дополнительная информация из сырого профиля
        raw_profile = db_load_person(message.chat.id, target_user.id)
        if raw_profile:
            if raw_profile.get('spice', 0) > 1:
                text_parts.append(f"🌶️ Токсичность: {raw_profile['spice']}/3")
            
            if raw_profile.get('notes'):
                text_parts.append(f"📋 Заметки: {'; '.join(raw_profile['notes'][-3:])}")
        
        await message.reply("\n".join(text_parts), parse_mode="HTML")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка получения профиля: {str(e)}")

@router.message(Command("clear_history"))
async def cmd_clear_history(message: Message):
    """Очищает историю сообщений (только для главного админа)."""
    # Главным админом считаем первого в отсортированном списке admin_ids
    primary_admin = next(iter(sorted(settings.admin_ids))) if settings.admin_ids else None
    if message.from_user.id != primary_admin:
        await message.reply("🚫 Команда доступна только главному администратору")
        return
    
    try:
        # Получаем количество для подтверждения
        current_count = len(db_get_chat_tail(message.chat.id, limit=10000))
        
        # Очищаем историю
        db_clear_history(message.chat.id)
        
        await message.reply(
            f"🗑️ Очищена история сообщений\n"
            f"Удалено записей: {current_count}"
        )
        
    except Exception as e:
        await message.reply(f"❌ Ошибка очистки истории: {str(e)}")

@router.message(Command("export_data"))
async def cmd_export_data(message: Message):
    """Экспортирует данные чата (только для главного админа)."""
    primary_admin = next(iter(sorted(settings.admin_ids))) if settings.admin_ids else None
    if message.from_user.id != primary_admin:
        await message.reply("🚫 Команда доступна только главному администратору")
        return
    
    try:
        # Собираем данные для экспорта
        export_data = {
            "chat_id": message.chat.id,
            "export_time": time.time(),
            "messages": db_get_chat_tail(message.chat.id, limit=1000),
            "stats": db_get_group_stats(message.chat.id),
            "dynamics": analyze_group_dynamics(message.chat.id),
            "tensions": get_group_tension_points(message.chat.id)
        }
        
        # Конвертируем в JSON
        json_data = json.dumps(export_data, ensure_ascii=False, indent=2)
        
        # Сохраняем во временный файл и отправляем
        filename = f"chat_export_{message.chat.id}_{int(time.time())}.json"
        
        await message.reply_document(
            document=json_data.encode('utf-8'),
            filename=filename,
            caption="📦 Экспорт данных чата"
        )
        
    except Exception as e:
        await message.reply(f"❌ Ошибка экспорта данных: {str(e)}")

@router.message(Command("global_stats"))
async def cmd_global_stats(message: Message):
    """Показывает глобальную статистику по всем чатам (только для главного админа)."""
    primary_admin = next(iter(sorted(settings.admin_ids))) if settings.admin_ids else None
    if message.from_user.id != primary_admin:
        await message.reply("🚫 Команда доступна только главному администратору")
        return
    
    try:
        # Получаем список всех групп
        groups = db_get_all_groups()
        
        total_messages = 0
        total_users = 0
        active_groups = 0
        
        group_details = []
        
        for group_data in groups:
            chat_id = group_data.get('chat_id')
            if not chat_id:
                continue
                
            stats = db_get_group_stats(chat_id)
            dynamics = analyze_group_dynamics(chat_id, limit=100)
            
            messages = stats.get('total_messages', 0)
            users = dynamics.get('active_users', 0)
            
            total_messages += messages
            total_users += users
            
            if messages > 10:  # считаем активными группы с >10 сообщений
                active_groups += 1
                
            # Получаем название группы
            try:
                chat = await message.bot.get_chat(chat_id)
                chat_name = chat.title or f"Chat {chat_id}"
            except:
                chat_name = f"Chat {chat_id}"
                
            group_details.append({
                'name': chat_name,
                'messages': messages,
                'users': users
            })
        
        # Сортируем по активности
        group_details.sort(key=lambda x: x['messages'], reverse=True)
        
        text_parts = [
            f"🌍 <b>Глобальная статистика</b>",
            f"",
            f"📊 Всего групп: {len(groups)}",
            f"✅ Активных групп: {active_groups}",  
            f"💬 Всего сообщений: {total_messages}",
            f"👥 Всего пользователей: {total_users}"
        ]
        
        if group_details:
            text_parts.append(f"\n🏆 <b>Топ групп по активности:</b>")
            for i, group in enumerate(group_details[:5], 1):
                text_parts.append(
                    f"{i}. {group['name']}: {group['messages']} сообщений, "
                    f"{group['users']} пользователей"
                )
        
        await message.reply("\n".join(text_parts), parse_mode="HTML")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка получения глобальной статистики: {str(e)}")

@router.message(Command("set_mode"))
async def cmd_set_mode(message: Message):
    """Изменяет режим работы бота (только для админов)."""
    if not is_admin(message.from_user.id):
        await message.reply("🚫 Команда доступна только администраторам")
        return
    
    try:
        args = message.text.split()[1:] if len(message.text.split()) > 1 else []
        
        if not args:
            await message.reply(
                "⚙️ Доступные режимы:\n"
                "/set_mode toxic - токсичный режим\n"
                "/set_mode friendly - дружелюбный режим\n"
                "/set_mode neutral - нейтральный режим\n"
                "/set_mode silent - тихий режим (не реагирует на сообщения)"
            )
            return
        
        mode = args[0].lower()
        valid_modes = ["toxic", "friendly", "neutral", "silent"]
        
        if mode not in valid_modes:
            await message.reply(f"❌ Неизвестный режим. Доступные: {', '.join(valid_modes)}")
            return
        
        # Сохраняем режим в базу данных (используем системный профиль)
        system_profile = db_load_person(message.chat.id, 0) or {}
        system_profile["bot_mode"] = mode
        db_save_person(message.chat.id, 0, system_profile)
        
        mode_names = {
            "toxic": "🔥 Токсичный",
            "friendly": "😊 Дружелюбный", 
            "neutral": "😐 Нейтральный",
            "silent": "🤐 Тихий"
        }
        
        await message.reply(f"✅ Режим изменен на: {mode_names[mode]}")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка изменения режима: {str(e)}")

@router.message(Command("debug"))
async def cmd_debug(message: Message):
    """Показывает отладочную информацию (только для главного админа)."""
    primary_admin = next(iter(sorted(settings.admin_ids))) if settings.admin_ids else None
    if message.from_user.id != primary_admin:
        await message.reply("🚫 Команда доступна только главному администратору")
        return
    
    try:
        import sys
        import psutil
        import os
        
        # Информация о системе
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        text_parts = [
            f"🔧 <b>Отладочная информация</b>",
            f"",
            f"🐍 Python: {sys.version.split()[0]}",
            f"💾 Память: {memory_info.rss / 1024 / 1024:.1f} MB",
            f"⚡ CPU: {process.cpu_percent():.1f}%",
            f"🕐 Время работы: {int(time.time() - process.create_time())} сек",
            f"",
            f"⚙️ Настройки:",
            f"• Admin IDs: {len(settings.admin_ids)}",
            f"• Name keywords: {len(settings.name_keywords_list)}",
            f"• Groq model: {settings.groq_model}",
            f"• Response chance: {settings.response_chance}%"
        ]
        
        await message.reply("\n".join(text_parts), parse_mode="HTML")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка получения отладочной информации: {str(e)}")

@router.message(Command("reload_settings"))
async def cmd_reload_settings(message: Message):
    """Горячий reload переменных окружения (главный админ)."""
    primary_admin = next(iter(sorted(settings.admin_ids))) if settings.admin_ids else None
    if message.from_user.id != primary_admin:
        await message.reply("🚫 Только главный администратор")
        return
    try:
        old_model = settings.groq_model
        new_s = _reload_settings()
        # Применяем runtime overrides поверх env (мгновенно)
        overrides = db_runtime_all()
        for k,v in overrides.items():
            if hasattr(new_s, k):
                try:
                    casted = type(getattr(new_s,k))(v) if getattr(new_s,k) is not None else v
                    object.__setattr__(new_s, k, casted)
                except Exception:
                    object.__setattr__(new_s, k, v)
        model_note = ""
        try:
            db_cfg = _db_get_settings_for_reload()
            if db_cfg.get("model") != new_s.groq_model:
                db_set_model(new_s.groq_model)
                model_note = " (обновлена модель в БД)"
        except Exception as db_e:
            model_note = f" (не удалось синхронизировать модель: {db_e})"
        await message.reply(
            "🔄 Settings reloaded\n"
            f"Model: {old_model} → {new_s.groq_model}{model_note}\n"
            f"Chance={new_s.response_chance}% short={'on' if new_s.reply_short_mode else 'off'} overrides={len(overrides)}"
        )
    except Exception as e:
        await message.reply(f"❌ Reload error: {e}")

@router.message(Command("prompt"))
async def cmd_prompt(message: Message):
    """Просмотр / изменение системного промпта (админы). Использование:
    /prompt – показать текущий (усечённый)
    /prompt full – показать полностью (в личке, чтобы не засорять группу)
    /prompt set <текст> – установить новый
    /prompt reset – сбросить к дефолтному
    """
    if not is_admin(message.from_user.id):
        await message.reply("🚫 Только для админов")
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) == 1:  # просто /prompt
            from html import escape
            cfg = db_get_settings()
            sp = cfg.get("system_prompt", "")
            short_raw = (sp[:400] + "…") if len(sp) > 400 else sp
            short = escape(short_raw)
            text = (
                "🧠 <b>System prompt</b> (усечён):\n" + short +
                "\n\n/set_mode toxic|friendly|neutral|silent\n"+
                "Использование: /prompt full | /prompt set <текст> | /prompt reset"
            )
            try:
                await message.reply(text, parse_mode="HTML")
            except Exception:
                # Fallback без HTML
                await message.reply("System prompt (усечён):\n" + short_raw)
            return
        sub = parts[1].lower()
        if sub == "full":
            from html import escape
            cfg = db_get_settings()
            full = escape(cfg.get("system_prompt",""))
            try:
                await message.reply("🧠 <b>System prompt (full)</b>:\n" + full, parse_mode="HTML")
            except Exception:
                await message.reply("System prompt (full):\n" + cfg.get("system_prompt",""))
            return
        if sub == "reset":
            db_set_system_prompt(settings.default_system_prompt)
            await message.reply("♻️ System prompt сброшен к дефолтному")
            return
        if sub == "set":
            if len(parts) < 3:
                await message.reply("⚠️ Укажи текст: /prompt set <текст>")
                return
            new_text = parts[2].strip()
            db_set_system_prompt(new_text)
            # runtime override тоже кладём
            db_runtime_set("system_prompt", new_text)
            await message.reply(f"✅ System prompt обновлён. Длина: {len(new_text)}")
            return
        await message.reply("❓ Неизвестная подкоманда. /prompt | full | set | reset")
    except Exception as e:
        await message.reply(f"❌ Ошибка prompt: {e}")

@router.message(Command("forget_user"))
async def cmd_forget_user(message: Message):
    """Забыть пользователя (admin). Использовать реплаем на его сообщение."""
    if not is_admin(message.from_user.id):
        await message.reply("🚫 Только для админов")
        return
    try:
        if not message.reply_to_message:
            await message.reply("Ответь этой командой на сообщение пользователя, которого нужно забыть.")
            return
        target = message.reply_to_message.from_user
        if target.is_bot:
            await message.reply("🤖 Это бот, пропускаю.")
            return
        db_save_person(message.chat.id, target.id, {})
        await message.reply(f"🧼 Память о {target.first_name} очищена.")
    except Exception as e:
        await message.reply(f"❌ Ошибка forget_user: {e}")

@router.message(Command("set"))
async def cmd_set_var(message: Message):
    """/set KEY VALUE — runtime override (админ). Сохраняется в БД и применяется при reload автоматически."""
    if not is_admin(message.from_user.id):
        return
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 3:
            await message.reply("Использование: /set ключ значение")
            return
        key, value = parts[1], parts[2]
        db_runtime_set(key, value)
        await message.reply(f"✅ override сохранён: {key}={value}")
    except Exception as e:
        await message.reply(f"❌ set error: {e}")

@router.message(Command("get"))
async def cmd_get_var(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("Использование: /get ключ")
            return
        key = parts[1]
        val = db_runtime_get(key)
        if val is None:
            await message.reply("(нет override)" )
        else:
            await message.reply(f"{key}={val}")
    except Exception as e:
        await message.reply(f"❌ get error: {e}")

@router.message(Command("vars"))
async def cmd_vars(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        allv = db_runtime_all()
        if not allv:
            await message.reply("Нет runtime overrides")
            return
        lines = [f"{k}={v}" for k,v in sorted(allv.items())]
        await message.reply("Overrides:\n"+"\n".join(lines))
    except Exception as e:
        await message.reply(f"❌ vars error: {e}")

@router.message(Command("unset"))
async def cmd_unset(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply("Использование: /unset ключ")
            return
        key = parts[1].strip()
        db_runtime_delete(key)
        await message.reply(f"🧹 override удалён: {key}")
    except Exception as e:
        await message.reply(f"❌ unset error: {e}")

@router.message(Command("admin_help"))
async def cmd_admin_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    cmds = [
        "/reload_settings","/prompt","/prompt full","/prompt set <txt>",
        "/set k v","/get k","/vars","/unset k",
        "/who","/stats","/global_stats","/clear_history","/export_data",
        "/set_mode <mode>","/debug","/forget_user (reply)"
    ]
    await message.reply("Админ команды:\n" + "\n".join(cmds))

@router.message(Command("model"))
async def cmd_model(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) == 1:
        from bot_groq.services.database import db_get_settings
        cur = db_get_settings().get("model")
        await message.reply(f"Текущая модель: {cur}\nИспользуй: /model <name>")
        return
    new_name = parts[1].strip()
    from bot_groq.services.llm import _normalize_model
    norm = _normalize_model(new_name)
    from bot_groq.services.database import db_set_model, db_runtime_set
    from bot_groq.services.database import db_get_settings as _gs
    prev = _gs().get("model")
    db_set_model(norm)
    db_runtime_set("groq_model", norm)
    if norm != new_name.strip():
        await message.reply(f"⚠️ '{new_name}' не распознана → '{norm}' (prev {prev}). /models для списка.")
    else:
        await message.reply(f"✅ Модель: {prev} → {norm}")

@router.message(Command("models"))
async def cmd_models(message: Message):
    if not is_admin(message.from_user.id):
        return
    from bot_groq.services.llm import list_models
    from bot_groq.services.database import db_get_settings
    cur = db_get_settings().get("model")
    models = list_models()
    lines = ["Доступные модели (известные слоги):"]
    for m in models:
        mark = "✅" if m == cur else "•"
        lines.append(f"{mark} {m}")
    await message.reply("\n".join(lines))
