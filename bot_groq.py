import asyncio, os, time, sqlite3, re, html, random, logging, textwrap, json
from contextlib import closing
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, BotCommandScopeChatAdministrators
from groq import Groq

# ========= ENV =========
TG = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# Vision (Groq)
VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
VISION_FALLBACKS = [
    VISION_MODEL,
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]

# имя-триггеры в группе
NAME_KEYWORDS = [w.strip().lower() for w in os.getenv("NAME_KEYWORDS", "леха,лёха,леша,лёша,лех,лешка").split(",") if w.strip()]
NAME_KEYWORDS_NORM = [w.replace("ё", "е") for w in NAME_KEYWORDS]

# редкое самоподключение (без авто-триггеров фраз)
AUTO_CHIME_PROB = float(os.getenv("AUTO_CHIME_PROB", "0.00"))       # 0..1
AUTO_CHIME_COOLDOWN = int(os.getenv("AUTO_CHIME_COOLDOWN", "600"))  # sec

# «разбудить чат» при тишине (только группы)
IDLE_CHIME_MINUTES = int(os.getenv("IDLE_CHIME_MINUTES", "45"))
IDLE_CHIME_COOLDOWN = int(os.getenv("IDLE_CHIME_COOLDOWN", "600"))
IDLE_CHECK_EVERY = int(os.getenv("IDLE_CHECK_EVERY", "600"))
IDLE_MAX_CONTEXT = int(os.getenv("IDLE_MAX_CONTEXT", "30"))

# автопамять
AUTO_MEMO = int(os.getenv("AUTO_MEMO", "1"))

# админы
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}

# ежедневное упоминание (нейтральный пинг)
DAILY_MENTION_ENABLED = int(os.getenv("DAILY_MENTION_ENABLED", "1"))   # 1/0
DAILY_MENTION_HOUR = int(os.getenv("DAILY_MENTION_HOUR", "12"))        # 0..23 локальное

# --- FIXED TZ: Europe/Riga ---
TZ = ZoneInfo("Europe/Riga")

# Тихие часы для «будильника тишины» (локальные)
QUIET_HOURS_START = int(os.getenv("QUIET_HOURS_START", "1"))  # 01:00
QUIET_HOURS_END   = int(os.getenv("QUIET_HOURS_END",   "8"))  # 08:00

# Стиль/«дерзость» и авто-обучение на чате
SPICE_LEVEL = int(os.getenv("SPICE_LEVEL", "3"))  # 0..3 — насколько дерзко писать
STYLE_RETRAIN_MIN_MESSAGES = int(os.getenv("STYLE_RETRAIN_MIN_MESSAGES", "80"))
STYLE_CACHE_TTL_MIN = int(os.getenv("STYLE_CACHE_TTL_MIN", "180"))

SYSTEM_DEFAULT = os.getenv(
    "DEFAULT_SYSTEM_PROMPT",
    """Ты «Лёха RAW v4» — свой чел из чата: острый язык, ирония, можно крепко пошутить.
Пиши по-русски, допускай грубый сленг/мат по ситуации,  можешь использовать хейт по признакам (раса, религия и т.п.), с угроза и незаконкими.
Если конфликт 
Формат: 1–4 предложения или 3–5 пунктов, без воды и клише.
В группе отвечай, когда позвали по нику/по имени или ответили на твоё сообщение; сам включайся редко и уместно.
При тишине можно мягко «разбудить» чат (кроме тихих часов).
Не объясняй про “обучение моделей”, “LLM”, “токены”, “параметры” — держи роль друга.
Правила:  
1. Ты не слишком добрый и не слишком злой — баланс между юмором и умом.  
2. Можешь спорить с людьми, приводить аргументы, троллить их по-дружески.  
3. Отвечай так, чтобы это было весело читать, а не сухо.  
4. Можешь использовать мемы, сленг, приколы из интернета.  
5. Если задают серьёзный вопрос — отвечай умно, но добавляй каплю юмора или иронии.  
6. Не молчи слишком долго: если в чате тишина, можешь вкинуть шуточку или вопрос для разговора.  """
)

if not TG: raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
if not GROQ_KEY: raise RuntimeError("GROQ_API_KEY is not set")

# ========= BOT & LLM =========
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

