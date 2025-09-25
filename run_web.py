#!/usr/bin/env python3
"""
Запуск веб-интерфейса администратора.
Можно запускать отдельно от основного бота.
"""

import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    """Главная функция запуска веб-интерфейса."""
    try:
        import uvicorn
        from bot_groq.web.app import app
        from bot_groq.config.settings import settings
        
        print("🌐 Запуск веб-интерфейса администратора...")
        print(f"📊 Dashboard будет доступен на: http://localhost:8000")
        print(f"🔑 Токен администратора: {settings.admin_token}")
        print("─" * 50)
        
        # Запускаем веб-сервер
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            reload=False,
            access_log=True
        )
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("💡 Установите зависимости: pip install -r requirements.txt")
        sys.exit(1)
        
    except Exception as e:
        print(f"❌ Ошибка запуска веб-интерфейса: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()