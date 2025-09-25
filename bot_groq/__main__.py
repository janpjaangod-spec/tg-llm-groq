#!/usr/bin/env python3
"""
Точка входа для запуска бота как модуль.
Использование: python -m bot_groq
"""

import asyncio
from bot_groq.main import main

if __name__ == "__main__":
    asyncio.run(main())