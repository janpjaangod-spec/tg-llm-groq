"""Вспомогательный скрипт для быстрой проверки загрузки настроек.
Не используется в проде; можно запустить локально: python test_settings.py
"""
from bot_groq.config.settings import settings


def main() -> int:
    try:
        print("✅ Настройки загружены")
        bt = settings.bot_token
        print(f"📱 Bot token: {bt[:6]+'...'+bt[-4:] if bt and len(bt)>14 else bt or 'NOT SET'}")
        print(f"🤖 Groq key set: {'YES' if settings.groq_api_key else 'NO'}")
        print(f"👑 Admin IDs: {sorted(settings.admin_ids)}")
        print(f"🌐 TZ: {settings.timezone} | ENV: {settings.environment}")
        print(f"🗃 DB: {settings.db_name}")
        settings.validate_required_fields()
        print("✅ Валидация обязательных полей прошла")
        return 0
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())