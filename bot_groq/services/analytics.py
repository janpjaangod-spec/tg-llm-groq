"""
Система аналитики и метрик для веб-интерфейса
"""

import time
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from datetime import datetime, timedelta
import asyncio

from bot_groq.services.database import db_get_chat_tail, db_get_all_groups
from bot_groq.utils.logging import core_logger
from bot_groq.utils.cache import cache, cached

@dataclass
class UserAnalytics:
    """Аналитика пользователя."""
    user_id: int
    username: str
    display_name: str
    total_messages: int
    avg_message_length: float
    toxicity_level: int
    last_activity: float
    favorite_words: Dict[str, int]
    activity_pattern: Dict[int, int]  # час -> количество сообщений
    sentiment_trend: List[float]  # последние 10 значений тона

@dataclass
class ChatAnalytics:
    """Аналитика чата."""
    chat_id: int
    chat_name: str
    total_messages: int
    active_users: int
    avg_messages_per_day: float
    peak_activity_hour: int
    toxicity_index: float
    top_users: List[Tuple[int, int]]  # (user_id, message_count)
    popular_topics: Dict[str, int]
    conflict_incidents: int
    growth_trend: List[int]  # сообщений за последние 7 дней

@dataclass
class GlobalAnalytics:
    """Глобальная аналитика бота."""
    total_chats: int
    total_users: int
    total_messages: int
    llm_requests: int
    llm_success_rate: float
    avg_response_time: float
    uptime_hours: float
    most_active_chat: Optional[int]
    daily_stats: Dict[str, int]  # дата -> сообщений

class AnalyticsEngine:
    """Движок аналитики."""
    
    def __init__(self):
        self.cache_ttl = 600  # 10 минут
        self._user_analytics_cache = {}
        self._chat_analytics_cache = {}
        
    @cached(ttl=600)
    def get_user_analytics(self, chat_id: int, user_id: int) -> Optional[UserAnalytics]:
        """Получает аналитику пользователя."""
        try:
            # Получаем историю сообщений пользователя
            history = db_get_chat_tail(chat_id, limit=1000)
            user_messages = [msg for msg in history if msg.get('user_id') == user_id]
            
            if not user_messages:
                return None
            
            # Вычисляем метрики
            total_messages = len(user_messages)
            total_length = sum(len(msg.get('text', '')) for msg in user_messages)
            avg_length = total_length / total_messages if total_messages > 0 else 0
            
            # Анализируем активность по часам
            activity_pattern = defaultdict(int)
            for msg in user_messages:
                if msg.get('timestamp'):
                    hour = datetime.fromtimestamp(msg['timestamp']).hour
                    activity_pattern[hour] += 1
            
            # Извлекаем популярные слова
            all_text = ' '.join(msg.get('text', '') for msg in user_messages)
            words = all_text.lower().split()
            word_freq = defaultdict(int)
            for word in words:
                if len(word) > 3:  # Только длинные слова
                    word_freq[word] += 1
            
            favorite_words = dict(sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10])
            
            # Последняя активность
            last_activity = max(msg.get('timestamp', 0) for msg in user_messages)
            
            # Получаем информацию о пользователе
            from bot_groq.services.database import db_load_person
            profile = db_load_person(chat_id, user_id) or {}
            
            return UserAnalytics(
                user_id=user_id,
                username=profile.get('username', ''),
                display_name=profile.get('display_name', f'User_{user_id}'),
                total_messages=total_messages,
                avg_message_length=avg_length,
                toxicity_level=profile.get('spice', 0),
                last_activity=last_activity,
                favorite_words=favorite_words,
                activity_pattern=dict(activity_pattern),
                sentiment_trend=[]  # TODO: Implement sentiment analysis
            )
            
        except Exception as e:
            core_logger.log_error(e, {"operation": "get_user_analytics", "user_id": user_id})
            return None
    
    @cached(ttl=600)
    def get_chat_analytics(self, chat_id: int) -> Optional[ChatAnalytics]:
        """Получает аналитику чата."""
        try:
            history = db_get_chat_tail(chat_id, limit=5000)
            
            if not history:
                return None
            
            # Основные метрики
            total_messages = len(history)
            unique_users = len(set(msg.get('user_id') for msg in history if msg.get('user_id')))
            
            # Активность по дням
            now = time.time()
            daily_messages = []
            for i in range(7):  # Последние 7 дней
                day_start = now - (i + 1) * 86400
                day_end = now - i * 86400
                day_count = len([msg for msg in history 
                               if day_start <= msg.get('timestamp', 0) < day_end])
                daily_messages.append(day_count)
            
            avg_per_day = sum(daily_messages) / 7 if daily_messages else 0
            
            # Пиковый час активности
            hour_activity = defaultdict(int)
            for msg in history:
                if msg.get('timestamp'):
                    hour = datetime.fromtimestamp(msg['timestamp']).hour
                    hour_activity[hour] += 1
            
            peak_hour = max(hour_activity.items(), key=lambda x: x[1])[0] if hour_activity else 0
            
            # Топ пользователей
            user_counts = defaultdict(int)
            for msg in history:
                if msg.get('user_id'):
                    user_counts[msg['user_id']] += 1
            
            top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # Популярные темы (простой анализ ключевых слов)
            all_text = ' '.join(msg.get('text', '') for msg in history).lower()
            words = all_text.split()
            topic_words = defaultdict(int)
            
            # Фильтруем по важным словам
            important_words = [word for word in words if len(word) > 4 and word.isalpha()]
            for word in important_words:
                topic_words[word] += 1
            
            popular_topics = dict(sorted(topic_words.items(), key=lambda x: x[1], reverse=True)[:15])
            
            return ChatAnalytics(
                chat_id=chat_id,
                chat_name=f"Chat_{chat_id}",  # TODO: Get real chat name
                total_messages=total_messages,
                active_users=unique_users,
                avg_messages_per_day=avg_per_day,
                peak_activity_hour=peak_hour,
                toxicity_index=0.0,  # TODO: Calculate toxicity
                top_users=top_users,
                popular_topics=popular_topics,
                conflict_incidents=0,  # TODO: Detect conflicts
                growth_trend=daily_messages
            )
            
        except Exception as e:
            core_logger.log_error(e, {"operation": "get_chat_analytics", "chat_id": chat_id})
            return None
    
    def get_global_analytics(self) -> GlobalAnalytics:
        """Получает глобальную аналитику."""
        try:
            # Получаем все группы
            groups = db_get_all_groups()
            total_chats = len(groups)
            
            total_messages = 0
            total_users = set()
            
            for group in groups:
                chat_id = group.get('chat_id')
                if chat_id:
                    history = db_get_chat_tail(chat_id, limit=1000)
                    total_messages += len(history)
                    
                    for msg in history:
                        if msg.get('user_id'):
                            total_users.add(msg['user_id'])
            
            # Статистика из метрик
            from bot_groq.utils.cache import bot_metrics
            metrics = bot_metrics.get_stats()
            
            # Дневная статистика (заглушка)
            daily_stats = {}
            for i in range(7):
                date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                daily_stats[date] = total_messages // 7  # Упрощенно
            
            return GlobalAnalytics(
                total_chats=total_chats,
                total_users=len(total_users),
                total_messages=total_messages,
                llm_requests=metrics.get('llm_requests', 0),
                llm_success_rate=1 - metrics.get('llm_error_rate', 0),
                avg_response_time=metrics.get('avg_response_time', 0),
                uptime_hours=metrics.get('uptime_seconds', 0) / 3600,
                most_active_chat=None,  # TODO: Determine most active
                daily_stats=daily_stats
            )
            
        except Exception as e:
            core_logger.log_error(e, {"operation": "get_global_analytics"})
            return GlobalAnalytics(0, 0, 0, 0, 0, 0, 0, None, {})

