#!/usr/bin/env python3
"""
Telegram Bot Леха - Главный файл запуска
Модульная архитектура с разделением обязанностей
"""

import asyncio
import logging
import sys
from contextlib import suppress
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeDefault,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
)

# Импорты наших модулей
from bot_groq.config import settings
from bot_groq.services import initialize_database
from bot_groq.services.database import db_get_settings, db_set_model
from bot_groq.handlers import routers
from bot_groq.tasks.idle_chime import idle_chime_worker

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def create_bot() -> Bot:
    """Создает экземпляр бота с настройками."""
    return Bot(
        token=settings.telegram_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True
        )
    )

def create_dispatcher() -> Dispatcher:
    """Создает диспетчер и регистрирует обработчики."""
    dp = Dispatcher()
    
    # Регистрируем роутеры в порядке приоритета
    for router in routers:
        dp.include_router(router)
    
    return dp

async def startup_message(bot: Bot):
    """Отправляет сообщение о запуске админам."""
    try:
        bot_info = await bot.get_me()
        startup_text = (
            f"🚀 Бот запущен успешно!\n"
            f"👤 Имя: {bot_info.first_name}\n"
            f"🆔 ID: {bot_info.id}\n"
            f"📝 Username: @{bot_info.username}\n"
            f"⚙️ Режим: {'DEBUG' if settings.debug else 'PRODUCTION'}\n"
            f"📊 Groq модель: {settings.groq_model}\n"
            f"🎲 Шанс ответа: {settings.response_chance}%"
        )
        
        # Отправляем админам
        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(admin_id, startup_text)
            except Exception as e:
                logger.warning(f"Не удалось отправить стартовое сообщение админу {admin_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка при отправке стартового сообщения: {e}")

async def shutdown_message(bot: Bot):
    """Отправляет сообщение о завершении работы админам."""
    try:
        shutdown_text = "🛑 Бот завершает работу..."
        
        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(admin_id, shutdown_text)
            except Exception as e:
                logger.warning(f"Не удалось отправить сообщение о завершении админу {admin_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения о завершении: {e}")

_bg_tasks = []  # хранение ссылок на фоновые таски

