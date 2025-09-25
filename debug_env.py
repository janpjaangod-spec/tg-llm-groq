#!/usr/bin/env python3
import os

print("Все переменные окружения с 'GROQ':")
for key, value in os.environ.items():
    if 'GROQ' in key.upper():
        print(f"{key} = {value}")

print(f"\nПрямая проверка GROQ_API_KEY: {os.getenv('GROQ_API_KEY', 'НЕ НАЙДЕНО')}")
print(f"groq_api_key: {os.getenv('groq_api_key', 'НЕ НАЙДЕНО')}")

# Попробуем создать настройки вручную
try:
    from bot_groq.config.settings import Settings
    s = Settings(groq_api_key="test123")
    print(f"Создание настроек с параметром работает: {s.groq_api_key}")
except Exception as e:
    print(f"Ошибка создания настроек: {e}")