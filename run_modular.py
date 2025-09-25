#!/usr/bin/env python3
"""
Скрипт запуска модульной версии бота Леха
"""

import os
import sys

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем и запускаем main
from bot_groq.main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())