class ReportGenerator:
    """Генератор отчетов."""
    
    def __init__(self, analytics: AnalyticsEngine):
        self.analytics = analytics
    
    def generate_chat_report(self, chat_id: int) -> Dict[str, Any]:
        """Генерирует отчет по чату."""
        chat_analytics = self.analytics.get_chat_analytics(chat_id)
        if not chat_analytics:
            return {"error": "No data available"}
        
        # Получаем аналитику топ пользователей
        top_user_analytics = []
        for user_id, message_count in chat_analytics.top_users[:5]:
            user_analytics = self.analytics.get_user_analytics(chat_id, user_id)
            if user_analytics:
                top_user_analytics.append(asdict(user_analytics))
        
        return {
            "chat": asdict(chat_analytics),
            "top_users": top_user_analytics,
            "generated_at": datetime.now().isoformat(),
            "report_type": "chat_summary"
        }
    
    def generate_user_report(self, chat_id: int, user_id: int) -> Dict[str, Any]:
        """Генерирует отчет по пользователю."""
        user_analytics = self.analytics.get_user_analytics(chat_id, user_id)
        if not user_analytics:
            return {"error": "No data available"}
        
        return {
            "user": asdict(user_analytics),
            "generated_at": datetime.now().isoformat(),
            "report_type": "user_profile"
        }
    
    def generate_global_report(self) -> Dict[str, Any]:
        """Генерирует глобальный отчет."""
        global_analytics = self.analytics.get_global_analytics()
        
        return {
            "global": asdict(global_analytics),
            "generated_at": datetime.now().isoformat(),
            "report_type": "global_summary"
        }

# Глобальные экземпляры
analytics_engine = AnalyticsEngine()
report_generator = ReportGenerator(analytics_engine)

# API функции для веб-интерфейса
async def get_dashboard_data() -> Dict[str, Any]:
    """Получает данные для дашборда."""
    global_analytics = analytics_engine.get_global_analytics()
    
    # Последние активные чаты
    groups = db_get_all_groups()
    recent_chats = []
    
    for group in groups[:10]:  # Топ 10 чатов
        chat_id = group.get('chat_id')
        if chat_id:
            chat_analytics = analytics_engine.get_chat_analytics(chat_id)
            if chat_analytics:
                recent_chats.append({
                    "chat_id": chat_id,
                    "name": chat_analytics.chat_name,
                    "messages": chat_analytics.total_messages,
                    "users": chat_analytics.active_users
                })
    
    return {
        "global": asdict(global_analytics),
        "recent_chats": recent_chats,
        "timestamp": datetime.now().isoformat()
    }

async def search_chats(query: str) -> List[Dict[str, Any]]:
    """Поиск чатов по названию или ID."""
    groups = db_get_all_groups()
    results = []
    
    for group in groups:
        chat_id = group.get('chat_id')
        if chat_id and (query in str(chat_id) or query.lower() in str(group).lower()):
            chat_analytics = analytics_engine.get_chat_analytics(chat_id)
            if chat_analytics:
                results.append({
                    "chat_id": chat_id,
                    "name": chat_analytics.chat_name,
                    "messages": chat_analytics.total_messages,
                    "users": chat_analytics.active_users
                })
    
    return results