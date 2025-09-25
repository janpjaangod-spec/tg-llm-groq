"""
Система плагинов для расширения функциональности бота
"""

from abc import ABC, abstractmethod
import importlib
import inspect
import os
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass
from enum import Enum
import asyncio

from aiogram.types import Message
from bot_groq.utils.logging import core_logger

class PluginType(Enum):
    """Типы плагинов."""
    COMMAND = "command"         # Обработчик команд
    MESSAGE = "message"         # Обработчик сообщений
    MEDIA = "media"            # Обработчик медиа
    SCHEDULER = "scheduler"     # Запланированные задачи
    FILTER = "filter"          # Фильтры контента

@dataclass
class PluginMetadata:
    """Метаданные плагина."""
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    dependencies: List[str] = None
    enabled: bool = True

class BotPlugin(ABC):
    """Базовый класс для всех плагинов."""
    
    def __init__(self):
        self.enabled = True
        self.context = {}
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Возвращает метаданные плагина."""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Инициализирует плагин. Возвращает True если успешно."""
        pass
    
    @abstractmethod
    async def handle(self, message: Message, context: Dict[str, Any]) -> Optional[str]:
        """Обрабатывает сообщение. Возвращает ответ или None."""
        pass
    
    async def cleanup(self):
        """Очищает ресурсы при выгрузке плагина."""
        pass
    
    def can_handle(self, message: Message) -> bool:
        """Проверяет, может ли плагин обработать сообщение."""
        return True

class PluginManager:
    """Менеджер плагинов."""
    
    def __init__(self, plugins_dir: str = "bot_groq/plugins"):
        self.plugins_dir = plugins_dir
        self.plugins: Dict[str, BotPlugin] = {}
        self.enabled_plugins: Dict[str, BotPlugin] = {}
        self.plugin_order: List[str] = []
    
    async def load_plugins(self):
        """Загружает все плагины из директории."""
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)
            core_logger.logger.info("plugins_directory_created", path=self.plugins_dir)
            return
        
        for filename in os.listdir(self.plugins_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                plugin_name = filename[:-3]
                await self.load_plugin(plugin_name)
    
    async def load_plugin(self, plugin_name: str) -> bool:
        """Загружает конкретный плагин."""
        try:
            module_path = f"{self.plugins_dir.replace('/', '.')}.{plugin_name}"
            module = importlib.import_module(module_path)
            
            # Ищем классы плагинов в модуле
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BotPlugin) and 
                    obj != BotPlugin):
                    
                    plugin_instance = obj()
                    
                    # Инициализируем плагин
                    if await plugin_instance.initialize():
                        self.plugins[plugin_name] = plugin_instance
                        
                        if plugin_instance.enabled:
                            self.enabled_plugins[plugin_name] = plugin_instance
                        
                        core_logger.logger.info(
                            "plugin_loaded",
                            name=plugin_name,
                            type=plugin_instance.metadata.plugin_type.value,
                            enabled=plugin_instance.enabled
                        )
                        return True
            
            core_logger.logger.warning("no_plugin_class_found", module=plugin_name)
            return False
            
        except Exception as e:
            core_logger.log_error(e, {"operation": "load_plugin", "plugin": plugin_name})
            return False
    
    async def unload_plugin(self, plugin_name: str):
        """Выгружает плагин."""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            await plugin.cleanup()
            
            del self.plugins[plugin_name]
            self.enabled_plugins.pop(plugin_name, None)
            
            core_logger.logger.info("plugin_unloaded", name=plugin_name)
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Включает плагин."""
        if plugin_name in self.plugins:
            plugin = self.plugins[plugin_name]
            plugin.enabled = True
            self.enabled_plugins[plugin_name] = plugin
            return True
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Отключает плагин."""
        if plugin_name in self.plugins:
            self.plugins[plugin_name].enabled = False
            self.enabled_plugins.pop(plugin_name, None)
            return True
        return False
    
    async def handle_message(self, message: Message, context: Dict[str, Any]) -> List[str]:
        """Обрабатывает сообщение через все подходящие плагины."""
        responses = []
        
        for plugin_name, plugin in self.enabled_plugins.items():
            try:
                if plugin.can_handle(message):
                    response = await plugin.handle(message, context)
                    if response:
                        responses.append(response)
            except Exception as e:
                core_logger.log_error(e, {
                    "operation": "plugin_handle_message",
                    "plugin": plugin_name
                })
        
        return responses
    
    def get_plugin_info(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает информацию о всех плагинах."""
        info = {}
        for name, plugin in self.plugins.items():
            metadata = plugin.metadata
            info[name] = {
                "name": metadata.name,
                "version": metadata.version,
                "description": metadata.description,
                "author": metadata.author,
                "type": metadata.plugin_type.value,
                "enabled": plugin.enabled,
                "dependencies": metadata.dependencies or []
            }
        return info

# Примеры плагинов

class GamePlugin(BotPlugin):
    """Плагин мини-игр."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Игры",
            version="1.0.0",
            description="Мини-игры для развлечения в чате",
            author="Леха Bot Team",
            plugin_type=PluginType.COMMAND
        )
    
    async def initialize(self) -> bool:
        self.games = {
            "dice": "🎲 Кубик",
            "coin": "🪙 Монетка", 
            "8ball": "🎱 Магический шар"
        }
        return True
    
    def can_handle(self, message: Message) -> bool:
        if not message.text:
            return False
        text = message.text.lower()
        return any(f"!{game}" in text for game in self.games.keys())
    
    async def handle(self, message: Message, context: Dict[str, Any]) -> Optional[str]:
        text = message.text.lower()
        
        if "!dice" in text:
            import random
            result = random.randint(1, 6)
            return f"🎲 Выпало: {result}"
        
        elif "!coin" in text:
            import random
            result = random.choice(["Орел", "Решка"])
            return f"🪙 Монетка: {result}"
        
        elif "!8ball" in text:
            import random
            answers = [
                "Определенно да", "Скорее всего", "Возможно", 
                "Не уверен", "Маловероятно", "Определенно нет"
            ]
            return f"🎱 Магический шар говорит: {random.choice(answers)}"
        
        return None

