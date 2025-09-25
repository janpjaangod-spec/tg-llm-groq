"""
Веб-интерфейс администратора для бота Леха.
Предоставляет dashboard, управление пользователями и аналитику.
"""

from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import json
from datetime import datetime, timedelta

from ..config.settings import settings
from ..services.database import database_service
from ..services.analytics import analytics_engine, report_generator
from ..utils.logging import bot_logger, bot_metrics
from ..utils.cache import memory_cache

app = FastAPI(
    title="Леха Bot Admin Panel",
    description="Панель администратора для управления ботом",
    version="1.0.0"
)

# Настройка шаблонов и статики
templates = Jinja2Templates(directory="bot_groq/web/templates")
app.mount("/static", StaticFiles(directory="bot_groq/web/static"), name="static")

# Безопасность
security = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str

class ChatModeUpdate(BaseModel):
    chat_id: int
    mode: str

class UserBanRequest(BaseModel):
    chat_id: int
    user_id: int
    duration_hours: Optional[int] = None
    reason: str = "Нарушение правил"

async def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка токена администратора."""
    if credentials.credentials != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return credentials.credentials

# Главная страница - дашборд
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, token: str = Depends(verify_admin_token)):
    """Главная страница с общей статистикой."""
    try:
        # Получаем статистику
        global_stats = analytics_engine.get_global_analytics()
        bot_stats = bot_metrics.get_stats()
        
        # Недавняя активность
        recent_chats = await database_service.get_recent_active_chats(limit=10)
        
        context = {
            "request": request,
            "global_stats": global_stats,
            "bot_stats": bot_stats,
            "recent_chats": recent_chats,
            "current_time": datetime.now().strftime("%H:%M:%S")
        }
        
        return templates.TemplateResponse("dashboard.html", context)
        
    except Exception as e:
        bot_logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Dashboard loading failed")

# API для получения статистики в реальном времени
@app.get("/api/stats/realtime")
async def get_realtime_stats(token: str = Depends(verify_admin_token)):
    """Получение статистики в реальном времени для обновления дашборда."""
    stats = {
        "bot_metrics": bot_metrics.get_stats(),
        "active_chats": len(await database_service.get_active_chats()),
        "messages_today": analytics_engine.get_messages_count_today(),
        "llm_requests_today": analytics_engine.get_llm_requests_today(),
        "cache_hit_rate": memory_cache.get_hit_rate(),
        "timestamp": datetime.now().isoformat()
    }
    return JSONResponse(stats)

# Управление чатами
@app.get("/chats", response_class=HTMLResponse)
async def chats_page(request: Request, token: str = Depends(verify_admin_token)):
    """Страница управления чатами."""
    chats = await database_service.get_all_chats()
    return templates.TemplateResponse("chats.html", {
        "request": request,
        "chats": chats
    })

@app.get("/api/chats")
async def get_chats(
    search: str = "", 
    limit: int = 50, 
    offset: int = 0,
    token: str = Depends(verify_admin_token)
):
    """API для получения списка чатов с поиском."""
    chats = await database_service.search_chats(search, limit, offset)
    
    # Добавляем статистику для каждого чата
    for chat in chats:
        chat_stats = analytics_engine.get_chat_analytics(chat['chat_id'])
        chat.update({
            'total_messages': chat_stats.total_messages,
            'active_users': len(chat_stats.active_users),
            'avg_toxicity': chat_stats.avg_toxicity_level,
            'last_activity': chat_stats.last_activity_time
        })
    
    return JSONResponse(chats)

@app.post("/api/chats/mode")
async def update_chat_mode(
    request: ChatModeUpdate, 
    token: str = Depends(verify_admin_token)
):
    """Изменение режима работы бота в чате."""
    try:
        await database_service.update_chat_mode(request.chat_id, request.mode)
        
        bot_logger.info(f"Chat mode updated: {request.chat_id} -> {request.mode}")
        
        return JSONResponse({
            "success": True,
            "message": f"Режим чата {request.chat_id} изменен на {request.mode}"
        })
        
    except Exception as e:
        bot_logger.error(f"Failed to update chat mode: {e}")
        raise HTTPException(status_code=500, detail="Failed to update chat mode")

# Управление пользователями
@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, token: str = Depends(verify_admin_token)):
    """Страница управления пользователями."""
    return templates.TemplateResponse("users.html", {"request": request})

@app.get("/api/users")
async def get_users(
    search: str = "", 
    limit: int = 50, 
    offset: int = 0,
    sort_by: str = "last_seen",
    token: str = Depends(verify_admin_token)
):
    """API для получения списка пользователей."""
    users = await database_service.search_users(search, limit, offset, sort_by)
    
    # Добавляем аналитику пользователей
    for user in users:
        user_stats = analytics_engine.get_user_analytics_all_chats(user['user_id'])
        user.update({
            'total_messages': user_stats.total_messages,
            'avg_toxicity': user_stats.avg_toxicity_level,
            'favorite_words': user_stats.favorite_words[:3],  # Топ-3
            'is_banned': user_stats.is_banned
        })
    
    return JSONResponse(users)

@app.post("/api/users/ban")
async def ban_user(
    request: UserBanRequest, 
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_admin_token)
):
    """Бан пользователя."""
    try:
        # Устанавливаем бан
        ban_until = None
        if request.duration_hours:
            ban_until = datetime.now() + timedelta(hours=request.duration_hours)
        
        await database_service.ban_user(
            request.chat_id, 
            request.user_id, 
            request.reason,
            ban_until
        )
        
        # Логируем действие
        bot_logger.warning(
            f"User banned: {request.user_id} in chat {request.chat_id}",
            extra={
                "action": "user_ban",
                "user_id": request.user_id,
                "chat_id": request.chat_id,
                "reason": request.reason,
                "duration_hours": request.duration_hours
            }
        )
        
        return JSONResponse({
            "success": True,
            "message": f"Пользователь {request.user_id} забанен"
        })
        
    except Exception as e:
        bot_logger.error(f"Failed to ban user: {e}")
        raise HTTPException(status_code=500, detail="Failed to ban user")

# Аналитика и отчеты
@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, token: str = Depends(verify_admin_token)):
    """Страница аналитики."""
    return templates.TemplateResponse("analytics.html", {"request": request})

@app.get("/api/analytics/global")
async def get_global_analytics(
    period: str = "7d",
    token: str = Depends(verify_admin_token)
):
    """Глобальная аналитика за период."""
    try:
        # Парсим период
        if period == "24h":
            hours = 24
        elif period == "7d":
            hours = 24 * 7
        elif period == "30d":
            hours = 24 * 30
        else:
            hours = 24 * 7
        
        analytics = analytics_engine.get_global_analytics_period(hours)
        
        return JSONResponse({
            "period": period,
            "analytics": analytics.__dict__,
            "generated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        bot_logger.error(f"Failed to get global analytics: {e}")
        raise HTTPException(status_code=500, detail="Analytics generation failed")

@app.get("/api/analytics/chat/{chat_id}")
async def get_chat_analytics(
    chat_id: int,
    period: str = "7d",
    token: str = Depends(verify_admin_token)
):
    """Аналитика конкретного чата."""
    try:
        analytics = analytics_engine.get_chat_analytics_period(chat_id, period)
        
        return JSONResponse({
            "chat_id": chat_id,
            "period": period,
            "analytics": analytics.__dict__,
            "generated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        bot_logger.error(f"Failed to get chat analytics: {e}")
        raise HTTPException(status_code=500, detail="Chat analytics generation failed")

@app.post("/api/reports/generate")
async def generate_report(
    background_tasks: BackgroundTasks,
    report_type: str = "global",
    format: str = "json",
    period: str = "7d",
    token: str = Depends(verify_admin_token)
):
    """Генерация отчета в фоновом режиме."""
    try:
        # Запускаем генерацию отчета в фоне
        task_id = f"report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        background_tasks.add_task(
            report_generator.generate_report_async,
            task_id,
            report_type,
            format,
            period
        )
        
        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "message": "Отчет генерируется в фоновом режиме"
        })
        
    except Exception as e:
        bot_logger.error(f"Failed to start report generation: {e}")
        raise HTTPException(status_code=500, detail="Report generation failed")

# Системная информация
@app.get("/api/system/info")
async def get_system_info(token: str = Depends(verify_admin_token)):
    """Информация о системе."""
    try:
        import psutil
        import platform
        
        system_info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_usage": psutil.cpu_percent(interval=1),
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "free": psutil.disk_usage('/').free,
                "percent": psutil.disk_usage('/').percent
            },
            "bot_uptime": bot_metrics.get_uptime(),
            "cache_stats": memory_cache.get_stats()
        }
        
        return JSONResponse(system_info)
        
    except Exception as e:
        bot_logger.error(f"Failed to get system info: {e}")
        return JSONResponse({"error": "System info unavailable"})

# Управление логами
@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, token: str = Depends(verify_admin_token)):
    """Страница просмотра логов."""
    return templates.TemplateResponse("logs.html", {"request": request})

@app.get("/api/logs")
async def get_logs(
    level: str = "INFO",
    limit: int = 100,
    search: str = "",
    token: str = Depends(verify_admin_token)
):
    """API для получения логов."""
    try:
        logs = await bot_logger.get_recent_logs(level, limit, search)
        return JSONResponse(logs)
        
    except Exception as e:
        bot_logger.error(f"Failed to get logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve logs")

# Настройки бота
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, token: str = Depends(verify_admin_token)):
    """Страница настроек бота."""
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": settings.model_dump()
    })

# Health check
@app.get("/health")
async def health_check():
    """Проверка здоровья приложения."""
    try:
        # Проверяем подключение к базе данных
        await database_service.health_check()
        
        return JSONResponse({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        })
        
    except Exception as e:
        return JSONResponse({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, status_code=503)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )