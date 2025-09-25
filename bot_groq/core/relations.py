import json
import random
import time
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

from bot_groq.config.settings import settings
from bot_groq.services.database import db_get_chat_tail

def get_user_clash_summary(chat_id: int, user1_id: int, user2_id: int, limit: int = 50) -> str:
    """
    Анализирует взаимодействие между двумя пользователями.
    """
    # Получаем последние сообщения
    messages = db_get_chat_tail(chat_id, limit * 2)
    if not messages:
        return ""
    
    # Фильтруем сообщения от наших пользователей
    user_messages = [m for m in messages if m.get("user_id") in (user1_id, user2_id)]
    if len(user_messages) < 5:
        return ""
    
    # Анализируем паттерны взаимодействия
    interactions = []
    prev_msg = None
    
    for msg in user_messages:
        if prev_msg and prev_msg.get("user_id") != msg.get("user_id"):
            # Это ответ между пользователями
            time_diff = msg.get("timestamp", 0) - prev_msg.get("timestamp", 0)
            if time_diff < 300:  # менее 5 минут - считаем взаимодействием
                interactions.append({
                    "user1": prev_msg.get("user_id"),
                    "user2": msg.get("user_id"),
                    "text1": prev_msg.get("text", "")[:100],
                    "text2": msg.get("text", "")[:100],
                    "quick": time_diff < 60
                })
        prev_msg = msg
    
    if not interactions:
        return ""
    
    # Анализируем тон взаимодействий
    positive_words = ["спасибо", "круто", "согласен", "правильно", "ахах", "лол", "+1", "да", "точно"]
    negative_words = ["не согласен", "хрень", "бред", "глупо", "нет", "фигня", "ерунда"]
    
    clash_score = 0
    quick_responses = 0
    total_interactions = len(interactions)
    
    for inter in interactions[-10:]:  # берем последние 10 взаимодействий
        text = (inter["text1"] + " " + inter["text2"]).lower()
        
        # Быстрые ответы могут означать конфликт
        if inter["quick"]:
            quick_responses += 1
        
        # Анализ тона
        pos_count = sum(1 for w in positive_words if w in text)
        neg_count = sum(1 for w in negative_words if w in text)
        
        if neg_count > pos_count:
            clash_score += 1
        elif pos_count > neg_count:
            clash_score -= 1
    
    # Формируем резюме
    if clash_score > 2 or quick_responses > 5:
        return f"Между этими пользователями явное напряжение. {quick_responses} быстрых перепалок из {total_interactions} взаимодействий."
    elif clash_score < -2:
        return f"Пользователи хорошо ладят. Дружелюбное общение в {total_interactions} взаимодействиях."
    else:
        return f"Нейтральное общение между пользователями. {total_interactions} взаимодействий."

def analyze_group_dynamics(chat_id: int, limit: int = 100) -> Dict[str, Any]:
    """
    Анализирует общую динамику группы.
    """
    messages = db_get_chat_tail(chat_id, limit)
    if not messages:
        return {}
    
    # Статистика активности
    user_activity = defaultdict(int)
    user_last_seen = {}
    reply_chains = []
    
    for msg in messages:
        user_id = msg.get("user_id")
        if user_id:
            user_activity[user_id] += 1
            user_last_seen[user_id] = msg.get("timestamp", 0)
    
    # Определяем самых активных
    most_active = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Анализируем цепочки реплаев
    current_time = time.time()
    recent_speakers = []
    
    for msg in messages[-20:]:
        user_id = msg.get("user_id")
        if user_id and user_id not in recent_speakers[-3:]:  # избегаем повторов
            recent_speakers.append(user_id)
    
    # Определяем "молчунов"
    silent_threshold = current_time - 7 * 24 * 3600  # 7 дней
    silent_users = [uid for uid, last_time in user_last_seen.items() 
                   if last_time < silent_threshold and user_activity[uid] > 5]
    
    return {
        "total_messages": len(messages),
        "active_users": len(user_activity),
        "most_active": most_active,
        "recent_speakers": recent_speakers[-5:],
        "silent_users": silent_users,
        "avg_activity": sum(user_activity.values()) / max(1, len(user_activity))
    }

