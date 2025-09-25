"""
Основная бизнес-логика бота
Модули для профилирования, анализа отношений и стилей общения
"""

from .profiles import (
    update_person_profile,
    person_prompt_addon,
    get_user_profile_for_display
)

from .relations import (
    analyze_group_dynamics,
    get_user_clash_summary,
    find_alliance_opportunities,
    get_manipulation_context
)

from .style_analysis import (
    style_analyzer,
    analyze_user_style,
    get_style_adaptation_prompt
)

__all__ = [
    # Профилирование
    "update_person_profile",
    "person_prompt_addon", 
    "get_user_profile_for_display",
    
    # Групповая динамика
    "analyze_group_dynamics",
    "get_user_clash_summary",
    "find_alliance_opportunities",
    "get_manipulation_context",
    
    # Анализ стиля
    "style_analyzer",
    "analyze_user_style",
    "get_style_adaptation_prompt"
]