async def on_startup(bot: Bot):
    """Обработчик запуска бота."""
    logger.info("🚀 Запуск бота...")
    
    # Инициализируем базу данных
    try:
        initialize_database()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        raise
    
    # Проверяем подключение к Telegram API
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Подключение к Telegram установлено. Бот: @{bot_info.username}")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Telegram: {e}")
        raise
    
    # Синхронизируем модель из ENV с моделью в БД (если пользователь сменил GROQ_MODEL)
    try:
        db_cfg = db_get_settings()
        if db_cfg.get("model") != settings.groq_model:
            db_set_model(settings.groq_model)
            logger.info(f"🔁 Обновил модель в БД: {db_cfg.get('model')} -> {settings.groq_model}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось синхронизировать модель: {e}")

    # Отправляем стартовое сообщение
    await startup_message(bot)

    # === Регистрация команд (перекрываем старые scope) ===
    try:
        user_commands = [
            BotCommand(command="help", description="Справка"),
            BotCommand(command="info", description="О боте"),
            BotCommand(command="me", description="Мой профиль"),
            BotCommand(command="mood", description="Настроение"),
            BotCommand(command="ask", description="Вопрос по делу"),
            BotCommand(command="random", description="Случайная фраза"),
            BotCommand(command="stats", description="Краткая статистика"),
            BotCommand(command="roast", description="Уничтожь меня"),
            BotCommand(command="compliment", description="Язвительный комплимент"),
            BotCommand(command="fortune", description="Мрачное предсказание"),
            BotCommand(command="bad_advice", description="Вредный совет"),
            BotCommand(command="settings", description="Текущие настройки"),
        ]
        admin_commands = user_commands + [
            BotCommand(command="who", description="Профиль пользователя"),
            BotCommand(command="set_mode", description="Режим бота"),
            BotCommand(command="clear_history", description="Очистить историю"),
            BotCommand(command="export_data", description="Экспорт данных"),
            BotCommand(command="global_stats", description="Глобальная статистика"),
            BotCommand(command="debug", description="Отладка"),
            BotCommand(command="reload_settings", description="Reload ENV"),
            BotCommand(command="prompt", description="Промпт"),
            BotCommand(command="forget_user", description="Забыть юзера"),
            BotCommand(command="set", description="Set var"),
            BotCommand(command="get", description="Get var"),
            BotCommand(command="vars", description="List vars"),
            BotCommand(command="unset", description="Del var"),
            BotCommand(command="admin_help", description="Админ справка"),
            BotCommand(command="model", description="Сменить модель"),
            BotCommand(command="models", description="Список моделей"),
        ]
        # Сначала удаляем старые списки в более специфичных scope
        for scope in (BotCommandScopeAllPrivateChats(), BotCommandScopeAllGroupChats(), BotCommandScopeAllChatAdministrators()):
            with suppress(Exception):
                await bot.delete_my_commands(scope=scope)
        # Записываем новые
        # В приватных чатах админы тоже увидят расширенный список, но Telegram не умеет фильтровать по user_id в scope.
        # Поэтому логика: если чат приватный – показываем user_commands (как базу), а admin свои увидят в меню administrators.
        await bot.set_my_commands(user_commands, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(user_commands, scope=BotCommandScopeAllGroupChats())
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeAllChatAdministrators())
        # И дублируем как default (на случай клиентов, которые читают только default)
        await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
        logger.info("✅ Команды бота зарегистрированы/обновлены")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось зарегистрировать команды: {e}")
    
    # Запускаем фоновые задачи
    try:
        task = asyncio.create_task(idle_chime_worker(bot))
        _bg_tasks.append(task)
        logger.info("▶️ idle_chime_worker started")
    except Exception as e:
        logger.warning(f"Не удалось запустить idle_chime_worker: {e}")

    logger.info("🎉 Бот успешно запущен и готов к работе!")

async def on_shutdown(bot: Bot):
    """Обработчик завершения работы бота."""
    logger.info("🛑 Завершение работы бота...")
    
    # Останавливаем фоновые задачи
    for t in _bg_tasks:
        try:
            t.cancel()
        except Exception:
            pass
    # Отправляем сообщение о завершении
    await shutdown_message(bot)
    
    # Закрываем сессию бота
    await bot.session.close()
    
    logger.info("👋 Бот завершил работу")

async def main():
    """Главная функция запуска бота."""
    
    # Проверяем критически важные настройки
    if not settings.telegram_token:
        import os
        checked = {k: os.getenv(k) for k in ["BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN"]}
        masked = {k: (v[:6] + "..." + v[-4:] if v and len(v) > 12 else v) for k, v in checked.items()}
        logger.error("❌ Не найден токен бота. Ожидались переменные: BOT_TOKEN / TELEGRAM_BOT_TOKEN / TELEGRAM_TOKEN")
        logger.error(f"🔎 Текущее состояние переменных: {masked}")
        sys.exit(1)
    
    if not settings.groq_api_key:
        logger.error("❌ Не задан GROQ_API_KEY!")
        sys.exit(1)
    
    if not settings.admin_ids:
        logger.warning("⚠️ Не заданы ADMIN_IDS! Админские функции будут недоступны.")
    
    # Создаем бот и диспетчер
    bot = create_bot()
    dp = create_dispatcher()
    
    # Регистрируем обработчики жизненного цикла
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    try:
        logger.info("🔄 Запуск polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True  # Игнорируем старые обновления
        )
    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал остановки")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        raise
    finally:
        logger.info("🧹 Очистка ресурсов...")

if __name__ == "__main__":
    try:
        # Для Windows совместимости
        if sys.platform.startswith('win'):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        # Запускаем бот
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("⏹️ Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка при запуске: {e}")
        sys.exit(1)