class WeatherPlugin(BotPlugin):
    """Плагин погоды."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Погода",
            version="1.0.0", 
            description="Получение информации о погоде",
            author="Леха Bot Team",
            plugin_type=PluginType.COMMAND
        )
    
    async def initialize(self) -> bool:
        # Здесь можно инициализировать API ключи и т.д.
        return True
    
    def can_handle(self, message: Message) -> bool:
        if not message.text:
            return False
        return "погода" in message.text.lower() or "!weather" in message.text.lower()
    
    async def handle(self, message: Message, context: Dict[str, Any]) -> Optional[str]:
        # Здесь был бы реальный API запрос к сервису погоды
        import random
        conditions = ["солнечно", "пасмурно", "дождь", "снег", "туман"]
        temp = random.randint(-10, 30)
        condition = random.choice(conditions)
        
        return f"🌤️ Погода: {condition}, температура {temp}°C"

class ReminderPlugin(BotPlugin):
    """Плагин напоминаний."""
    
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Напоминания",
            version="1.0.0",
            description="Система напоминаний",
            author="Леха Bot Team", 
            plugin_type=PluginType.SCHEDULER
        )
    
    async def initialize(self) -> bool:
        self.reminders = []
        # Запускаем фоновую задачу для проверки напоминаний
        asyncio.create_task(self._check_reminders())
        return True
    
    def can_handle(self, message: Message) -> bool:
        if not message.text:
            return False
        return "напомни" in message.text.lower() or "!remind" in message.text.lower()
    
    async def handle(self, message: Message, context: Dict[str, Any]) -> Optional[str]:
        # Парсинг команды напоминания
        # Здесь была бы логика парсинга времени и текста
        return "⏰ Напоминание установлено!"
    
    async def _check_reminders(self):
        """Фоновая задача для проверки напоминаний."""
        while True:
            # Проверка и отправка напоминаний
            await asyncio.sleep(60)  # Проверяем каждую минуту

# Глобальный менеджер плагинов
plugin_manager = PluginManager()

async def initialize_plugins():
    """Инициализирует систему плагинов."""
    await plugin_manager.load_plugins()
    core_logger.logger.info("plugin_system_initialized", 
                           total_plugins=len(plugin_manager.plugins),
                           enabled_plugins=len(plugin_manager.enabled_plugins))