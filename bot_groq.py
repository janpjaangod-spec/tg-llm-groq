import asyncio, os, time, sqlite3, re
from contextlib import closing
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from groq import Groq

# ---------- ENV ----------
TG = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")

# Текстовая модель: можно сменить на qwen3-32b через переменную окружения
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# Vision-модель: актуальные варианты на Groq сейчас — Scout/Maverick
VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
VISION_FALLBACKS = [
    VISION_MODEL,
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]

ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()}
SYSTEM_DEFAULT = os.getenv("DEFAULT_SYSTEM_PROMPT",
    "Ты «Лёшка RAW v3» — свободный разговорный ассистент. Пиши по-русски, можно сленг/мат (без личных оскорблений и запрещёнки). "
    "НИКОГДА не используй упоминания и плейсхолдеры: никаких @никнеймов, «@имя», «[имя]», «<имя>». "
    "Если конфликт — коротко с самоиронией и смена темы/вопрос. Формат: 1–4 предложения или 3–5 пунктов. "
    "Команды: !topic, !wyr, !quiz3, !sum, !plan."
)

if not TG:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
if not GROQ_KEY:
    raise RuntimeError("GROQ_API_KEY is not set")

# ---------- BOT & LLM ----------
bot = Bot(TG, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
client = Groq(api_key=GROQ_KEY)

# ---------- DB ----------
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
    c.execute("SELECT COUNT(*) FROM settings")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO settings (id, system_prompt, model) VALUES (1, ?, ?)",
                  (SYSTEM_DEFAULT, MODEL))
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
        c.execute("INSERT INTO history (user_id, role, content, ts) VALUES (?,?,?,?)",
                  (user_id, role, content, time.time()))
        c.execute("""DELETE FROM history
                     WHERE user_id=?
                     AND rowid NOT IN (
                       SELECT rowid FROM history WHERE user_id=? ORDER BY ts DESC LIMIT 20
                     )""", (user_id, user_id))
        conn.commit()

def db_get_history(user_id: str):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("SELECT role, content FROM history WHERE user_id=? ORDER BY ts ASC", (user_id,))
        return [{"role": r, "content": t} for (r, t) in c.fetchall()]

def db_clear_history(user_id: str):
    with closing(sqlite3.connect(DB)) as conn:
        conn.execute("DELETE FROM history WHERE user_id=?", (user_id,))
        conn.commit()

# ---------- OUTPUT SANITIZER ----------
def clean_reply(t: str) -> str:
    t = re.sub(r'@имя|[\[\{<]\s*имя\s*[\]\}>]', '', t, flags=re.IGNORECASE)  # явные плейсхолдеры
    t = re.sub(r'@\w+', '', t)  # любые @упоминания
    t = re.sub(r'Похоже, ты.*?(до свидания|прощай)[.!?]?', '', t, flags=re.IGNORECASE | re.DOTALL)
    t = " ".join(t.split())
    return t.strip()

# ---------- LLM CALLS ----------
def llm_text(messages, model):
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

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
            return resp.choices[0].message.content.strip()
        except Exception as e:
            last_err = e
            continue
    # если все варианты не сработали — пробрасываем последнюю ошибку
    raise last_err

# ---------- COMMANDS ----------
@dp.message(CommandStart())
async def start(m: Message):
    s = db_get_settings()
    await m.answer(
        "Привет! Я LLM-бот на Groq. Пиши — отвечу.\n\n"
        f"<b>Модель:</b> <code>{s['model']}</code>\n"
        "Команды: /prompt, /setprompt, /model, /reset"
    )

@dp.message(Command("prompt"))
async def show_prompt(m: Message):
    s = db_get_settings()
    await m.answer(f"<b>System prompt:</b>\n<pre>{s['system_prompt']}</pre>")

@dp.message(Command("setprompt"))
async def set_prompt(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return await m.answer("Нет прав.")
    text = m.text.partition(" ")[2].strip()
    if not text:
        return await m.answer("Использование: /setprompt <текст>")
    db_set_system_prompt(text)
    await m.answer("✅ Обновил system prompt. /prompt — посмотреть")

@dp.message(Command("model"))
async def set_model(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return await m.answer("Нет прав.")
    name = m.text.partition(" ")[2].strip()
    if not name:
        s = db_get_settings()
        return await m.answer(f"Текущая модель: <code>{s['model']}</code>\nИспользование: /model <имя>")
    db_set_model(name)
    await m.answer(f"✅ Модель обновлена: <code>{name}</code>")

@dp.message(Command("reset"))
async def reset_history(m: Message):
    db_clear_history(str(m.from_user.id))
    await m.answer("🧹 История очищена.")

# ---------- PHOTO HANDLER ----------
@dp.message(F.photo)
async def on_photo(m: Message):
    file_id = m.photo[-1].file_id
    file = await bot.get_file(file_id)
    tg_file_url = f"https://api.telegram.org/file/bot{TG}/{file.file_path}"
    caption = (m.caption or "").strip()
    user_prompt = caption if caption else "Опиши, что на фото, кратко и по делу. Если есть текст — прочитай и перескажи."

    s = db_get_settings()
    await bot.send_chat_action(m.chat.id, "typing")
    try:
        answer = llm_vision(s["system_prompt"], tg_file_url, user_prompt)
    except Exception as e:
        answer = f"Ошибка vision-запроса: {e}"

    answer = clean_reply(answer)
    uid = str(m.from_user.id)
    db_add_history(uid, "user", f"[photo] {caption}")
    db_add_history(uid, "assistant", answer)
    await m.answer(answer)

# ---------- TEXT HANDLER ----------
@dp.message(F.text)
async def chat(m: Message):
    uid = str(m.from_user.id)
    s = db_get_settings()
    sys = {"role":"system","content":s["system_prompt"]}
    msgs = [sys] + db_get_history(uid) + [{"role":"user","content": m.text}]
    await bot.send_chat_action(m.chat.id, "typing")
    try:
        answer = llm_text(msgs, s["model"])
    except Exception as e:
        answer = f"Ошибка LLM: {e}"

    answer = clean_reply(answer)
    db_add_history(uid, "user", m.text)
    db_add_history(uid, "assistant", answer)
    await m.answer(answer)

# ---------- RUN ----------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
