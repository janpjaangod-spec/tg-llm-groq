"""
Система кеширования и оптимизации базы данных
"""

import sqlite3
import time
import json
import hashlib
from contextlib import closing
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from threading import Lock
import asyncio
from functools import wraps

from bot_groq.config.settings import settings
from bot_groq.utils.logging import database_logger, bot_metrics

@dataclass
class CacheEntry:
    """Запись в кеше."""
    value: Any
    timestamp: float
    ttl: float
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl

class MemoryCache:
    """In-memory кеш для частых запросов."""
    
    def __init__(self, default_ttl: float = 300):  # 5 минут по умолчанию
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = Lock()
        self.default_ttl = default_ttl
        
        # Статистика кеша
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Получает значение из кеша."""
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                self.hits += 1
                return entry.value
            elif entry:
                # Удаляем просроченную запись
                del self._cache[key]
            
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Сохраняет значение в кеш."""
        with self._lock:
            ttl = ttl or self.default_ttl
            self._cache[key] = CacheEntry(value, time.time(), ttl)
    
    def delete(self, key: str):
        """Удаляет значение из кеша."""
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self):
        """Очищает весь кеш."""
        with self._lock:
            self._cache.clear()
    
    def cleanup_expired(self):
        """Удаляет просроченные записи."""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items() 
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику кеша."""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "cache_size": len(self._cache)
        }

# Глобальный кеш
cache = MemoryCache()

def cache_key(*args) -> str:
    """Генерирует ключ кеша из аргументов."""
    key_str = "|".join(str(arg) for arg in args)
    return hashlib.md5(key_str.encode()).hexdigest()

def cached(ttl: Optional[float] = None, key_func=None):
    """Декоратор для кеширования результатов функций."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Генерируем ключ кеша
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = cache_key(func.__name__, *args, *kwargs.items())
            
            # Пробуем получить из кеша
            result = cache.get(key)
            if result is not None:
                return result
            
            # Выполняем функцию и кешируем результат
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        
        return wrapper
    return decorator

class DatabaseOptimizer:
    """Оптимизатор базы данных."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._last_vacuum = 0
        self._last_analyze = 0
    
    def optimize_database(self):
        """Выполняет полную оптимизацию базы данных."""
        with database_logger.timed_operation("database_optimization"):
            try:
                with closing(sqlite3.connect(self.db_path)) as conn:
                    conn.execute("PRAGMA optimize")
                    
                    # VACUUM каждые 24 часа
                    if time.time() - self._last_vacuum > 86400:
                        conn.execute("VACUUM")
                        self._last_vacuum = time.time()
                        database_logger.logger.info("database_vacuum_completed")
                    
                    # ANALYZE каждые 6 часов
                    if time.time() - self._last_analyze > 21600:
                        conn.execute("ANALYZE")
                        self._last_analyze = time.time()
                        database_logger.logger.info("database_analyze_completed")
                    
                    conn.commit()
                    
            except Exception as e:
                database_logger.log_error(e, {"operation": "database_optimization"})
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Возвращает статистику базы данных."""
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                c = conn.cursor()
                
                # Размер базы данных
                c.execute("PRAGMA page_count")
                page_count = c.fetchone()[0]
                c.execute("PRAGMA page_size")
                page_size = c.fetchone()[0]
                db_size = page_count * page_size
                
                # Количество записей в основных таблицах
                table_counts = {}
                tables = ['chat_history', 'person_profile', 'relationship_profile', 'reminders']
                
                for table in tables:
                    try:
                        c.execute(f"SELECT COUNT(*) FROM {table}")
                        table_counts[table] = c.fetchone()[0]
                    except sqlite3.OperationalError:
                        table_counts[table] = 0
                
                return {
                    "database_size_bytes": db_size,
                    "database_size_mb": round(db_size / 1024 / 1024, 2),
                    "table_counts": table_counts,
                    "last_vacuum": self._last_vacuum,
                    "last_analyze": self._last_analyze
                }
                
        except Exception as e:
            database_logger.log_error(e, {"operation": "get_database_stats"})
            return {}

