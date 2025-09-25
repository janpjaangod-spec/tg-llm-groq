#!/usr/bin/env python3
import os

# Установим переменные
os.environ['BOT_TOKEN'] = '1234567890:ABCdefghijklmnopqrstuvwxyz123456789'
os.environ['GROQ_API_KEY'] = 'gsk_1234567890abcdef'

print("Переменные установлены в os.environ:")
print(f"BOT_TOKEN: {os.environ['BOT_TOKEN']}")
print(f"GROQ_API_KEY: {os.environ['GROQ_API_KEY']}")

try:
    from bot_groq.config.settings import Settings
    
    # Создаем новый экземпляр 
    s = Settings()
    print(f"\nНовый экземпляр Settings:")
    print(f"bot_token: {s.bot_token}")
    print(f"groq_api_key: {s.groq_api_key}")
    
except Exception as e:
    print(f"Ошибка: {e}")
    import traceback
    traceback.print_exc()