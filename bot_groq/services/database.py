import sqlite3
import time
import json
from contextlib import closing
from typing import List, Dict, Any, Tuple, Optional

from bot_groq.config.settings import settings
import os
import logging

_db_logger = logging.getLogger("database")
_db_path_logged = False  # чтобы не засорять логи повторениями

def get_db_connection():
    """Возвращает соединение с базой данных.
    Делает папку при необходимости и один раз логирует фактический путь.
    """
    global _db_path_logged
    db_path = settings.db_name
    # Если указали URL по ошибке (например https://...), предупреждаем.
    if db_path.startswith("http://") or db_path.startswith("https://"):
        # Нам явно подсунули не путь, а домен/URL – это распространённая ошибка при настройке ENV.
        raise RuntimeError(
            f"DB_NAME='{db_path}' выглядит как URL. Ожидается путь к файлу, например /data/bot.db"
        )
    # Создаём директорию если путь содержит каталог и он отсутствует
    try:
        parent = os.path.dirname(db_path)
        if parent and parent not in {".", ""}:
            os.makedirs(parent, exist_ok=True)
    except Exception as e:
        _db_logger.warning(f"Не удалось создать директорию для БД '{db_path}': {e}")
    if not _db_path_logged:
        _db_logger.info(f"Использую файл БД: {os.path.abspath(db_path)}")
        _db_path_logged = True
    return sqlite3.connect(db_path)

