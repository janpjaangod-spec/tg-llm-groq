import asyncio, os, time, sqlite3
from contextlib import closing
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties   # <— добавили
from groq import Groq

TG = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()}
SYSTEM_DEFAULT = os.getenv("DEFAULT_SYSTEM_PROMPT", "You are a helpful assistant in Russian. Be concise.")

if not TG:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
if not GROQ_KEY:
    raise RuntimeError("GROQ_API_KEY is not set")

# В aiogram 3.7+ parse_mode задаётся через default=DefaultBotProperties(...)
bot = Bot(TG, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
client = Groq(api_key=GROQ_KEY)

client = Groq(api_key=GROQ_KEY)

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

def get_settings():
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("SELECT system_prompt, model FROM settings WHERE id=1")
        s = c.fetchone()
    return {"system_prompt": s[0], "model": s[1]}

def set_prompt(text:str):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET system_prompt=? WHERE id=1", (text,))
        conn.commit()

def set_model(name:str):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("UPDATE settings SET model=? WHERE id=1", (name,))
        conn.commit()

def add_hist(uid, role, content):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO history (user_id, role, content, ts) VALUES (?,?,?,?)",
                  (uid, role, content, time.time()))
        c.execute("""DELETE FROM history
                     WHERE user_id=?
                     AND rowid NOT IN (
                       SELECT rowid FROM history WHERE user_id=? ORDER BY ts DESC LIMIT 20
                     )""", (uid, uid))
        conn.commit()

def get_hist(uid):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("SELECT role, content FROM history WHERE user_id=? ORDER BY ts ASC", (uid,))
        return [{"role": r, "content": t} for (r,t) in c.fetchall()]

def clear_hist(uid):
    with closing(sqlite3.connect(DB)) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM history WHERE user_id=?", (uid,))
        conn.commit()

def llm_reply(messages, model):
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()

@dp.message(CommandStart())
async def start(m: Message):
    s = get_settings()
    await m.answer(
        "Привет! Я LLM-бот на Groq. Пиши — отвечу.\n\n"
        f"<b>Модель:</b> <code>{s['model']}</code>\n"
        "Команды: /prompt, /setprompt, /model, /reset"
    )

@dp.message(Command("prompt"))
async def show_prompt(m: Message):
    s = get_settings()
    await m.answer(f"<b>System prompt:</b>\n<pre>{s['system_prompt']}</pre>")

@dp.message(Command("setprompt"))
async def setprompt(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return await m.answer("Нет прав.")
    text = m.text.partition(" ")[2].strip()
    if not text:
        return await m.answer("Использование: /setprompt <текст>")
    set_prompt(text)
    await m.answer("✅ Обновил system prompt. /prompt — посмотреть")

@dp.message(Command("model"))
async def model_cmd(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return await m.answer("Нет прав.")
    name = m.text.partition(" ")[2].strip()
    if not name:
        s = get_settings(); return await m.answer(f"Текущая модель: <code>{s['model']}</code>")
    set_model(name)
    await m.answer(f"✅ Модель обновлена: <code>{name}</code>")

@dp.message(Command("reset"))
async def reset_cmd(m: Message):
    clear_hist(str(m.from_user.id))
    await m.answer("🧹 История очищена.")

@dp.message(F.text)
async def chat(m: Message):
    uid = str(m.from_user.id)
    s = get_settings()
    sys = {"role":"system","content":s["system_prompt"]}
    msgs = [sys] + get_hist(uid) + [{"role":"user","content": m.text}]
    await bot.send_chat_action(m.chat.id, "typing")
    try:
        answer = llm_reply(msgs, s["model"])
    except Exception as e:
        answer = f"Ошибка LLM: {e}"
    add_hist(uid,"user",m.text)
    add_hist(uid,"assistant",answer)
    await m.answer(answer)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
