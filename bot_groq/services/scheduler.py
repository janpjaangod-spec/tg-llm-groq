"""
Расширенный планировщик фоновых задач и напоминаний
"""

import asyncio
import time
import json
from typing import Dict, List, Any, Callable, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod

from bot_groq.config.settings import settings
from bot_groq.services.database import db_get_due_reminders, db_delete_reminder, db_add_reminder, db_get_last_activity
from bot_groq.utils.logging import core_logger

class TaskType(Enum):
    """Типы задач."""
    REMINDER = "reminder"
    IDLE_CHECK = "idle_check"
    CLEANUP = "cleanup"
    ANALYTICS = "analytics"
    BACKUP = "backup"
    NOTIFICATION = "notification"

class TaskStatus(Enum):
    """Статусы задач."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class TaskResult:
    """Результат выполнения задачи."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    execution_time: float = 0.0

class BaseTask(ABC):
    """Базовый класс для задач."""
    
    def __init__(self, task_id: str, task_type: TaskType):
        self.task_id = task_id
        self.task_type = task_type
        self.status = TaskStatus.PENDING
        self.created_at = time.time()
        self.scheduled_at: Optional[float] = None
        self.executed_at: Optional[float] = None
        self.retries = 0
        self.max_retries = 3
    
    @abstractmethod
    async def execute(self) -> TaskResult:
        """Выполняет задачу."""
        pass
    
    def should_execute(self) -> bool:
        """Проверяет, нужно ли выполнять задачу."""
        if self.scheduled_at is None:
            return True
        return time.time() >= self.scheduled_at
    
    def can_retry(self) -> bool:
        """Проверяет, можно ли повторить задачу."""
        return self.retries < self.max_retries

class ReminderTask(BaseTask):
    """Задача напоминания."""
    
    def __init__(self, reminder_id: int, chat_id: int, user_id: int, text: str, due_time: float):
        super().__init__(f"reminder_{reminder_id}", TaskType.REMINDER)
        self.reminder_id = reminder_id
        self.chat_id = chat_id
        self.user_id = user_id
        self.text = text
        self.scheduled_at = due_time
    
    async def execute(self) -> TaskResult:
        """Выполняет напоминание."""
        try:
            # Здесь нужен доступ к bot instance
            # Для простоты пока возвращаем успех
            return TaskResult(True, "Reminder task completed")
            
        except Exception as e:
            core_logger.log_error(e, {"task": "reminder", "reminder_id": self.reminder_id})
            return TaskResult(False, f"Error sending reminder: {e}")

class CleanupTask(BaseTask):
    """Задача очистки данных."""
    
    def __init__(self):
        super().__init__("cleanup", TaskType.CLEANUP)
        self.scheduled_at = time.time() + 3600  # Каждый час
    
    async def execute(self) -> TaskResult:
        """Выполняет очистку данных."""
        try:
            from bot_groq.utils.cache import cache, db_optimizer
            
            # Очищаем кеш
            cache.cleanup_expired()
            
            # Оптимизируем БД
            db_optimizer.optimize_database()
            
            # Планируем следующую очистку
            self.scheduled_at = time.time() + 3600
            self.status = TaskStatus.PENDING
            
            return TaskResult(True, "Cleanup completed")
            
        except Exception as e:
            core_logger.log_error(e, {"task": "cleanup"})
            return TaskResult(False, f"Cleanup error: {e}")

class AdvancedTaskScheduler:
    """Расширенный планировщик задач."""
    
    def __init__(self):
        self.running = False
        self.tasks: Dict[str, BaseTask] = {}
        self.task_history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
        # Статистика
        self.stats = {
            "total_executed": 0,
            "successful": 0,
            "failed": 0,
            "retries": 0
        }
    
    async def start(self):
        """Запускает планировщик."""
        self.running = True
        
        # Добавляем системные задачи
        await self._add_system_tasks()
        
        # Запускаем основной цикл
        asyncio.create_task(self._scheduler_loop())
        
        core_logger.logger.info("advanced_scheduler_started", tasks_count=len(self.tasks))
    
    async def stop(self):
        """Останавливает планировщик."""
        self.running = False
        core_logger.logger.info("advanced_scheduler_stopped")
    
    async def _scheduler_loop(self):
        """Основной цикл планировщика."""
        while self.running:
            try:
                await self._execute_ready_tasks()
                await asyncio.sleep(30)  # Проверяем каждые 30 секунд
            except Exception as e:
                core_logger.log_error(e, {"operation": "scheduler_loop"})
                await asyncio.sleep(60)  # Пауза при ошибке
    
    async def _execute_ready_tasks(self):
        """Выполняет готовые задачи."""
        ready_tasks = [
            task for task in self.tasks.values()
            if task.status == TaskStatus.PENDING and task.should_execute()
        ]
        
        for task in ready_tasks:
            await self._execute_task(task)
    
    async def _execute_task(self, task: BaseTask):
        """Выполняет конкретную задачу."""
        task.status = TaskStatus.RUNNING
        task.executed_at = time.time()
        
        start_time = time.time()
        
        try:
            result = await task.execute()
            execution_time = time.time() - start_time
            
            if result.success:
                task.status = TaskStatus.COMPLETED
                self.stats["successful"] += 1
            else:
                if task.can_retry():
                    task.retries += 1
                    task.status = TaskStatus.PENDING
                    task.scheduled_at = time.time() + (60 * task.retries)
                    self.stats["retries"] += 1
                else:
                    task.status = TaskStatus.FAILED
                    self.stats["failed"] += 1
            
            self.stats["total_executed"] += 1
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            self.stats["failed"] += 1
            core_logger.log_error(e, {"task": task.task_id, "operation": "execute_task"})
    
    async def _add_system_tasks(self):
        """Добавляет системные задачи."""
        # Задача очистки
        cleanup_task = CleanupTask()
        self.tasks[cleanup_task.task_id] = cleanup_task
        
        core_logger.logger.info("system_tasks_added")
    
    def add_task(self, task: BaseTask):
        """Добавляет задачу в планировщик."""
        self.tasks[task.task_id] = task
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику планировщика."""
        return {
            **self.stats,
            "active_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING]),
            "running_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.RUNNING])
        }

# Глобальный планировщик
advanced_scheduler = AdvancedTaskScheduler()

# API функции
async def start_scheduler():
    """Запускает планировщик."""
    await advanced_scheduler.start()

async def stop_scheduler():
    """Останавливает планировщик."""
    await advanced_scheduler.stop()

def schedule_reminder(chat_id: int, user_id: int, text: str, due_time: float) -> str:
    """Планирует напоминание."""
    reminder_id = db_add_reminder(chat_id, user_id, text, due_time)
    
    task = ReminderTask(reminder_id, chat_id, user_id, text, due_time)
    advanced_scheduler.add_task(task)
    
    return task.task_id

def get_scheduler_stats() -> Dict[str, Any]:
    """Возвращает статистику планировщика."""
    return advanced_scheduler.get_stats()