def initialize_database():
    """Инициализирует базу данных и создает таблицы, если они не существуют."""
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS settings(
            id INTEGER PRIMARY KEY CHECK (id=1),
            system_prompt TEXT NOT NULL,
            model TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS history(
            user_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, ts REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS chat_history(
            chat_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
            ts REAL NOT NULL, user_id TEXT, username TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS chat_activity(
            chat_id TEXT PRIMARY KEY, last_ts REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS user_memory(
            user_id TEXT NOT NULL, value TEXT NOT NULL, ts REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS chat_memory(
            chat_id TEXT NOT NULL, value TEXT NOT NULL, ts REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS reminders(
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL, user_id TEXT NOT NULL,
            text TEXT NOT NULL, due_ts REAL NOT NULL, created_ts REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS daily_mention(
            chat_id TEXT PRIMARY KEY, last_date TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS recent_media(
            chat_id TEXT PRIMARY KEY, file_id TEXT NOT NULL, caption TEXT, ts REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS chat_style(
            chat_id TEXT PRIMARY KEY, style_json TEXT NOT NULL, updated_ts REAL NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS person_profile(
            chat_id TEXT NOT NULL, user_id TEXT NOT NULL,
            profile_json TEXT NOT NULL, updated_ts REAL NOT NULL,
            PRIMARY KEY(chat_id,user_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS relationship_profile(
            chat_id TEXT NOT NULL, user_id_a TEXT NOT NULL, user_id_b TEXT NOT NULL,
            score REAL NOT NULL, tone REAL NOT NULL, addr_json TEXT NOT NULL, last_ts REAL NOT NULL,
            PRIMARY KEY(chat_id,user_id_a,user_id_b))""")

        # Добавляю индексы для оптимизации (из ROADMAP.md)
        c.execute("CREATE INDEX IF NOT EXISTS idx_person_profile_chat_user ON person_profile(chat_id, user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_relationship_chat_user_a ON relationship_profile(chat_id, user_id_a)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_history_user_ts ON history(user_id, ts)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_chat_ts ON chat_history(chat_id, ts)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_reminders_due_ts ON reminders(due_ts)")

        c.execute("SELECT COUNT(*) FROM settings")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO settings (id, system_prompt, model) VALUES (1, ?, ?)",
                      (settings.default_system_prompt, settings.groq_model))
        # --- Миграции ---
        # Добавляем колонку username в chat_history если отсутствует
        c.execute("PRAGMA table_info(chat_history)")
        cols = [row[1] for row in c.fetchall()]
        if "username" not in cols:
            try:
                c.execute("ALTER TABLE chat_history ADD COLUMN username TEXT")
            except Exception:
                pass
        conn.commit()

# ========= Settings =========
def db_get_settings() -> Dict[str, Any]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT system_prompt, model FROM settings WHERE id=1")
        row = c.fetchone()
    return {"system_prompt": row[0], "model": row[1]}

def db_set_system_prompt(text: str):
    with closing(get_db_connection()) as conn:
        conn.execute("UPDATE settings SET system_prompt=? WHERE id=1", (text,))
        conn.commit()

def db_set_model(model: str):
    with closing(get_db_connection()) as conn:
        conn.execute("UPDATE settings SET model=? WHERE id=1", (model,))
        conn.commit()

# ========= History =========
def db_add_history(user_id: str, role: str, content: str):
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO history (user_id, role, content, ts) VALUES (?,?,?,?)", (user_id, role, content, time.time()))
        c.execute("""DELETE FROM history WHERE user_id=? AND rowid NOT IN
                     (SELECT rowid FROM history WHERE user_id=? ORDER BY ts DESC LIMIT ?)""", (user_id, user_id, settings.history_turns * 2))
        conn.commit()

def db_get_history(user_id: str) -> List[Dict[str, str]]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT role, content FROM history WHERE user_id=? ORDER BY ts ASC", (user_id,))
        rows = c.fetchall()
    return [{"role": r, "content": t} for (r, t) in rows]

def db_add_chat_message(chat_id: int, role: str, content: str, user_id: Optional[str] = None, username: Optional[str] = None):
    """Базовая внутренняя функция добавления сообщения в историю чата.
    Используйте log_chat_event для гибкой записи из хендлеров.
    """
    now = time.time()
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO chat_history (chat_id, role, content, ts, user_id, username) VALUES (?,?,?,?,?,?)",
                  (str(chat_id), role, content, now, str(user_id) if user_id else None, username))
        c.execute("""DELETE FROM chat_history WHERE chat_id=? AND rowid NOT IN
                     (SELECT rowid FROM chat_history WHERE chat_id=? ORDER BY ts DESC LIMIT 200)""",
                  (str(chat_id), str(chat_id)))
        c.execute("""INSERT INTO chat_activity (chat_id, last_ts) VALUES (?,?)
                     ON CONFLICT(chat_id) DO UPDATE SET last_ts=excluded.last_ts""",
                  (str(chat_id), now))
        conn.commit()

def log_chat_event(*, chat_id: int, user_id: Optional[int] = None, username: Optional[str] = None,
                   text: str = "", timestamp: Optional[float] = None, is_bot: bool = False, role: Optional[str] = None):
    """Back-compat слой для старых вызовов.
    Старые хендлеры вызывали db_add_chat_message с keyword аргументами (username, text, timestamp).
    Мы приводим их к унифицированному формату и вызываем db_add_chat_message.
    Параметр username пока не сохраняется (нет колонки) – при необходимости добавить миграцию.
    """
    if role is None:
        # Простая эвристика: бот -> assistant, остальное -> user
        role = "assistant" if is_bot else "user"
    content = text or ""
    db_add_chat_message(chat_id=chat_id, role=role, content=content, user_id=str(user_id) if user_id else None, username=username)

def db_get_chat_tail(chat_id: int, limit: int) -> List[Dict[str, str]]:
    """Возвращает последние сообщения чата.
    Теперь дополнительно возвращаем user_id (если есть) для более богатого контекста.
    В текущей схеме нет username, поэтому handlers должны сами восстанавливать имена при необходимости.
    """
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT role, content, user_id FROM chat_history WHERE chat_id=? ORDER BY ts DESC LIMIT ?",
                  (str(chat_id), limit))
        rows = c.fetchall()[::-1]
    return [{"role": r, "content": t, "user_id": u} for (r, t, u) in rows]

# ========= Simple memories =========
def mem_add_user(user_id: str, value: str):
    v = value.strip()
    if not v: return
    with closing(get_db_connection()) as conn:
        conn.execute("INSERT INTO user_memory (user_id, value, ts) VALUES (?,?,?)", (user_id, v, time.time()))
        conn.commit()

def mem_list_user(user_id: str, limit: int = 50) -> List[Tuple[int, str]]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT rowid, value FROM user_memory WHERE user_id=? ORDER BY ts DESC LIMIT ?", (user_id, limit))
        return c.fetchall()

def mem_del_user(user_id: str, rowid: int):
    with closing(get_db_connection()) as conn:
        conn.execute("DELETE FROM user_memory WHERE user_id=? AND rowid=?", (user_id, rowid))
        conn.commit()

def mem_add_chat(chat_id: int, value: str):
    v = value.strip()
    if not v: return
    with closing(get_db_connection()) as conn:
        conn.execute("INSERT INTO chat_memory (chat_id, value, ts) VALUES (?,?,?)", (str(chat_id), v, time.time()))
        conn.commit()

def mem_list_chat(chat_id: int, limit: int = 50) -> List[Tuple[int, str]]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT rowid, value FROM chat_memory WHERE chat_id=? ORDER BY ts DESC LIMIT ?", (str(chat_id), limit))
        return c.fetchall()

def mem_del_chat(chat_id: int, rowid: int):
    with closing(get_db_connection()) as conn:
        conn.execute("DELETE FROM chat_memory WHERE chat_id=? AND rowid=?", (str(chat_id), rowid))
        conn.commit()

# ========= Person profiles =========
def db_load_person(chat_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT profile_json FROM person_profile WHERE chat_id=? AND user_id=?", (str(chat_id), str(user_id)))
        row = c.fetchone()
    return json.loads(row[0]) if row else None

def db_save_person(chat_id: int, user_id: int, prof: Dict[str, Any]):
    with closing(get_db_connection()) as conn:
        conn.execute("""INSERT INTO person_profile(chat_id,user_id,profile_json,updated_ts)
                        VALUES(?,?,?,?)
                        ON CONFLICT(chat_id,user_id) DO UPDATE SET
                          profile_json=excluded.profile_json,
                          updated_ts=excluded.updated_ts""",
                     (str(chat_id), str(user_id), json.dumps(prof, ensure_ascii=False), time.time()))
        conn.commit()

# ========= Relationships (A->B) =========
def db_load_rel(chat_id: int, a: int, b: int) -> Optional[Dict[str, Any]]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("""SELECT score,tone,addr_json,last_ts FROM relationship_profile
                     WHERE chat_id=? AND user_id_a=? AND user_id_b=?""",
                  (str(chat_id), str(a), str(b)))
        row = c.fetchone()
    if not row: return None
    try:
        addr = json.loads(row[2] or "[]")
    except:
        addr = []
    return {"score": row[0], "tone": row[1], "addr": addr, "last_ts": row[3]}

def db_save_rel(chat_id: int, a: int, b: int, score: float, tone: float, addr: list):
    with closing(get_db_connection()) as conn:
        conn.execute("""INSERT INTO relationship_profile(chat_id,user_id_a,user_id_b,score,tone,addr_json,last_ts)
                        VALUES(?,?,?,?,?,?,?)
                        ON CONFLICT(chat_id,user_id_a,user_id_b) DO UPDATE SET
                          score=excluded.score, tone=excluded.tone,
                          addr_json=excluded.addr_json, last_ts=excluded.last_ts""",
                     (str(chat_id), str(a), str(b), score, tone, json.dumps(addr, ensure_ascii=False), time.time()))
        conn.commit()

# ========= Chat Style =========
def db_load_chat_style(chat_id: int) -> Optional[Dict[str, Any]]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT style_json, updated_ts FROM chat_style WHERE chat_id=?", (str(chat_id),))
        row = c.fetchone()
    if not row: return None
    try:
        js = json.loads(row[0])
        ts = row[1]
        if time.time() - ts > settings.style_cache_ttl_min * 60:
            return None
        return js
    except:
        return None

def db_save_chat_style(chat_id: int, style: Dict[str, Any]):
    with closing(get_db_connection()) as conn:
        conn.execute("""INSERT INTO chat_style(chat_id,style_json,updated_ts) VALUES(?,?,?)
                        ON CONFLICT(chat_id) DO UPDATE SET style_json=excluded.style_json,updated_ts=excluded.updated_ts""",
                     (str(chat_id), json.dumps(style, ensure_ascii=False), time.time()))
        conn.commit()

def db_get_chat_history_for_style(chat_id: int) -> List[str]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("""SELECT content FROM chat_history WHERE chat_id=? AND role='user'
                     ORDER BY ts DESC LIMIT ?""", (str(chat_id), settings.style_retrain_min_messages))
        return [t for (t,) in c.fetchall() if t and not t.startswith("[image]")]

# ========= Reminders / Schedulers =========
def db_add_reminder(chat_id: int, user_id: int, text: str, due_ts: float):
    with closing(get_db_connection()) as conn:
        conn.execute("INSERT INTO reminders(chat_id,user_id,text,due_ts,created_ts) VALUES(?,?,?,?,?)",
                     (str(chat_id), str(user_id), text, due_ts, time.time()))
        conn.commit()

def db_get_due_reminders(now_ts: float) -> List[Tuple]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT id,chat_id,user_id,text,due_ts FROM reminders WHERE due_ts<=? ORDER BY due_ts ASC LIMIT 20", (now_ts,))
        return c.fetchall()

def db_delete_reminder(reminder_id: int):
    with closing(get_db_connection()) as conn:
        conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
        conn.commit()

def db_get_all_chat_activities() -> List[Tuple]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT chat_id, last_ts FROM chat_activity")
        return c.fetchall()

def db_get_daily_mention_date(chat_id: int) -> Optional[str]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT last_date FROM daily_mention WHERE chat_id=?", (str(chat_id),))
        row = c.fetchone()
        return row[0] if row else None

def db_get_random_user_from_chat(chat_id: int) -> Optional[int]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("""SELECT DISTINCT user_id FROM chat_history WHERE chat_id=? AND user_id IS NOT NULL
                     ORDER BY ts DESC LIMIT 200""", (str(chat_id),))
        ids = [int(uid) for (uid,) in c.fetchall() if uid and uid.isdigit()]
    return __import__('random').choice(ids) if ids else None

def db_update_daily_mention_date(chat_id: int, date_str: str):
    with closing(get_db_connection()) as conn:
        conn.execute("""INSERT INTO daily_mention(chat_id,last_date) VALUES(?,?)
                        ON CONFLICT(chat_id) DO UPDATE SET last_date=excluded.last_date""",
                     (str(chat_id), date_str))
        conn.commit()

# ========= Media =========
def db_get_last_chat_photo(chat_id: int, max_age_sec: int = 24 * 3600) -> Optional[Tuple]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT file_id, caption, ts FROM recent_media WHERE chat_id=?", (str(chat_id),))
        row = c.fetchone()
    if not row: return None
    fid, caption, ts = row
    if time.time() - ts > max_age_sec: return None
    return fid, caption or ""

def db_update_recent_media(chat_id: int, file_id: str, caption: Optional[str]):
    with closing(get_db_connection()) as conn:
        conn.execute("""INSERT INTO recent_media(chat_id,file_id,caption,ts) VALUES(?,?,?,?)
                        ON CONFLICT(chat_id) DO UPDATE SET file_id=excluded.file_id,caption=excluded.caption,ts=excluded.ts""",
                     (str(chat_id), file_id, caption or "", time.time()))
        conn.commit()

# ========= Relationship Analysis =========
def db_get_user_relationships(chat_id: int, user_id: int, limit: int = 6) -> List[Tuple]:
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("""SELECT user_id_b, score, tone, addr_json FROM relationship_profile
                     WHERE chat_id=? AND user_id_a=? ORDER BY ABS(score) DESC LIMIT ?""",
                  (str(chat_id), str(user_id), limit))
        return c.fetchall()

def db_get_group_stats(chat_id: int) -> Dict[str, Any]:
    """Получает статистику группы."""
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        
        # Количество сообщений
        c.execute("SELECT COUNT(*) FROM chat_history WHERE chat_id=?", (str(chat_id),))
        message_count = c.fetchone()[0]
        
        # Количество уникальных пользователей
        c.execute("SELECT COUNT(DISTINCT user_id) FROM chat_history WHERE chat_id=? AND user_id IS NOT NULL", (str(chat_id),))
        user_count = c.fetchone()[0]
        
        # Последняя активность
        c.execute("SELECT MAX(ts) FROM chat_history WHERE chat_id=?", (str(chat_id),))
        last_activity = c.fetchone()[0]
        
        return {
            "message_count": message_count,
            "user_count": user_count,
            "last_activity": last_activity
        }

def db_get_last_activity(chat_id: int) -> Optional[float]:
    """Получает время последней активности в чате."""
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT last_ts FROM chat_activity WHERE chat_id=?", (str(chat_id),))
        result = c.fetchone()
        return result[0] if result else None

def db_clear_history(chat_id: int):
    """Очищает историю сообщений для чата."""
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM chat_history WHERE chat_id=?", (str(chat_id),))
        conn.commit()

def db_get_all_groups() -> List[Tuple]:
    """Получает список всех групп/чатов."""
    with closing(get_db_connection()) as conn:
        c = conn.cursor()
        c.execute("SELECT DISTINCT chat_id FROM chat_history")
        return c.fetchall()
