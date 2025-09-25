"""
Продвинутые фильтры текста и система безопасности
"""

import re
import hashlib  
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class ThreatLevel(Enum):
    """Уровни угроз в сообщениях."""
    SAFE = "safe"
    LOW = "low" 
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class FilterResult:
    """Результат фильтрации сообщения."""
    is_safe: bool
    threat_level: ThreatLevel
    violations: List[str]
    filtered_text: Optional[str] = None
    confidence: float = 0.0

class AdvancedTextFilter:
    """Продвинутая система фильтрации текста."""
    
    def __init__(self):
        # Расширенные категории нежелательного контента
        self.spam_patterns = [
            r'(?:https?://|www\.)[^\s]+',  # URLs
            r'@[a-zA-Z0-9_]+',             # Mentions
            r'#[a-zA-Z0-9_]+',             # Hashtags
            r'(?:купи|продам|реклама|скидка|акция)',  # Commercial
            r'(?:подпишись|лайк|репост)',  # Social engineering
        ]
        
        self.personal_data_patterns = [
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Card numbers
            r'\b\d{3}[-\s]?\d{3}[-\s]?\d{4}\b',             # Phone numbers
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Emails
            r'\b\d{3}-\d{2}-\d{4}\b',                       # SSN-like
        ]
        
        self.hate_speech_patterns = [
            r'(?:убить|смерть|умри)',
            r'(?:расист|фашист|нацист)',
            r'(?:урод|дегенерат|мразь)',
        ]
        
        # Паттерны для детекции LLM-выдачи себя
        self.llm_leak_patterns = [
            r'я\s+(?:искусственный\s+)?интеллект',
            r'как\s+(?:ии|ай|ai|языковая)\s+модель',
            r'я\s+не\s+могу\s+(?:чувствовать|испытывать)',
            r'мои\s+алгоритмы',
            r'в\s+моей\s+базе\s+данных',
            r'я\s+(?:был\s+)?(?:обучен|создан)\s+(?:на|для)',
        ]
        
        # Компиляция регексов для производительности
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Компилирует все паттерны в регексы."""
        self.spam_re = re.compile('|'.join(self.spam_patterns), re.IGNORECASE)
        self.personal_data_re = re.compile('|'.join(self.personal_data_patterns), re.IGNORECASE)
        self.hate_speech_re = re.compile('|'.join(self.hate_speech_patterns), re.IGNORECASE)
        self.llm_leak_re = re.compile('|'.join(self.llm_leak_patterns), re.IGNORECASE)
    
    def analyze_text(self, text: str) -> FilterResult:
        """Анализирует текст на предмет различных нарушений."""
        if not text:
            return FilterResult(True, ThreatLevel.SAFE, [])
        
        violations = []
        threat_level = ThreatLevel.SAFE
        
        # Проверка на спам
        if self.spam_re.search(text):
            violations.append("spam_content")
            threat_level = max(threat_level, ThreatLevel.LOW)
        
        # Проверка персональных данных
        if self.personal_data_re.search(text):
            violations.append("personal_data")
            threat_level = max(threat_level, ThreatLevel.HIGH)
        
        # Проверка hate speech
        if self.hate_speech_re.search(text):
            violations.append("hate_speech")
            threat_level = max(threat_level, ThreatLevel.CRITICAL)
        
        # Проверка на выдачу себя LLM
        if self.llm_leak_re.search(text):
            violations.append("llm_leak")
            threat_level = max(threat_level, ThreatLevel.MEDIUM)
        
        # Дополнительные проверки
        if len(text) > 4000:  # Слишком длинный текст
            violations.append("excessive_length")
            threat_level = max(threat_level, ThreatLevel.LOW)
        
        if text.count('!') > 10:  # Слишком много восклицательных знаков
            violations.append("excessive_punctuation")
            threat_level = max(threat_level, ThreatLevel.LOW)
        
        is_safe = threat_level in [ThreatLevel.SAFE, ThreatLevel.LOW]
        
        return FilterResult(
            is_safe=is_safe,
            threat_level=threat_level,
            violations=violations,
            confidence=0.8 if violations else 1.0
        )
    
    def filter_llm_response(self, text: str) -> str:
        """Специальная фильтрация для ответов LLM."""
        if not text:
            return text
        
        # Удаляем LLM-leak паттерны
        filtered = self.llm_leak_re.sub('', text)
        
        # Удаляем слишком вежливые фразы (не в характере токсичного бота)
        polite_patterns = [
            r'извините,?\s*',
            r'пожалуйста,?\s*',
            r'с\s+уважением,?\s*',
            r'благодарю\s+вас,?\s*'
        ]
        
        for pattern in polite_patterns:
            filtered = re.sub(pattern, '', filtered, flags=re.IGNORECASE)
        
        # Очищаем лишние пробелы
        filtered = re.sub(r'\s+', ' ', filtered).strip()
        
        return filtered or "..."

class RateLimiter:
    """Система ограничения частоты запросов."""
    
    def __init__(self):
        self.user_requests: Dict[int, List[float]] = {}
        self.chat_requests: Dict[int, List[float]] = {}
        
        # Лимиты (запросов в секунду)
        self.user_limit = 5  # 5 сообщений в минуту на пользователя
        self.chat_limit = 20  # 20 сообщений в минуту на чат
        self.window = 60  # Окно в секундах
    
    def is_allowed(self, user_id: int, chat_id: int) -> Tuple[bool, str]:
        """Проверяет, разрешен ли запрос от пользователя."""
        import time
        current_time = time.time()
        
        # Очищаем старые записи
        self._cleanup_old_requests(current_time)
        
        # Проверяем лимит пользователя
        user_requests = self.user_requests.get(user_id, [])
        if len(user_requests) >= self.user_limit:
            return False, f"Превышен лимит сообщений ({self.user_limit}/мин)"
        
        # Проверяем лимит чата
        chat_requests = self.chat_requests.get(chat_id, [])
        if len(chat_requests) >= self.chat_limit:
            return False, f"Превышен лимит чата ({self.chat_limit}/мин)"
        
        # Добавляем текущий запрос
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        if chat_id not in self.chat_requests:
            self.chat_requests[chat_id] = []
        
        self.user_requests[user_id].append(current_time)
        self.chat_requests[chat_id].append(current_time)
        
        return True, ""
    
    def _cleanup_old_requests(self, current_time: float):
        """Удаляет старые запросы вне окна."""
        cutoff_time = current_time - self.window
        
        for user_id in list(self.user_requests.keys()):
            self.user_requests[user_id] = [
                t for t in self.user_requests[user_id] if t > cutoff_time
            ]
            if not self.user_requests[user_id]:
                del self.user_requests[user_id]
        
        for chat_id in list(self.chat_requests.keys()):
            self.chat_requests[chat_id] = [
                t for t in self.chat_requests[chat_id] if t > cutoff_time
            ]
            if not self.chat_requests[chat_id]:
                del self.chat_requests[chat_id]

# Глобальные экземпляры
text_filter = AdvancedTextFilter()
rate_limiter = RateLimiter()

def safe_filter_text(text: str) -> FilterResult:
    """Основная функция для фильтрации текста."""
    return text_filter.analyze_text(text)

def filter_bot_response(text: str) -> str:
    """Фильтрует ответ бота перед отправкой."""
    return text_filter.filter_llm_response(text)

def check_rate_limit(user_id: int, chat_id: int) -> Tuple[bool, str]:
    """Проверяет ограничения частоты запросов."""
    return rate_limiter.is_allowed(user_id, chat_id)