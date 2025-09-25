"""
Конфигурация бота
Централизованное управление настройками через Pydantic
"""

from .settings import settings, Settings

def reload_settings() -> Settings:
	"""Перечитывает переменные окружения и возвращает новый объект настроек.
	ВАЖНО: Обновляет глобальный `settings` по месту, чтобы другие импорты видели обновление.
	"""
	global settings  # type: ignore
	settings = Settings()  # re-evaluate env
	return settings

__all__ = ["settings", "reload_settings", "Settings"]
