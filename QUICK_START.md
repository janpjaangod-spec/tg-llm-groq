# ⚡ Быстрый запуск на Koyeb

## 🚀 3 шага до запуска бота

### Шаг 1: Создание приложения
1. Идите на [Koyeb Dashboard](https://app.koyeb.com)
2. Create App → GitHub → Выберите `janpjaangod-spec/tg-llm-groq`
3. Branch: `main`

### Шаг 2: Настройка сервиса
```
Service name: leha-bot
Instance: Nano (бесплатный)
Build command: pip install -r requirements.txt
Run command: python -m bot_groq.main
Port: 8080
```

### Шаг 3: Environment Variables
Добавьте ТОЛЬКО эти 3 обязательные переменные:

```bash
BOT_TOKEN=ваш_токен_от_BotFather
GROQ_API_KEY=ваш_ключ_от_groq
ADMIN_TOKEN=случайная_строка_32_символа_минимум
```

## ✅ Готово!
- Нажмите **Deploy**
- Ждите 3-5 минут
- Проверьте логи на ошибки
- Тестируйте бота в Telegram

## 🔧 Дополнительные настройки (опционально)

Для лучшей производительности добавьте:
```bash
ENVIRONMENT=production
LOG_LEVEL=INFO
CACHE_MAX_SIZE=200
MAX_CONTEXT_LENGTH=3000
```

## 🆘 Если что-то не работает

1. **TelegramConflictError** → Остановите старые деплои, подождите 30 сек
2. **Groq API Error** → Проверьте ключ API на console.groq.com
3. **Memory Limit** → Добавьте `KOYEB_NANO_MODE=true`

**Полная документация:** [KOYEB_DEPLOYMENT.md](KOYEB_DEPLOYMENT.md)