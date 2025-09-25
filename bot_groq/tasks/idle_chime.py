import asyncio
import time
import random
import logging
from typing import Dict
from aiogram import Bot

from bot_groq.config.settings import settings
from bot_groq.services.database import (
    db_get_all_groups, db_get_last_activity, db_runtime_get, db_runtime_all, db_get_settings
)
from bot_groq.services.llm import llm_text

logger = logging.getLogger(__name__)

_last_chime: Dict[int, float] = {}

IDLE_PROMPTS = [
    "В чате мертвяк. Поддери их чуть-чуть язвительно.",
    "Тишина уже слишком долго. Брось провокационный комментарий.",
    "Сделай язвительный пинг чтобы расшевелить болото.",
    "Скучно. Подкинь искру разговора в стиле токсика.",
]

async def idle_chime_worker(bot: Bot):
    """Фоновая задача: проверяет чаты и пишет что-нибудь после долгой тишины.
    Условия:
      - включено settings.idle_enabled
      - прошло >= idle_chime_minutes с последней активности
      - прошло >= idle_chime_cooldown с последнего нашего чима
      - не в 'тихих часах'
    """
    await asyncio.sleep(10)  # даём стартовым процессам устаканиться
    while True:
        try:
            if not settings.idle_enabled:
                await asyncio.sleep(settings.idle_check_every)
                continue
            now = time.time()
            quiet_start = settings.quiet_hours_start
            quiet_end = settings.quiet_hours_end
            hour = int(time.strftime('%H', time.localtime(now)))
            def in_quiet(h: int) -> bool:
                if quiet_start < quiet_end:
                    return quiet_start <= h < quiet_end
                # Перехлёст через полночь
                return h >= quiet_start or h < quiet_end
            if in_quiet(hour):
                await asyncio.sleep(settings.idle_check_every)
                continue
            # Получаем группы из истории
            groups = db_get_all_groups()  # list of tuples [(chat_id,), ...]
            for (chat_id_raw,) in groups:
                try:
                    chat_id = int(chat_id_raw)
                except Exception:
                    continue
                last_act = db_get_last_activity(chat_id) or 0
                since = now - last_act
                if since < settings.idle_chime_minutes * 60:
                    continue
                last_sent = _last_chime.get(chat_id, 0)
                if now - last_sent < settings.idle_chime_cooldown:
                    continue
                # Небольшая вероятностная регулировка: если response_chance у чата высокий (runtime), можно понижать
                try:
                    cfg = db_get_settings()
                    chance = int(cfg.get('response_chance', settings.response_chance))
                except Exception:
                    chance = settings.response_chance
                # Чем больше шанс обычных ответов, тем реже пинги
                prob = 0.6 - min(0.4, chance/200.0)
                if random.random() > prob:
                    continue
                prompt = random.choice(IDLE_PROMPTS) + f" (тишина {int(since/60)} мин)"
                try:
                    reply = await llm_text(prompt, max_tokens=0)
                except Exception as e:
                    logger.warning(f"idle_chime llm error chat={chat_id}: {e}")
                    reply = None
                if not reply:
                    continue
                try:
                    await bot.send_message(chat_id, reply)
                    _last_chime[chat_id] = now
                    logger.info(f"[idle_chime] sent to {chat_id} after {int(since/60)}m silence")
                except Exception as e:
                    logger.debug(f"idle_chime send fail chat={chat_id}: {e}")
            await asyncio.sleep(settings.idle_check_every)
        except asyncio.CancelledError:
            logger.info("idle_chime_worker cancelled")
            break
        except Exception as e:
            logger.error(f"idle_chime_worker loop error: {e}")
            await asyncio.sleep(30)

__all__ = ["idle_chime_worker"]