class BatchProcessor:
    """Обработчик для батчевых операций с базой данных."""
    
    def __init__(self, batch_size: int = 100, flush_interval: float = 30.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._batches: Dict[str, List[Tuple]] = {}
        self._last_flush = time.time()
        self._lock = Lock()
    
    def add_operation(self, operation_type: str, data: Tuple):
        """Добавляет операцию в батч."""
        with self._lock:
            if operation_type not in self._batches:
                self._batches[operation_type] = []
            
            self._batches[operation_type].append(data)
            
            # Проверяем, нужно ли сбросить батч
            if (len(self._batches[operation_type]) >= self.batch_size or 
                time.time() - self._last_flush > self.flush_interval):
                self._flush_batch(operation_type)
    
    def _flush_batch(self, operation_type: str):
        """Сбрасывает батч в базу данных."""
        if operation_type not in self._batches or not self._batches[operation_type]:
            return
        
        batch = self._batches[operation_type].copy()
        self._batches[operation_type].clear()
        self._last_flush = time.time()
        
        try:
            with closing(sqlite3.connect(settings.db_name)) as conn:
                if operation_type == "save_message":
                    conn.executemany(
                        "INSERT OR REPLACE INTO chat_history VALUES (?, ?, ?, ?, ?)",
                        batch
                    )
                elif operation_type == "update_activity":
                    conn.executemany(
                        "INSERT OR REPLACE INTO chat_activity VALUES (?, ?)",
                        batch
                    )
                # Добавить другие типы операций по необходимости
                
                conn.commit()
                bot_metrics.metrics["database_operations"] += len(batch)
                
        except Exception as e:
            database_logger.log_error(e, {
                "operation": "flush_batch", 
                "type": operation_type,
                "batch_size": len(batch)
            })
            bot_metrics.metrics["database_errors"] += 1
    
    def flush_all(self):
        """Принудительно сбрасывает все батчи."""
        with self._lock:
            for operation_type in list(self._batches.keys()):
                self._flush_batch(operation_type)

# Глобальные экземпляры
db_optimizer = DatabaseOptimizer(settings.db_name)
batch_processor = BatchProcessor()

# Улучшенные функции базы данных с кешированием
@cached(ttl=60)  # Кешируем на 1 минуту
def get_user_profile_cached(chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Получает профиль пользователя с кешированием."""
    from bot_groq.services.database import db_load_person
    return db_load_person(chat_id, user_id)

@cached(ttl=300)  # Кешируем на 5 минут
def get_chat_stats_cached(chat_id: int) -> Dict[str, Any]:
    """Получает статистику чата с кешированием."""
    from bot_groq.services.database import db_get_group_stats
    return db_get_group_stats(chat_id)

def invalidate_user_cache(chat_id: int, user_id: int):
    """Инвалидирует кеш пользователя."""
    key = cache_key("get_user_profile_cached", chat_id, user_id)
    cache.delete(key)

def invalidate_chat_cache(chat_id: int):
    """Инвалидирует кеш чата."""
    key = cache_key("get_chat_stats_cached", chat_id)
    cache.delete(key)

# Фоновая задача для периодической очистки
async def background_maintenance():
    """Фоновая задача для обслуживания кеша и БД."""
    while True:
        try:
            # Очищаем просроченные записи кеша
            cache.cleanup_expired()
            
            # Сбрасываем батчи
            batch_processor.flush_all()
            
            # Оптимизируем базу данных (раз в час)
            if int(time.time()) % 3600 == 0:
                db_optimizer.optimize_database()
            
            await asyncio.sleep(60)  # Каждую минуту
            
        except Exception as e:
            database_logger.log_error(e, {"operation": "background_maintenance"})