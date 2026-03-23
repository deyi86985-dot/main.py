import logging, os, asyncio, re, time, requests
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
from flask import Flask
from threading import Thread
from imdb import Cinemagoer

# --- CONFIG ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"
OWNER_ID = 6783893816 
CHANNEL_ID = -1003065768519 

ia = Cinemagoer()

# --- WEB SERVER (Render Port Fix) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "CINESOCIETY ULTRA V4 IS ALIVE! 🚀"

def run_flask():
    # Render-এর পোর্ট এরর ফিক্স করার জন্য এটি অত্যন্ত জরুরি
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- DATABASE ---
class Database:
    def __init__(self, url):
        self.client = AsyncIOMotorClient(url)
        self.db = self.client["CINESOCIETY_ULTRA_V4"]
        self.users = self.db["users"]
        self.settings = self.db["settings"]
        self.files = self.db["files"]
        self.admins = self.db["admins"]

    async def get_setting(self, key, default):
        s = await self.settings.find_one({"key": key})
        return s["value"] if s else default

    async def update_setting(self, key, value):
        await self.settings.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

    async def get_user(self, user_id):
        user = await self.users.find_one({"user_id": user_id})
        if not user:
            user = {"user_id": user_id, "is_ban": False, "is_premium": False, "last_verify": 0}
            await self.users.insert_one(user)
        return user

    async def is_admin(self, user_id):
        if user_id == OWNER_ID: return True
        return await self.admins.find_one({"user_id": user_id}) is not None

db = Database(MONGO_URI)
app = Client("CINESOCIETY_PRO", API_ID, API_HASH, bot_token=BOT_TOKEN)

# --- HELPERS ---
def format_btn(filename):
    clean = re.sub(r'(@\w+|\[.*?\])', '', filename)
    res = re.search(r'(480p|720p|1080p|4k)', filename, re.I)
    res = res.group(0).upper() if res else "HD"
    se_match = re.search(r'(S\d+|E\d+)', filename, re.I)
    se = se_match.group(0).upper() if se_match else ""
    clean = re.sub(r'(480p|720p|1080p|4k|S\d+|E\d+)', '', clean, flags=re.I)
    clean = re.sub(r'[_.\-]', ' ', clean).strip().title()
    return f"🎬 {res} / {se} {clean[:25]}".strip()

async def auto_delete(c, chat_id, msg_id):
    await asyncio.sleep(120) # ২ মিনিট
    try: await c.delete_messages(chat_id, msg_id)
    except: pass

# --- SEARCH & PAGINATION LOGIC ---
async def send_results(m, query, page=0, is_cb=False):
    words = query.split()
    regex = f"^{''.join([f'(?=.*{re.escape(w)})' for w in words])}.*$"
    cursor = db.files.find({"clean_name": {"$regex": regex, "$options": "i"}})
    results = await cursor.to_list(length=100)

    if not results:
        return await m.reply("❌ No results found!") if not is_cb else await m.answer("No results!")

    start = page * 10
    end = start + 10
    page_items = results[start:end]
    total_pages = (len(results) + 9) // 10

    # Top Filter Buttons
    btns = [[
        InlineKeyboardButton("🌐 Language", callback_data=f"filt_lang_{query}_{page}"),
        InlineKeyboardButton("📂 Session", callback_data=f"filt_sess_{query}_{page}")
    ]]

    for f in page_items:
        btns.append([InlineKeyboardButton(format_btn(f['file_name']), url=f"https://t.me/{(await app.get_me()).username}?start=file_{f['_id']}")])

    # Pagination Row
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("<", callback_data=f"pg_{query}_{page-1}"))
    if end < len(results): nav.append(InlineKeyboardButton(">", callback_data=f"pg_{query}_{page+1}"))
    if nav: btns.append(nav)

    text = f"🔍 **Results for:** `{query.upper()}`\n📄 **Page:** `{page+1}/{total_pages}`\n\n**Edit by INDRA**"
    
    if is_cb:
        await m.message.edit(text, reply_markup=InlineKeyboardMarkup(btns))
    else:
        sent = await m.reply_text(text, reply_markup=InlineKeyboardMarkup(btns))
        if m.chat.type in ["group", "supergroup"]:
            asyncio.create_task(auto_delete(app, m.chat.id, sent.id))

# --- HANDLERS ---
@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    user = await db.get_user(m.from_user.id)
    if len(m.command) > 1 and m.command[1].startswith("file_"):
        doc_id = m.command[1].split("_")[1]
        doc = await db.files.find_one({"_id": ObjectId(doc_id)})
        if doc:
            f_msg = await c.send_cached_media(m.chat.id, doc['file_id'], caption=doc['caption'])
            w_msg = await m.reply("⚠️ Deleted in 2 mins!")
            asyncio.create_task(auto_delete(c, m.chat.id, [f_msg.id, w_msg.id]))
        return
    await m.reply_text(f"👋 Hello {m.from_user.mention}! Search movies here.")

@app.on_message(filters.text & ~filters.command(["start", "index", "stats", "commands"]))
async def handle_search(c, m):
    await send_results(m, m.text.lower().strip())

@app.on_callback_query()
async def cb_handler(c, cb: CallbackQuery):
    data = cb.data.split("_")
    if data[0] == "pg": await send_results(cb, data[1], int(data[2]), is_cb=True)
    elif data[0] == "filt":
        f_type, query, page = data[1], data[2], data[3]
        if f_type == "lang":
            btns = [[InlineKeyboardButton(l, callback_data=f"apply_lang_{l}_{query}")] for l in ["Hindi", "English", "Bengali", "Tamil"]]
            btns.append([InlineKeyboardButton("🔙 Back", callback_data=f"pg_{query}_{page}")])
            await cb.message.edit("🌍 Select Language:", reply_markup=InlineKeyboardMarkup(btns))
        elif f_type == "sess":
            btns = [[InlineKeyboardButton(f"S{i}", callback_data=f"apply_sess_{i}_{query}"), 
                     InlineKeyboardButton(f"S{i+1}", callback_data=f"apply_sess_{i+1}_{query}")] for i in range(1, 11, 2)]
            btns.append([InlineKeyboardButton("🔙 Back", callback_data=f"pg_{query}_{page}")])
            await cb.message.edit("📂 Select Session:", reply_markup=InlineKeyboardMarkup(btns))
    elif data[0] == "apply":
        f_t, val, q = data[1], data[2], data[3]
        p = f"S{int(val):02d}|Season {val}" if f_t == "sess" else val
        cursor = db.files.find({"clean_name": {"$regex": q}, "file_name": {"$regex": p, "$options": "i"}})
        res = await cursor.to_list(length=15)
        if not res: return await cb.message.edit("❌ **This is the language file here.**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"pg_{q}_0")]]))
        btns = [[InlineKeyboardButton(format_btn(f['file_name']), url=f"https://t.me/{(await c.get_me()).username}?start=file_{f['_id']}")] for f in res]
        btns.append([InlineKeyboardButton("🔙 Back to Results", callback_data=f"pg_{q}_0")])
        await cb.message.edit(f"✅ Filtered Results ({val}):", reply_markup=InlineKeyboardMarkup(btns))

# --- BOOTSTRAP ---
async def start_bot():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    print("🚀 Master Bot is LIVE! Edit by INDRA")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
