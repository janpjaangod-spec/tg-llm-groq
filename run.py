#!/usr/bin/env python3
"""
Скрипт запуска бота для Koyeb.
Альтернативный способ запуска если Procfile не работает.
"""

if __name__ == "__main__":
    import asyncio
    from bot_groq.main import main
    
    print("🚀 Запуск Telegram Bot 'Леха' на Koyeb...")
    asyncio.run(main())