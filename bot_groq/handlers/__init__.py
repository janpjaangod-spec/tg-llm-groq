"""
Обработчики сообщений и команд
Роутеры для разных типов взаимодействий с ботом
"""

from . import admin
from . import public  
from . import chat
from . import media

# Список всех роутеров для регистрации в диспетчере
routers = [
    admin.router,
    public.router,
    media.router,
    chat.router
]

__all__ = [
    "admin",
    "public", 
    "chat",
    "media",
    "routers"
]
