#!/usr/bin/env    try:
        from bot_groq.config.settings import settings
        
        print("✅ Настройки загружены успешно!")
        print(f"📱 Bot token: {'*' * 10}...{settings.bot_token[-10:] if settings.bot_token and len(settings.bot_token) > 20 else 'NOT SET'}")
        print(f"🤖 Groq API key: {'*' * 10}...{settings.groq_api_key[-10:] if settings.groq_api_key and len(settings.groq_api_key) > 20 else 'NOT SET'}")
        print(f"👤 Admin token: {settings.admin_token or 'NOT SET'}")
        print(f"🎯 Name keywords: {settings.name_keywords_list}")
        print(f"🌍 Environment: {settings.environment}")
        print(f"📊 Log level: {settings.log_level}")

        # Проверяем валидацию
        try:
            settings.validate_required_fields()
            print("✅ Валидация обязательных полей пройдена")
        except ValueError as e:
            print(f"❌ Ошибка валидации: {e}") настроек - проверяем что конфигурация загружается без ошибок.
"""

import sys
import os
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

def test_settings():
    """Тестируем загрузку настроек."""
    try:
        from bot_groq.config.settings import settings
        
        print("✅ Настройки загружены успешно!")
        print(f"📱 Bot token: {'*' * 10}...{settings.bot_token[-10:] if settings.bot_token and len(settings.bot_token) > 20 else 'NOT SET'}")
    print(f"🤖 Groq API key: {'*' * 10}...{settings.groq_api_key[-10:] if settings.groq_api_key and len(settings.groq_api_key) > 20 else 'NOT SET'}")
    print(f"� Admin token: {settings.admin_token or 'NOT SET'}")
    print(f"🎯 Name keywords: {settings.name_keywords_list}")
    print(f"🌍 Environment: {settings.environment}")
    print(f"� Log level: {settings.log_level}")

    # Проверяем валидацию
    try:
        settings.validate_required_fields()
        print("✅ Валидация обязательных полей пройдена")
    except ValueError as e:
        print(f"❌ Ошибка валидации: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка загрузки настроек: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_settings()
    sys.exit(0 if success else 1)