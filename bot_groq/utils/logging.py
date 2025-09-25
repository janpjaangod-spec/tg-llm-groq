"""
Structured logging и monitoring для бота
"""

import logging
import structlog
import time
from typing import Any, Dict, Optional
from contextlib import contextmanager
import sys
import json

# Настройка structured logging
def configure_logging():
    """Конфигурирует structured logging с JSON выводом."""
    
    # Timestamper для добавления времени
    timestamper = structlog.processors.TimeStamper(fmt="ISO")
    
    # Shared processors для всех логгеров
    shared_processors = [
        structlog.stdlib.filter_by_level,
        timestamper,
        structlog.dev.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Разные форматеры для разных сред
    if sys.stdout.isatty():
        # Красивый вывод для разработки
        processor = structlog.dev.ConsoleRenderer()
    else:
        # JSON для продакшена (Koyeb)
        processor = structlog.processors.JSONRenderer()
    
    structlog.configure(
        processors=shared_processors + [processor],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

class BotLogger:
    """Централизованный логгер для всех компонентов бота."""
    
    def __init__(self, component: str):
        self.logger = structlog.get_logger(component)
    
    def log_user_action(self, chat_id: int, user_id: int, action: str, **kwargs):
        """Логирует действие пользователя."""
        self.logger.info(
            "user_action",
            chat_id=str(chat_id),
            user_id=str(user_id), 
            action=action,
            **kwargs
        )
    
    def log_llm_request(self, model: str, tokens: int, latency: float, success: bool = True):
        """Логирует запрос к LLM."""
        self.logger.info(
            "llm_request",
            model=model,
            tokens=tokens,
            latency_sec=round(latency, 3),
            success=success
        )
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """Логирует ошибку с контекстом."""
        self.logger.error(
            "error_occurred",
            error_type=type(error).__name__,
            error_message=str(error),
            context=context or {}
        )
    
    def log_performance(self, operation: str, duration: float, **metrics):
        """Логирует метрики производительности."""
        self.logger.info(
            "performance_metric",
            operation=operation,
            duration_sec=round(duration, 3),
            **metrics
        )
    
    @contextmanager
    def timed_operation(self, operation: str, **context):
        """Context manager для измерения времени операций."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.log_performance(operation, duration, **context)

# Глобальные логгеры для разных компонентов
database_logger = BotLogger("database")
llm_logger = BotLogger("llm")
handlers_logger = BotLogger("handlers")
core_logger = BotLogger("core")

# Метрики для мониторинга
class BotMetrics:
    """Сбор метрик бота для мониторинга."""
    
    def __init__(self):
        self.metrics = {
            "messages_processed": 0,
            "llm_requests": 0,
            "llm_errors": 0,
            "database_operations": 0,
            "database_errors": 0,
            "active_chats": set(),
            "response_times": [],
            "uptime_start": time.time()
        }
    
    def increment_messages(self):
        self.metrics["messages_processed"] += 1
    
    def increment_llm_requests(self):
        self.metrics["llm_requests"] += 1
    
    def increment_llm_errors(self):
        self.metrics["llm_errors"] += 1
    
    def add_chat(self, chat_id: int):
        self.metrics["active_chats"].add(chat_id)
    
    def add_response_time(self, time_sec: float):
        # Храним только последние 1000 времен ответа
        self.metrics["response_times"].append(time_sec)
        if len(self.metrics["response_times"]) > 1000:
            self.metrics["response_times"].pop(0)
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает текущую статистику."""
        response_times = self.metrics["response_times"]
        
        return {
            "messages_processed": self.metrics["messages_processed"],
            "llm_requests": self.metrics["llm_requests"],
            "llm_errors": self.metrics["llm_errors"],
            "llm_error_rate": self.metrics["llm_errors"] / max(1, self.metrics["llm_requests"]),
            "database_operations": self.metrics["database_operations"],
            "database_errors": self.metrics["database_errors"],
            "active_chats_count": len(self.metrics["active_chats"]),
            "uptime_seconds": time.time() - self.metrics["uptime_start"],
            "avg_response_time": sum(response_times) / len(response_times) if response_times else 0,
            "p95_response_time": sorted(response_times)[int(len(response_times) * 0.95)] if response_times else 0
        }

# Глобальный экземпляр метрик
bot_metrics = BotMetrics()

# Декораторы для автоматического логирования
def log_function_call(logger: BotLogger):
    """Декоратор для автоматического логирования вызовов функций."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            with logger.timed_operation(func.__name__):
                try:
                    result = await func(*args, **kwargs)
                    logger.logger.debug(f"{func.__name__}_completed", args_count=len(args))
                    return result
                except Exception as e:
                    logger.log_error(e, {"function": func.__name__, "args_count": len(args)})
                    raise
        
        def sync_wrapper(*args, **kwargs):
            with logger.timed_operation(func.__name__):
                try:
                    result = func(*args, **kwargs)
                    logger.logger.debug(f"{func.__name__}_completed", args_count=len(args))
                    return result
                except Exception as e:
                    logger.log_error(e, {"function": func.__name__, "args_count": len(args)})
                    raise
        
        # Возвращаем соответствующий wrapper
        if hasattr(func, '__call__') and hasattr(func, '__code__'):
            return async_wrapper if 'async' in str(func) else sync_wrapper
        return sync_wrapper
    
    return decorator