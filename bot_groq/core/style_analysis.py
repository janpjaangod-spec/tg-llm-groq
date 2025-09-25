import re
import random
from typing import Dict, List, Any, Optional
from collections import Counter

class StyleAnalyzer:
    """Анализатор стиля общения пользователя."""
    
    def __init__(self):
        # Паттерны для определения стиля
        self.formal_indicators = [
            "пожалуйста", "будьте добры", "не могли бы вы", "извините", 
            "благодарю", "с уважением", "позвольте", "разрешите"
        ]
        
        self.casual_indicators = [
            "привет", "хай", "ку", "как дела", "чё как", "погнали", 
            "окей", "пока", "увидимся", "лады"
        ]
        
        self.aggressive_indicators = [
            "сука", "блять", "хуй", "пизда", "ебать", "нахуй", "охуел", 
            "заткнись", "отвали", "иди нахер", "пошел нахуй"
        ]
        
        self.ironic_indicators = [
            "ага", "конечно", "ну да", "еще чего", "ясно-понятно", 
            "как же", "ну конечно же", "прям так", "ага щас"
        ]
        
        self.emotional_indicators = [
            "!!!", "??", "!!!", "ахахах", "ололо", "вау", "ого", 
            "боже", "капец", "пиздец", "охреть"
        ]
    
    def analyze_message_style(self, text: str) -> Dict[str, Any]:
        """Анализирует стиль конкретного сообщения."""
        if not text:
            return {}
        
        text_lower = text.lower()
        
        # Подсчет индикаторов разных стилей
        formal_score = sum(1 for ind in self.formal_indicators if ind in text_lower)
        casual_score = sum(1 for ind in self.casual_indicators if ind in text_lower)
        aggressive_score = sum(1 for ind in self.aggressive_indicators if ind in text_lower)
        ironic_score = sum(1 for ind in self.ironic_indicators if ind in text_lower)
        emotional_score = sum(1 for ind in self.emotional_indicators if ind in text)
        
        # Дополнительные метрики
        caps_ratio = sum(1 for c in text if c.isupper()) / max(1, len(text))
        exclamation_count = text.count('!')
        question_count = text.count('?')
        emoji_count = len(re.findall(r'[😀-🙏]', text))
        
        return {
            "formal": formal_score,
            "casual": casual_score, 
            "aggressive": aggressive_score,
            "ironic": ironic_score,
            "emotional": emotional_score,
            "caps_ratio": caps_ratio,
            "exclamations": exclamation_count,
            "questions": question_count,
            "emojis": emoji_count,
            "length": len(text),
            "words": len(text.split())
        }
    
    def get_dominant_style(self, style_metrics: Dict[str, Any]) -> str:
        """Определяет доминирующий стиль на основе метрик."""
        styles = {
            "formal": style_metrics.get("formal", 0),
            "casual": style_metrics.get("casual", 0),
            "aggressive": style_metrics.get("aggressive", 0),
            "ironic": style_metrics.get("ironic", 0),
            "emotional": style_metrics.get("emotional", 0)
        }
        
        # Дополнительные правила
        if style_metrics.get("caps_ratio", 0) > 0.3:
            styles["aggressive"] += 2
        
        if style_metrics.get("exclamations", 0) > 2:
            styles["emotional"] += 1
        
        if style_metrics.get("emojis", 0) > 0:
            styles["casual"] += 1
        
        # Определяем максимальный стиль
        max_style = max(styles.items(), key=lambda x: x[1])
        
        if max_style[1] == 0:
            return "neutral"
        
        return max_style[0]
    
    def generate_style_adaptation(self, user_style: str, bot_personality: str = "toxic") -> Dict[str, str]:
        """Генерирует адаптацию стиля бота под пользователя."""
        
        adaptations = {
            "formal": {
                "toxic": "Отвечай подчеркнуто вежливо, но с ядовитым подтекстом. 'Благодарю за столь... оригинальное мнение.'",
                "friendly": "Поддерживай формальный тон, используй 'Вы', избегай сленга.",
                "neutral": "Умеренно формальный стиль, без крайностей."
            },
            "casual": {
                "toxic": "Отвечай в том же стиле, но добавляй колкости. 'Ну окей, только вот проблема...'",
                "friendly": "Поддерживай непринужденный тон, используй сленг и эмодзи.",
                "neutral": "Обычный разговорный стиль."
            },
            "aggressive": {
                "toxic": "Отзеркаливай агрессию, но умнее. Бей по болевым точкам, а не матом.",
                "friendly": "Сглаживай агрессию юмором и переводи в конструктив.",
                "neutral": "Не поддавайся на провокации, отвечай спокойно."
            },
            "ironic": {
                "toxic": "Ирония против иронии. Будь еще более саркастичным.",
                "friendly": "Поддерживай легкую иронию, но дружелюбно.",
                "neutral": "Умеренная ирония без перегибов."
            },
            "emotional": {
                "toxic": "Используй эмоциональность против него же. 'Вау, какая глубокая мысль!'",
                "friendly": "Разделяй эмоции, поддерживай энтузиазм.",
                "neutral": "Умеренно эмоциональные ответы."
            },
            "neutral": {
                "toxic": "Стандартная токсичность - ищи слабые места и бей точечно.",
                "friendly": "Обычный дружелюбный стиль.",
                "neutral": "Нейтральные ответы без особенностей."
            }
        }
        
        return {
            "instruction": adaptations.get(user_style, {}).get(bot_personality, "Обычный стиль ответа."),
            "style": user_style,
            "personality": bot_personality
        }
    
    def analyze_conversation_dynamics(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Анализирует динамику развития разговора."""
        if not messages:
            return {}
        
        styles_over_time = []
        aggression_trend = []
        engagement_trend = []
        
        for msg in messages:
            text = msg.get("text", "")
            if text:
                style_metrics = self.analyze_message_style(text)
                dominant_style = self.get_dominant_style(style_metrics)
                
                styles_over_time.append(dominant_style)
                aggression_trend.append(style_metrics.get("aggressive", 0))
                engagement_trend.append(style_metrics.get("words", 0))
        
        # Анализ трендов
        style_changes = len(set(styles_over_time))
        avg_aggression = sum(aggression_trend) / max(1, len(aggression_trend))
        avg_engagement = sum(engagement_trend) / max(1, len(engagement_trend))
        
        # Определение фазы разговора
        if len(messages) < 3:
            conversation_phase = "beginning"
        elif avg_aggression > 1:
            conversation_phase = "heated"
        elif style_changes > 3:
            conversation_phase = "dynamic"
        else:
            conversation_phase = "stable"
        
        return {
            "styles_sequence": styles_over_time,
            "style_diversity": style_changes,
            "avg_aggression": avg_aggression,
            "avg_engagement": avg_engagement,
            "conversation_phase": conversation_phase,
            "dominant_style": max(set(styles_over_time), key=styles_over_time.count) if styles_over_time else "neutral"
        }
    
    def get_response_strategy(self, user_messages: List[str], bot_personality: str = "toxic") -> str:
        """Определяет стратегию ответа на основе истории сообщений пользователя."""
        
        if not user_messages:
            return "Стандартный ответ"
        
        # Анализируем последние сообщения
        recent_styles = []
        for msg in user_messages[-5:]:  # последние 5 сообщений
            style_metrics = self.analyze_message_style(msg)
            style = self.get_dominant_style(style_metrics)
            recent_styles.append(style)
        
        # Определяем паттерн
        if len(set(recent_styles)) == 1:
            # Пользователь стабилен в стиле
            stable_style = recent_styles[0]
            adaptation = self.generate_style_adaptation(stable_style, bot_personality)
            return f"СТАБИЛЬНЫЙ СТИЛЬ ({stable_style}): {adaptation['instruction']}"
        
        elif "aggressive" in recent_styles[-2:]:
            # Недавняя агрессия
            if bot_personality == "toxic":
                return "АГРЕССИЯ ДЕТЕКТЕД: Эскалируй конфликт, но умно. Не опускайся до мата, бей по существу."
            else:
                return "АГРЕССИЯ ДЕТЕКТЕД: Сглаживай конфликт, переводи в конструктив."
        
        elif len(set(recent_styles)) > 3:
            # Пользователь меняет стили
            return "ХАОТИЧНОЕ ПОВЕДЕНИЕ: Адаптируйся под каждый ответ, будь непредсказуемым."
        
        else:
            # Обычная ситуация
            last_style = recent_styles[-1] if recent_styles else "neutral"
            adaptation = self.generate_style_adaptation(last_style, bot_personality)
            return f"АДАПТАЦИЯ К СТИЛЮ: {adaptation['instruction']}"

# Глобальный экземпляр анализатора
style_analyzer = StyleAnalyzer()

def analyze_user_style(messages: List[str]) -> Dict[str, Any]:
    """Анализирует стиль пользователя по списку сообщений."""
    return style_analyzer.analyze_conversation_dynamics([{"text": msg} for msg in messages])

def get_style_adaptation_prompt(user_messages: List[str], bot_personality: str = "toxic") -> str:
    """Возвращает промпт для адаптации стиля бота."""
    return style_analyzer.get_response_strategy(user_messages, bot_personality)