"""
Telegram Bot Леха - Модульная архитектура
Токсичный бот для групповых чатов с интеграцией Groq LLM
"""

__version__ = "2.0.0"
__author__ = "Леха Bot Team"
__description__ = "Модульный Telegram бот с профилированием пользователей и групповой динамикой"

# Основные компоненты для импорта
from .config.settings import settings
from .services.database import initialize_database
from .services.llm import llm_text, llm_vision

__all__ = [
    "settings",
    "initialize_database", 
    "llm_text",
    "llm_vision",
    "__version__"
]