def get_group_tension_points(chat_id: int) -> List[str]:
    """
    Ищет точки напряжения в группе.
    """
    messages = db_get_chat_tail(chat_id, 50)
    if not messages:
        return []
    
    tension_indicators = []
    
    # Паттерны конфликтов
    conflict_patterns = [
        "не согласен", "ты не прав", "бред несешь", "хватит", "заткнись",
        "иди нахуй", "отвали", "не лезь", "твое дело", "не твоя тема"
    ]
    
    # Анализируем последние сообщения на конфликтность
    conflict_count = 0
    for msg in messages:
        text = (msg.get("text") or "").lower()
        if any(pattern in text for pattern in conflict_patterns):
            conflict_count += 1
    
    if conflict_count > 3:
        tension_indicators.append("Повышенная конфликтность в последних сообщениях")
    
    # Анализируем активность (слишком тихо или слишком шумно)
    dynamics = analyze_group_dynamics(chat_id)
    
    if dynamics.get("active_users", 0) < 2:
        tension_indicators.append("Группа практически мертва")
    elif dynamics.get("avg_activity", 0) > 10:
        tension_indicators.append("Слишком много активности - возможна перепалка")
    
    if len(dynamics.get("silent_users", [])) > 3:
        tension_indicators.append("Много участников ушли в молчанку")
    
    return tension_indicators

def generate_conflict_prompt(chat_id: int, user1_id: int, user2_id: int) -> str:
    """
    Генерирует промпт для эскалации конфликта между пользователями.
    """
    clash_summary = get_user_clash_summary(chat_id, user1_id, user2_id)
    group_dynamics = analyze_group_dynamics(chat_id)
    
    if not clash_summary:
        return ""
    
    prompt_parts = [
        f"АНАЛИЗ КОНФЛИКТА: {clash_summary}",
        f"Активность группы: {group_dynamics.get('total_messages', 0)} сообщений от {group_dynamics.get('active_users', 0)} участников"
    ]
    
    # Стратегии эскалации
    strategies = [
        "Подлей масла в огонь - найди болевую точку каждого",
        "Сравни их достижения в пользу одного против другого", 
        "Вспомни их прошлые промахи и ткни носом",
        "Намекни на скрытые мотивы одного из них"
    ]
    
    prompt_parts.append(f"СТРАТЕГИЯ: {random.choice(strategies)}")
    
    return "\n".join(prompt_parts)

def find_alliance_opportunities(chat_id: int, target_user_id: int) -> List[Tuple[int, str]]:
    """
    Ищет пользователей, которых можно настроить против цели.
    """
    messages = db_get_chat_tail(chat_id, 100)
    if not messages:
        return []
    
    # Анализируем, кто с кем не ладит
    user_interactions = defaultdict(list)
    
    for i, msg in enumerate(messages):
        if msg.get("user_id") == target_user_id:
            # Ищем ответы на сообщения цели
            for j in range(i + 1, min(i + 5, len(messages))):
                reply_msg = messages[j]
                if reply_msg.get("user_id") != target_user_id:
                    reply_text = reply_msg.get("text", "").lower()
                    
                    negative_indicators = ["не согласен", "бред", "хрень", "нет", "фигня"]
                    if any(ind in reply_text for ind in negative_indicators):
                        user_interactions[reply_msg.get("user_id")].append("negative")
                    else:
                        user_interactions[reply_msg.get("user_id")].append("neutral")
    
    # Находим потенциальных союзников (тех, кто часто не соглашается с целью)
    potential_allies = []
    for user_id, interactions in user_interactions.items():
        if len(interactions) >= 3:
            negative_ratio = interactions.count("negative") / len(interactions)
            if negative_ratio > 0.4:  # более 40% негативных взаимодействий
                reason = f"Часто не соглашается с целью ({negative_ratio:.1%} конфликтов)"
                potential_allies.append((user_id, reason))
    
    return potential_allies[:3]  # максимум 3 союзника

def get_manipulation_context(chat_id: int) -> str:
    """
    Создает контекст для манипулятивного поведения.
    """
    tensions = get_group_tension_points(chat_id)
    dynamics = analyze_group_dynamics(chat_id)
    
    context_parts = []
    
    if tensions:
        context_parts.append(f"УЯЗВИМОСТИ ГРУППЫ: {'; '.join(tensions)}")
    
    if dynamics.get("most_active"):
        top_user = dynamics["most_active"][0]
        context_parts.append(f"ЛИДЕР АКТИВНОСТИ: пользователь {top_user[0]} ({top_user[1]} сообщений)")
    
    if dynamics.get("silent_users"):
        context_parts.append(f"МОЛЧУНЫ: {len(dynamics['silent_users'])} пользователей ушли в тень")
    
    strategies = [
        "Играй на противоречиях - найди разногласия и раздувай их",
        "Используй лидера мнений - через него влияй на остальных", 
        "Атакуй молчунов - выведи их из зоны комфорта",
        "Создавай коалиции - настраивай одних против других"
    ]
    
    context_parts.append(f"ТАКТИКА: {random.choice(strategies)}")
    
    return "\n".join(context_parts) if context_parts else ""