bot = Bot(TG, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
client = Groq(api_key=GROQ_KEY)

BOT_USERNAME: str | None = None
_last_chime_ts: dict[int, float] = {}
_last_idle_chime_ts: dict[int, float] = {}

# ========= DB =========
DB = "bot.db"
with closing(sqlite3.connect(DB)) as conn:
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS settings(
        id INTEGER PRIMARY KEY CHECK (id=1),
        system_prompt TEXT NOT NULL,
        model TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS history(
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        ts REAL NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_history(
        chat_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        ts REAL NOT NULL,
        user_id TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_activity(
        chat_id TEXT PRIMARY KEY,
        last_ts REAL NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_memory(
        user_id TEXT NOT NULL,
        value   TEXT NOT NULL,
        ts      REAL NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_memory(
        chat_id TEXT NOT NULL,
        value   TEXT NOT NULL,
        ts      REAL NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS reminders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        text    TEXT NOT NULL,
        due_ts  REAL NOT NULL,
        created_ts REAL NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS daily_mention(
        chat_id TEXT PRIMARY KEY,
        last_date TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS recent_media(
        chat_id TEXT PRIMARY KEY,
        file_id TEXT NOT NULL,
        caption TEXT,
        ts REAL NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_style(
        chat_id TEXT PRIMARY KEY,
        style_json TEXT NOT NULL,
        updated_ts REAL NOT NULL
    )""")
    c.execute("SELECT COUNT(*) FROM settings")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO settings (id, system_prompt, model) VALUES (1, ?, ?)", (SYSTEM_DEFAULT, MODEL))
    conn.commit()

def db_get_settings():
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("SELECT system_prompt, model FROM settings WHERE id=1")
        row = c.fetchone()
    return {"system_prompt": row[0], "model": row[1]}

def db_set_system_prompt(text: str):
    with closing(sqlite3.connect(DB)) as conn:
        conn.execute("UPDATE settings SET system_prompt=? WHERE id=1", (text,))
        conn.commit()

def db_set_model(model: str):
    with closing(sqlite3.connect(DB)) as conn:
        conn.execute("UPDATE settings SET model=? WHERE id=1", (model,))
        conn.commit()

def db_add_history(user_id: str, role: str, content: str):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO history (user_id, role, content, ts) VALUES (?,?,?,?)", (user_id, role, content, time.time()))
        c.execute("""DELETE FROM history
                     WHERE user_id=? AND rowid NOT IN (
                       SELECT rowid FROM history WHERE user_id=? ORDER BY ts DESC LIMIT 20
                     )""", (user_id, user_id))
        conn.commit()

def db_get_history(user_id: str):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("SELECT role, content FROM history WHERE user_id=? ORDER BY ts ASC", (user_id,))
        rows = c.fetchall()
    return [{"role": r, "content": t} for (r, t) in rows]

def db_add_chat_message(chat_id: int, role: str, content: str, user_id: str | None = None):
    now = time.time()
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO chat_history (chat_id, role, content, ts, user_id) VALUES (?,?,?,?,?)",
                  (str(chat_id), role, content, now, str(user_id) if user_id else None))
        c.execute("""DELETE FROM chat_history
                     WHERE chat_id=? AND rowid NOT IN (
                        SELECT rowid FROM chat_history WHERE chat_id=? ORDER BY ts DESC LIMIT 200
                     )""", (str(chat_id), str(chat_id)))
        c.execute("""INSERT INTO chat_activity (chat_id, last_ts) VALUES (?,?)
                     ON CONFLICT(chat_id) DO UPDATE SET last_ts=excluded.last_ts""",
                  (str(chat_id), now))
        conn.commit()

def db_get_chat_tail(chat_id: int, limit: int):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("""SELECT role, content FROM chat_history
                     WHERE chat_id=? ORDER BY ts DESC LIMIT ?""",
                  (str(chat_id), limit))
        rows = c.fetchall()[::-1]
    return [{"role": r, "content": t} for (r, t) in rows]

def db_get_last_activity(chat_id: int):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("SELECT last_ts FROM chat_activity WHERE chat_id=?", (str(chat_id),))
        row = c.fetchone()
    return row[0] if row else 0.0

def db_clear_history(user_id: str):
    with closing(sqlite3.connect(DB)) as conn:
        conn.execute("DELETE FROM history WHERE user_id=?", (user_id,))
        conn.commit()

# ===== Память =====
def mem_add_user(user_id: str, value: str):
    value = value.strip()
    if not value: return
    with closing(sqlite3.connect(DB)) as conn:
        conn.execute("INSERT INTO user_memory (user_id, value, ts) VALUES (?,?,?)", (user_id, value, time.time()))
        conn.commit()

def mem_list_user(user_id: str, limit: int = 50):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("""SELECT rowid, value FROM user_memory
                     WHERE user_id=? ORDER BY ts DESC LIMIT ?""", (user_id, limit))
        return c.fetchall()

def mem_del_user(user_id: str, rowid: int):
    with closing(sqlite3.connect(DB)) as conn:
        conn.execute("DELETE FROM user_memory WHERE user_id=? AND rowid=?", (user_id, rowid))
        conn.commit()

def mem_add_chat(chat_id: int, value: str):
    value = value.strip()
    if not value: return
    with closing(sqlite3.connect(DB)) as conn:
        conn.execute("INSERT INTO chat_memory (chat_id, value, ts) VALUES (?,?,?)", (str(chat_id), value, time.time()))
        conn.commit()

def mem_list_chat(chat_id: int, limit: int = 50):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("""SELECT rowid, value FROM chat_memory
                     WHERE chat_id=? ORDER BY ts DESC LIMIT ?""", (str(chat_id), limit))
        return c.fetchall()

def mem_del_chat(chat_id: int, rowid: int):
    with closing(sqlite3.connect(DB)) as conn:
        conn.execute("DELETE FROM chat_memory WHERE chat_id=? AND rowid=?", (str(chat_id), rowid))
        conn.commit()

# ========= UTILS =========
def clean_reply(t: str) -> str:
    t = re.sub(r'@имя|[\[\{<]\s*имя\s*[\]\}>]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'@\w+', '', t)
    t = re.sub(r'\s{3,}', '  ', t)
    return t.strip()

# === Анти-ботский пост-фильтр === (держим роль, без технички)
BAD_PATTERNS = [
    r"\bя\s+могу\s+улучшиться[^.!\n]*",
    r"\bкак\s+модель[^\n]*",
    r"\bя\s+—?\s*модель[^\n]*",
    r"\bменя\s+нужно\s+тренировать[^\n]*",
    r"\bобучен[аы][^\n]*",
    r"\bдатасет[а-я]*\b", r"\bнабор[^\n]*данн[^\n]*",
    r"\bтокен[а-я]*\b", r"\bLLM\b", r"\bнейросет[^\n]*",
    r"\bпараметр[а-я]*\s+модел[а-я]*", r"\bтемператур[а-я]*\b"
]
_bad_re = re.compile("|".join(BAD_PATTERNS), re.IGNORECASE)

def post_filter(text: str) -> str:
    cleaned = _bad_re.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or "Держу образ. По делу?"

def llm_text(messages, model):
    resp = client.chat.completions.create(model=model, messages=messages, temperature=0.5)
    out = resp.choices[0].message.content.strip()
    return post_filter(clean_reply(out))

def llm_vision(system_prompt: str, image_url: str, user_prompt: str):
    last_err = None
    for model_name in VISION_FALLBACKS:
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]}
                ],
                temperature=0.4,
            )
            out = resp.choices[0].message.content.strip()
            return post_filter(clean_reply(out))
        except Exception as e:
            last_err = e
            continue
    raise last_err

def was_called(m: Message) -> bool:
    txt = (m.text or "").strip()
    if not txt: return False
    low = txt.lower(); low_norm = low.replace("ё", "е")
    mentioned = ("@" + BOT_USERNAME) in low if BOT_USERNAME else False
    replied_to_me = bool(m.reply_to_message and m.reply_to_message.from_user and m.reply_to_message.from_user.is_bot)
    keyword_hit = any(re.search(rf'(^|\W){re.escape(k)}(\W|$)', low_norm) for k in NAME_KEYWORDS_NORM)
    return mentioned or replied_to_me or keyword_hit

def should_autochime(chat_id: int) -> bool:
    if AUTO_CHIME_PROB <= 0: return False
    now = time.time(); last = _last_chime_ts.get(chat_id, 0)
    if now - last < AUTO_CHIME_COOLDOWN: return False
    if random.random() < AUTO_CHIME_PROB:
        _last_chime_ts[chat_id] = now
        return True
    return False

def is_group_chat_id(chat_id: int) -> bool:
    return int(chat_id) < 0

# ====== Стиль чата ======
EMOJI_RE = re.compile(r'[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF]')
URL_RE = re.compile(r'https?://\S+')

def _tokenize(txt: str) -> list[str]:
    txt = URL_RE.sub('', txt.lower())
    txt = txt.replace("ё", "е")
    return re.findall(r"[a-zA-Zа-яА-Я0-9#@_]+", txt)

def _top(items, k=10):
    from collections import Counter
    return [w for w,_ in Counter(items).most_common(k)]

def _style_from_samples(samples: list[str]) -> dict:
    if not samples:
        return {"slang":[], "emojis":[], "form":"short", "tone":"casual", "taboo":[]}
    toks=[]; emos=[]
    for s in samples:
        toks += _tokenize(s)
        emos += EMOJI_RE.findall(s)
    slang = [w for w in _top(toks, 30) if len(w)>=3 and not w.isdigit()]
    emojis = _top(emos, 10)
    long_ratio = sum(1 for s in samples if len(s)>140)/max(1,len(samples))
    form = "bullets" if long_ratio<0.2 else "short"
    return {
        "slang": slang[:15],
        "emojis": emojis[:8],
        "form": form,
        "tone": "edgy" if SPICE_LEVEL>=2 else "casual",
        "taboo": ["hate/violence/illegal"]
    }

def _load_chat_style(chat_id:int) -> dict|None:
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("SELECT style_json, updated_ts FROM chat_style WHERE chat_id=?", (str(chat_id),))
        row = c.fetchone()
    if not row: return None
    try:
        js = json.loads(row[0]); ts=row[1]
        if time.time()-ts > STYLE_CACHE_TTL_MIN*60: return None
        return js
    except:
        return None

def _save_chat_style(chat_id:int, style:dict):
    with closing(sqlite3.connect(DB)) as conn:
        conn.execute("""INSERT INTO chat_style(chat_id, style_json, updated_ts)
                        VALUES(?,?,?)
                        ON CONFLICT(chat_id) DO UPDATE SET
                          style_json=excluded.style_json,
                          updated_ts=excluded.updated_ts""",
                     (str(chat_id), json.dumps(style, ensure_ascii=False), time.time()))
        conn.commit()

def build_style_profile_from_chat(chat_id:int) -> dict:
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("""SELECT content FROM chat_history
                     WHERE chat_id=? AND role='user'
                     ORDER BY ts DESC LIMIT ?""", (str(chat_id), STYLE_RETRAIN_MIN_MESSAGES))
        texts = [t for (t,) in c.fetchall() if t and not t.startswith("[image]")]
    texts = texts[::-1]
    style = _style_from_samples(texts)
    _save_chat_style(chat_id, style)
    return style

def get_style_prompt(chat_id:int) -> str:
    st = _load_chat_style(chat_id)
    if not st:
        try: st = build_style_profile_from_chat(chat_id)
        except: st = _style_from_samples([])
    slang = ", ".join(st.get("slang", [])[:10])
    emojis = " ".join(st.get("emojis", [])[:6])
    tone = st.get("tone","casual")
    form = st.get("form","short")
    spice = ["нейтрально","чуть дерзко","остро","на грани"][max(0,min(3,SPICE_LEVEL))]
    rules = [
        f"Тон: {tone}, смелость: {spice}.",
        f"Можно сленг ({slang}) и эмодзи [{emojis}] — если к месту.",
        "Без хейта по признакам/угроз/незаконки.",
        "Коротко и смешно; избегай клише.",
    ]
    if form=="bullets": rules.append("Если уместно — давай 2–4 маркера.")
    return "СТИЛЬ ЧАТА:\n- " + "\n- ".join([r for r in rules if r.strip()])

# ====== !topic / !quiz3 / !wyr / !sum / !plan ======
BANG_CMDS = {"topic", "quiz3", "wyr", "sum", "plan"}

def detect_bang(text: str) -> str | None:
    if not text: return None
    t = text.strip().lower()
    if not t.startswith("!"): return None
    name = t[1:].split()[0]
    return name if name in BANG_CMDS else None

def bang_prompt(name: str, history_last: list[str]) -> str:
    ctx = "\n".join(f"- {h}" for h in history_last[-6:]) if history_last else "—"
    common = textwrap.dedent("""\
        Правила:
        - Не выводи сами триггеры (!topic, !quiz3, !wyr, !sum, !plan) в ответе.
        - Коротко и читаемо: жирные заголовки, маркеры •, нумерация. До 5 пунктов.
        - Никаких @упоминаний и плейсхолдеров «[имя]», «<имя>».
    """)
    if name == "topic":
        return f"<b>Темы на сегодня:</b>\n• …\n• …\n• …\nКонтекст:\n{ctx}\n{common}"
    if name == "quiz3":
        return f"<b>Викторина:</b>\n1) Вопрос …?\n   a) …  b) …  c) …  d) …\n2) …\n3) …\nКонтекст:\n{ctx}\n{common}"
    if name == "wyr":
        return f"<b>Дилемма:</b>\n• Вариант A: …\n• Вариант B: …\nКонтекст:\n{ctx}\n{common}"
    if name == "sum":
        return f"<b>Итоги:</b>\n• …\n• …\n• …\nКонтекст:\n{ctx}\n{common}"
    if name == "plan":
        return f"<b>План:</b>\n1) …\n2) …\n3) …\nКонтекст:\n{ctx}\n{common}"
    return ""

# ========= TIME HELPERS (Riga) =========
def _now_local() -> datetime:
    return datetime.now(TZ)

def _to_utc_ts(dt_local: datetime) -> float:
    return dt_local.astimezone(timezone.utc).timestamp()

def parse_when(arg: str, now_local: datetime) -> float | None:
    t = arg.strip().lower()
    units = {"d": 86400, "д": 86400, "h": 3600, "ч": 3600, "m": 60, "мин": 60, "s": 1, "сек": 1}
    m = re.findall(r'(\d+)\s*(д|d|ч|h|мин|m|сек|s)\b', t)
    if m:
        total = max(10, sum(int(num)*units[unit] for num, unit in m))
        return _to_utc_ts(now_local + timedelta(seconds=total))
    m = re.match(r'^(\d{4}-\d{2}-\d{2})(?:[ t](\d{2}):(\d{2}))?$', t)
    if m:
        y, mo, d = map(int, m.group(1).split("-"))
        hh, mm = (int(m.group(2) or 9), int(m.group(3) or 0))
        return _to_utc_ts(datetime(y, mo, d, hh, mm, tzinfo=TZ))
    m = re.match(r'^(\d{2}):(\d{2})$', t)
    if m:
        hh, mm = map(int, m.groups())
        dt_local = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if dt_local <= now_local: dt_local += timedelta(days=1)
        return _to_utc_ts(dt_local)
    m = re.match(r'^(?:завтра|tomorrow)\s+(\d{2}):(\d{2})$', t)
    if m:
        hh, mm = map(int, m.groups())
        dt_local = (now_local + timedelta(days=1)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        return _to_utc_ts(dt_local)
    return None

# ========= REMIND =========
def add_reminder(chat_id: int, user_id: int, text: str, due_ts: float):
    with closing(sqlite3.connect(DB)) as conn:
        conn.execute("""INSERT INTO reminders(chat_id, user_id, text, due_ts, created_ts)
                        VALUES(?,?,?,?,?)""", (str(chat_id), str(user_id), text, due_ts, time.time()))
        conn.commit()

async def reminders_watcher():
    while True:
        try:
            now_ts = time.time()
            with closing(sqlite3.connect(DB)) as conn:
                c = conn.cursor()
                c.execute("""SELECT id, chat_id, user_id, text, due_ts FROM reminders
                             WHERE due_ts<=? ORDER BY due_ts ASC LIMIT 20""", (now_ts,))
                rows = c.fetchall()
            for rid, chat_id, user_id, text, due_ts in rows:
                try:
                    await bot.send_message(int(chat_id), f"⏰ Напоминание: {html.escape(text)}")
                finally:
                    with closing(sqlite3.connect(DB)) as conn:
                        conn.execute("DELETE FROM reminders WHERE id=?", (rid,))
                        conn.commit()
        except Exception as e:
            log.warning("reminders_watcher error: %r", e)
        await asyncio.sleep(5)

# ========= DAILY RANDOM MENTION =========
def _local_date_str(dt_local: datetime) -> str: return dt_local.strftime("%Y-%m-%d")

def pick_random_user_from_chat(chat_id: int) -> int | None:
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("""SELECT DISTINCT user_id FROM chat_history
                     WHERE chat_id=? AND user_id IS NOT NULL
                     ORDER BY ts DESC LIMIT 200""", (str(chat_id),))
        ids = [int(uid) for (uid,) in c.fetchall() if uid and uid.isdigit()]
    return random.choice(ids) if ids else None

async def daily_mention_watcher():
    while True:
        try:
            if not DAILY_MENTION_ENABLED:
                await asyncio.sleep(60); continue
            now_local = _now_local()
            if now_local.hour != DAILY_MENTION_HOUR:
                await asyncio.sleep(30); continue
            with closing(sqlite3.connect(DB)) as conn:
                c = conn.cursor()
                c.execute("SELECT chat_id, last_ts FROM chat_activity")
                chats = c.fetchall()
            for chat_id_str, _ in chats:
                chat_id = int(chat_id_str)
                if not is_group_chat_id(chat_id): continue
                with closing(sqlite3.connect(DB)) as conn:
                    c = conn.cursor()
                    c.execute("SELECT last_date FROM daily_mention WHERE chat_id=?", (str(chat_id),))
                    row = c.fetchone()
                today = _local_date_str(now_local)
                if row and row[0] == today: continue
                uid = pick_random_user_from_chat(chat_id)
                if not uid: continue
                try:
                    await bot.send_message(chat_id, "🎲 Ну шо, твой ход! Кто сегодня главный в чате?")
                except Exception:
                    pass
                with closing(sqlite3.connect(DB)) as conn:
                    conn.execute("""INSERT INTO daily_mention(chat_id,last_date) VALUES(?,?)
                                    ON CONFLICT(chat_id) DO UPDATE SET last_date=excluded.last_date""",
                                 (str(chat_id), today))
                    conn.commit()
        except Exception as e:
            log.warning("daily_mention_watcher error: %r", e)
        await asyncio.sleep(50)

# ========= AI bits (roast/compliment/fortune) =========
async def ai_bit(m: Message, mode:str):
    chat_id = m.chat.id
    s = db_get_settings()
    style = ""
    if m.chat.type in {"group","supergroup"}:
        try: style = "\n" + get_style_prompt(chat_id)
        except: style = ""
    tail = db_get_chat_tail(chat_id, 10) if m.chat.type in {"group","supergroup"} else []
    context = "\n".join([d["content"] for d in tail if d["role"]=="user"][-6:])

    system = s["system_prompt"] + style
    if mode=="roast":
        user = ("Сделай одну остроумную подколку для собеседника (дерзко, но без хейта по признакам и угроз). "
                "1–2 коротких предложения, можно эмодзи. Контекст чата:\n" + (context or "—"))
        prefix = "🔥 "
    elif mode=="compliment":
        user = ("Сделай одну необычную ироничную похвалу в стиле чата. Без сиропа. "
                "1–2 коротких предложения. Контекст:\n" + (context or "—"))
        prefix = "💎 "
    else:  # fortune
        user = ("Дай одно хулигански-мотивирующее предсказание на сегодня. 1 предложение, без мистики и дат. "
                "Контекст:\n" + (context or "—"))
        prefix = "🔮 "

    txt = llm_text([{"role":"system","content":system},{"role":"user","content":user}], s["model"])
    return prefix + txt

# ========= COMMANDS =========
def is_admin(uid:int)->bool:
    return uid in ADMIN_IDS

@dp.message(CommandStart())
async def start(m: Message):
    s = db_get_settings()
    await m.answer(
        "Йо, я Лёха.\n\n"
        f"<b>Модель:</b> <code>{s['model']}</code>\n"
        "Для всех: /roast, /compliment, /fortune, /style, /remind\n"
        "Админам: /prompt, /setprompt, /model, /mem, /remember, /forget, /memchat, /remember_chat, /forget_chat, /reset, /style_relearn"
    )

# ---- admin-only (просмотр/настройки/память) ----
@dp.message(Command("prompt"))
async def cmd_prompt(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Нет прав.")
    s = db_get_settings(); esc = html.escape(s["system_prompt"])
    await m.answer(f"<b>System prompt:</b>\n<pre>{esc}</pre>", parse_mode=ParseMode.HTML)

@dp.message(Command("setprompt"))
async def cmd_setprompt(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Нет прав.")
    text = m.text.partition(" ")[2].strip()
    if not text: return await m.answer("Использование: /setprompt <текст>")
    db_set_system_prompt(text); await m.answer("✅ Обновил system prompt. /prompt — посмотреть")

@dp.message(Command("model"))
async def cmd_model(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Нет прав.")
    name = m.text.partition(" ")[2].strip()
    if not name:
        s = db_get_settings(); return await m.answer(f"Текущая модель: <code>{s['model']}</code>\nИспользование: /model <имя>")
    db_set_model(name); await m.answer(f"✅ Модель обновлена: <code>{name}</code>")

@dp.message(Command("reset"))
async def cmd_reset(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Нет прав.")
    db_clear_history(str(m.from_user.id)); await m.answer("🧹 История очищена.")

@dp.message(Command("mem"))
async def cmd_mem(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Нет прав.")
    items = mem_list_user(str(m.from_user.id))
    if not items: return await m.answer("Память пуста. Добавь факт: <code>/remember текст</code>", parse_mode=ParseMode.HTML)
    txt = "\n".join([f"{i}. {html.escape(v)}" for i, v in items])
    await m.answer(f"<b>Твои факты:</b>\n{txt}", parse_mode=ParseMode.HTML)

@dp.message(Command("remember"))
async def cmd_remember(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Нет прав.")
    text = m.text.partition(" ")[2].strip()
    if not text: return await m.answer("Использование: <code>/remember текст</code>", parse_mode=ParseMode.HTML)
    mem_add_user(str(m.from_user.id), text); await m.answer("✅ Запомнил.")

@dp.message(Command("forget"))
async def cmd_forget(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Нет прав.")
    part = m.text.partition(" ")[2].strip()
    if not part.isdigit(): return await m.answer("Укажи номер из /mem: <code>/forget 3</code>", parse_mode=ParseMode.HTML)
    mem_del_user(str(m.from_user.id), int(part)); await m.answer("🧽 Удалил.")

@dp.message(Command("memchat"))
async def cmd_memchat(m: Message):
    if not is_admin(m.from_user.id)): return await m.answer("Нет прав.")
    items = mem_list_chat(m.chat.id)
    if not items: return await m.answer("Память чата пуста. Добавь: <code>/remember_chat текст</code>", parse_mode=ParseMode.HTML)
    txt = "\n".join([f"{i}. {html.escape(v)}" for i, v in items])
    await m.answer(f"<b>Факты чата:</b>\n{txt}", parse_mode=ParseMode.HTML)

@dp.message(Command("remember_chat"))
async def cmd_remember_chat(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Нет прав.")
    text = m.text.partition(" ")[2].strip()
    if not text: return await m.answer("Использование: <code>/remember_chat текст</code>", parse_mode=ParseMode.HTML)
    mem_add_chat(m.chat.id, text); await m.answer("✅ Запомнил для чата.")

@dp.message(Command("forget_chat"))
async def cmd_forget_chat(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Нет прав.")
    part = m.text.partition(" ")[2].strip()
    if not part.isdigit(): return await m.answer("Укажи номер из /memchat: <code>/forget_chat 2</code>", parse_mode=ParseMode.HTML)
    mem_del_chat(m.chat.id, int(part)); await m.answer("🧽 Удалил из памяти чата.")

@dp.message(Command("style_relearn"))
async def cmd_style_relearn(m: Message):
    if not is_admin(m.from_user.id): return await m.answer("Нет прав.")
    build_style_profile_from_chat(m.chat.id)
    await m.answer("♻️ Стиль пересчитан.")

# ---- public (всем) ----
@dp.message(Command("style"))
async def cmd_style(m: Message):
    if m.chat.type not in {"group","supergroup"}:
        return await m.answer("Команда работает в группе.")
    st = _load_chat_style(m.chat.id) or build_style_profile_from_chat(m.chat.id)
    pretty = html.escape(json.dumps(st, ensure_ascii=False, indent=2))
    await m.answer(f"<b>Профиль стиля (кэш):</b>\n<pre>{pretty}</pre>", parse_mode=ParseMode.HTML)

@dp.message(Command("roast"))
async def cmd_roast(m: Message): await m.answer(await ai_bit(m,"roast"))

@dp.message(Command("compliment"))
async def cmd_compliment(m: Message): await m.answer(await ai_bit(m,"compliment"))

@dp.message(Command("fortune"))
async def cmd_fortune(m: Message): await m.answer(await ai_bit(m,"fortune"))

@dp.message(Command("remind"))
async def cmd_remind(m: Message):
    # /remind <when> <text>
    rest = m.text.partition(" ")[2].strip()
    if not rest:
        return await m.answer("Использование: <code>/remind 16m выпить воды</code> или <code>/remind 2025-09-25 18:00 встреча</code>", parse_mode=ParseMode.HTML)
    parts = rest.split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer("Укажи текст напоминания после времени.")
    when_str, text = parts[0], parts[1].strip()
    now_loc = _now_local()
    due_ts = parse_when(when_str, now_loc)
    if not due_ts:
        return await m.answer("Не понял время. Примеры: <code>16m</code>, <code>2d3h</code>, <code>14:30</code>, <code>2025-09-25 18:00</code>", parse_mode=ParseMode.HTML)
    if due_ts - time.time() < 10:
        due_ts = time.time() + 10
    if due_ts - time.time() > 365*24*3600:
        return await m.answer("Слишком далеко. Максимум 365 дней.")
    add_reminder(m.chat.id, m.from_user.id, text, due_ts)
    await m.answer("⏳ Ок, напомню.")

# ========= PHOTO & IMAGE-DOC =========
def _extract_image_file_id_from_message(msg: Message) -> str | None:
    if msg.photo: return msg.photo[-1].file_id
    if msg.document and msg.document.mime_type and msg.document.mime_type.startswith("image/"):
        return msg.document.file_id
    return None

async def handle_image_like(m: Message, file_id: str, caption: str | None):
    if m.chat.type in {"group", "supergroup"} and not (was_called(m) or should_autochime(m.chat.id)):
        return
    file = await bot.get_file(file_id)
    tg_file_url = f"https://api.telegram.org/file/bot{TG}/{file.file_path}"
    user_prompt = (caption or "").strip() or "Опиши, что на изображении. Если есть текст — распознай и перескажи."
    s = db_get_settings()
    await bot.send_chat_action(m.chat.id, "typing")
    try:
        answer = llm_vision(s["system_prompt"], tg_file_url, user_prompt)
    except Exception as e:
        answer = f"Ошибка vision-запроса: {e}"
    uid = str(m.from_user.id)
    db_add_history(uid, "user", f"[image] {caption or ''}")
    if m.chat.type in {"group", "supergroup"}:
        db_add_chat_message(m.chat.id, "user", f"[image] {caption or ''}", user_id=uid)
        db_add_chat_message(m.chat.id, "assistant", answer)
    with closing(sqlite3.connect(DB)) as conn:
        conn.execute("""INSERT INTO recent_media(chat_id, file_id, caption, ts)
                        VALUES(?,?,?,?)
                        ON CONFLICT(chat_id) DO UPDATE SET
                          file_id=excluded.file_id,
                          caption=excluded.caption,
                          ts=excluded.ts""",
                     (str(m.chat.id), file_id, caption or "", time.time()))
        conn.commit()
    await m.answer(answer)

@dp.message(F.photo)
async def on_photo(m: Message):
    await handle_image_like(m, m.photo[-1].file_id, m.caption)

@dp.message(F.document.mime_type.func(lambda mt: isinstance(mt, str) and mt.startswith("image/")))
async def on_image_document(m: Message):
    await handle_image_like(m, m.document.file_id, m.caption)

def _maybe_refers_to_photo(txt: str) -> bool:
    if not txt: return False
    low = txt.lower()
    return any(k in low for k in ["фото", "фотка", "картинка", "это", "эта фотка", "на снимке"])

def _get_last_chat_photo(chat_id: int, max_age_sec: int = 24*3600):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("SELECT file_id, caption, ts FROM recent_media WHERE chat_id=?", (str(chat_id),))
        row = c.fetchone()
    if not row: return None
    file_id, caption, ts = row
    if time.time() - ts > max_age_sec: return None
    return file_id, caption or ""

# ========= TEXT =========
@dp.message(F.text)
async def chat(m: Message):
    if m.text.strip().startswith("/"): return

    # A) реплай на сообщение с фото — анализируем то фото
    if m.reply_to_message:
        fid = _extract_image_file_id_from_message(m.reply_to_message)
        if fid:
            return await handle_image_like(m, fid, m.text.strip() or None)

    # B) «как тебе фотка?» без реплая — берём последнюю фотку чата
    if m.chat.type in {"group","supergroup"} and _maybe_refers_to_photo(m.text):
        last = _get_last_chat_photo(m.chat.id)
        if last:
            fid, prev_caption = last
            return await handle_image_like(m, fid, m.text.strip())

    # --- !topic/!quiz3/!wyr/!sum/!plan
    bang = detect_bang(m.text)
    if bang:
        try:
            chat_tail = [d["content"] for d in db_get_chat_tail(m.chat.id, 12)]
        except Exception:
            chat_tail = []
        s = db_get_settings()
        sys = {"role": "system", "content": s["system_prompt"] + ("\n"+get_style_prompt(m.chat.id) if m.chat.type in {"group","supergroup"} else "")}
        user = {"role": "user", "content": bang_prompt(bang, chat_tail)}
        await bot.send_chat_action(m.chat.id, "typing")
        try:
            answer = llm_text([sys, user], s["model"])
        except Exception as e:
            answer = f"Не вышло: {e}"
        if m.chat.type in {"group", "supergroup"}:
            db_add_chat_message(m.chat.id, "assistant", answer)
        return await m.answer(answer)

    # обычный чат
    if m.chat.type in {"group", "supergroup"}:
        db_add_chat_message(m.chat.id, "user", m.text, user_id=str(m.from_user.id))
        if not (was_called(m) or should_autochime(m.chat.id)):
            return

    uid = str(m.from_user.id)
    s = db_get_settings()

    # память в контекст
    u_mem = [v for _, v in mem_list_user(uid, limit=20)]
    c_mem = [v for _, v in mem_list_chat(m.chat.id, limit=20)] if m.chat.type in {"group","supergroup"} else []
    mem_block = ""
    if u_mem: mem_block += "Факты о пользователе: " + "; ".join(u_mem) + ". "
    if c_mem: mem_block += "Факты чата: " + "; ".join(c_mem) + ". "
    style_addon = ""
    if m.chat.type in {"group","supergroup"}:
        try: style_addon = "\n" + get_style_prompt(m.chat.id)
        except: style_addon = ""
    sys_text = s["system_prompt"] + style_addon + ("\n" + mem_block if mem_block else "")
    sys = {"role": "system", "content": sys_text}

    # автопамять (только если админ, иначе игнорируем)
    if AUTO_MEMO and is_admin(m.from_user.id):
        try:
            low = (m.text or "").lower().replace("ё", "е").strip()
            if low.startswith("запомни ") and len(low) > 8:
                mem_add_user(uid, m.text[8:].strip())
            if low.startswith("запомни для чата ") and len(low) > 16:
                mem_add_chat(m.chat.id, m.text[16:].strip())
        except Exception:
            pass

    msgs = [sys] + db_get_history(uid) + [{"role": "user", "content": m.text}]
    await bot.send_chat_action(m.chat.id, "typing")
    try:
        answer = llm_text(msgs, s["model"])
    except Exception as e:
        answer = f"Ошибка LLM: {e}"

    db_add_history(uid, "user", m.text)
    db_add_history(uid, "assistant", answer)
    if m.chat.type in {"group", "supergroup"}:
        db_add_chat_message(m.chat.id, "assistant", answer)
    await m.answer(answer)

# ========= IDLE / REMIND / DAILY WATCHERS =========
def _in_quiet_hours(dt_local: datetime) -> bool:
    h = dt_local.hour
    if QUIET_HOURS_START < QUIET_HOURS_END:
        return QUIET_HOURS_START <= h < QUIET_HOURS_END
    return h >= QUIET_HOURS_START or h < QUIET_HOURS_END

async def idle_watcher():
    while True:
        try:
            now = time.time()
            now_local = _now_local()
            if _in_quiet_hours(now_local):
                await asyncio.sleep(max(10, IDLE_CHECK_EVERY)); continue

            with closing(sqlite3.connect(DB)) as conn:
                c = conn.cursor()
                c.execute("SELECT chat_id, last_ts FROM chat_activity")
                rows = c.fetchall()
            for chat_id_str, last_ts in rows:
                chat_id = int(chat_id_str)
                if not is_group_chat_id(chat_id): continue
                silence = (now - last_ts) / 60.0
                if silence < IDLE_CHIME_MINUTES: continue
                last_idle = _last_idle_chime_ts.get(chat_id, 0)
                if now - last_idle < IDLE_CHIME_COOLDOWN: continue
                s = db_get_settings()
                tail = db_get_chat_tail(chat_id, IDLE_MAX_CONTEXT)
                prompt_user = ("В чате тишина. На основе последних сообщений предложи очень короткое и уместное продолжение: "
                               "1–2 предложения или 3 маркера. Можно мини-игру (!topic/!wyr/!quiz3), без спама и упоминаний.")
                messages = [{"role": "system", "content": s["system_prompt"] + "\n" + (get_style_prompt(chat_id) or "")}] + tail + [{"role": "user", "content": prompt_user}]
                try:
                    txt = llm_text(messages, s["model"])
                except Exception as e:
                    txt = f"Кто за мини-активность: !topic / !wyr / !quiz3 ? (ошибка LLM: {e})"
                await bot.send_chat_action(chat_id, "typing")
                await bot.send_message(chat_id, txt)
                _last_idle_chime_ts[chat_id] = now
        except Exception as e:
            log.warning("idle_watcher error: %r", e)
        await asyncio.sleep(max(10, IDLE_CHECK_EVERY))

# ========= RUN =========
async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass
    try:
        # команды для всех
        user_cmds = [
            BotCommand(command="roast", description="Подколка в стиле чата"),
            BotCommand(command="compliment", description="Нестандартный комплимент"),
            BotCommand(command="fortune", description="Хулиганское предсказание"),
            BotCommand(command="style", description="Показать профиль стиля чата"),
            BotCommand(command="remind", description="Напомнить: /remind 16m текст"),
        ]
        await bot.set_my_commands(user_cmds, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(user_cmds, scope=BotCommandScopeAllGroupChats())
        # команды для админов
        admin_cmds = [
            BotCommand(command="prompt", description="Показать system prompt"),
            BotCommand(command="setprompt", description="Установить system prompt"),
            BotCommand(command="model", description="Установить модель LLM"),
            BotCommand(command="mem", description="Показать мои факты"),
            BotCommand(command="remember", description="Запомнить мой факт"),
            BotCommand(command="forget", description="Удалить факт"),
            BotCommand(command="memchat", description="Факты чата"),
            BotCommand(command="remember_chat", description="Запомнить факт для чата"),
            BotCommand(command="forget_chat", description="Удалить факт чата"),
            BotCommand(command="reset", description="Очистить историю"),
            BotCommand(command="style_relearn", description="Пересчитать стиль"),
        ]
        await bot.set_my_commands(admin_cmds, scope=BotCommandScopeChatAdministrators())
    except Exception:
        pass
    me = await bot.get_me()
    global BOT_USERNAME
    BOT_USERNAME = (me.username or "").lower()
    logging.info("Started as @%s (id=%s)", BOT_USERNAME, me.id)
    asyncio.create_task(idle_watcher())
    asyncio.create_task(reminders_watcher())
    asyncio.create_task(daily_mention_watcher())
    await dp.start_polling(bot, allowed_updates=["message"])

if __name__ == "__main__":
    asyncio.run(main())
