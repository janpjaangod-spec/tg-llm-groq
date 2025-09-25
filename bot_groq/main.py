#!/usr/bin/env python3
"""
Telegram Bot Леха - Главный файл запуска
Модульная архитектура с разделением обязанностей
"""

import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Импорты наших модулей
from bot_groq.config import settings
from bot_groq.services import initialize_database
from bot_groq.handlers import routers

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
        for admin_id in settings.admin_user_ids:
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
        
        for admin_id in settings.admin_user_ids:
            try:
                await bot.send_message(admin_id, shutdown_text)
            except Exception as e:
                logger.warning(f"Не удалось отправить сообщение о завершении админу {admin_id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения о завершении: {e}")

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
    
    # Отправляем стартовое сообщение
    await startup_message(bot)
    
    logger.info("🎉 Бот успешно запущен и готов к работе!")

async def on_shutdown(bot: Bot):
    """Обработчик завершения работы бота."""
    logger.info("🛑 Завершение работы бота...")
    
    # Отправляем сообщение о завершении
    await shutdown_message(bot)
    
    # Закрываем сессию бота
    await bot.session.close()
    
    logger.info("👋 Бот завершил работу")

async def main():
    """Главная функция запуска бота."""
    
    # Проверяем критически важные настройки
    if not settings.telegram_token:
        logger.error("❌ Не задан TELEGRAM_TOKEN!")
        sys.exit(1)
    
    if not settings.groq_api_key:
        logger.error("❌ Не задан GROQ_API_KEY!")
        sys.exit(1)
    
    if not settings.admin_user_ids:
        logger.error("❌ Не заданы ADMIN_USER_IDS!")
        sys.exit(1)
    
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
