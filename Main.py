import logging, os, asyncio, re, time, requests
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
from flask import Flask
from threading import Thread
from imdb import Cinemagoer

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
def home(): return "CINESOCIETY ULTRA V5 IS ONLINE! 🚀"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- DATABASE ---
class Database:
    def __init__(self, url):
        self.client = AsyncIOMotorClient(url)
        self.db = self.client["CINESOCIETY_ULTRA_V5"]
        self.files = self.db["files"]
        self.users = self.db["users"]
        self.settings = self.db["settings"]

    async def save_file(self, f_id, f_name, f_size, caption):
        clean = re.sub(r'(@\w+|\[.*?\])', '', f_name).lower().strip()
        if not await self.files.find_one({"file_name": f_name, "file_size": f_size}):
            await self.files.insert_one({'file_id': f_id, 'file_name': f_name, 'clean_name': clean, 'file_size': f_size, 'caption': caption})
            return True
        return False

db = Database(MONGO_URI)
app = Client("CINESOCIETY_PRO", API_ID, API_HASH, bot_token=BOT_TOKEN)

# --- HELPERS ---
def format_btn(filename):
    clean = re.sub(r'(@\w+|\[.*?\])', '', filename)
    res = re.search(r'(480p|720p|1080p|4k)', filename, re.I)
    res = res.group(0).upper() if res else "HD"
    se = re.search(r'(S\d+|E\d+)', filename, re.I)
    se = se.group(0).upper() if se else ""
    clean = re.sub(r'(480p|720p|1080p|4k|S\d+|E\d+)', '', clean, flags=re.I)
    clean = re.sub(r'[_.\-]', ' ', clean).strip().title()
    return f"🎬 {res} / {se} {clean[:25]}".strip()

async def auto_delete(c, chat_id, msg_id):
    await asyncio.sleep(120)
    try: await c.delete_messages(chat_id, msg_id)
    except: pass

# --- SEARCH ENGINE ---
async def send_results(m, query, page=0, is_cb=False):
    words = query.split()
    regex = f".*{'.*'.join([re.escape(w) for w in words])}.*"
    cursor = db.files.find({"clean_name": {"$regex": regex, "$options": "i"}})
    results = await cursor.to_list(length=100)

    if not results:
        txt = "❌ No results found!\n\n**Edit by INDRA**"
        if is_cb: return await m.answer("No more results!", show_alert=True)
        msg = await m.reply_text(txt)
        return

    start, end = page * 10, (page + 1) * 10
    page_items = results[start:end]
    total_pages = (len(results) + 9) // 10

    btns = [[
        InlineKeyboardButton("🌐 Language", callback_data=f"filt_lang_{query}_{page}"),
        InlineKeyboardButton("📂 Session", callback_data=f"filt_sess_{query}_{page}")
    ]]
    for f in page_items:
        btns.append([InlineKeyboardButton(format_btn(f['file_name']), url=f"https://t.me/{(await app.get_me()).username}?start=file_{f['_id']}")])

    nav = []
    if page > 0: nav.append(InlineKeyboardButton("<", callback_data=f"pg_{query}_{page-1}"))
    if end < len(results): nav.append(InlineKeyboardButton(">", callback_data=f"pg_{query}_{page+1}"))
    if nav: btns.append(nav)

    text = f"🔍 **Results for:** `{query.upper()}`\n📄 **Page:** `{page+1}/{total_pages}`\n\n**Edit by INDRA**"
    if is_cb: await m.message.edit(text, reply_markup=InlineKeyboardMarkup(btns))
    else:
        sent = await m.reply_text(text, reply_markup=InlineKeyboardMarkup(btns))
        if m.chat.type in ["group", "supergroup"]: asyncio.create_task(auto_delete(app, m.chat.id, sent.id))

# --- COMMANDS ---
@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    if len(m.command) > 1 and m.command[1].startswith("file_"):
        doc = await db.files.find_one({"_id": ObjectId(m.command[1].split("_")[1])})
        if doc:
            f_msg = await c.send_cached_media(m.chat.id, doc['file_id'], caption=doc['caption'])
            asyncio.create_task(auto_delete(c, m.chat.id, f_msg.id))
        return
    await m.reply_text(f"👋 Hello {m.from_user.mention}! Search movies here.")

@app.on_message(filters.command("stats"))
async def stats_cmd(c, m):
    count = await db.files.count_documents({})
    await m.reply(f"📊 **Total Indexed Files:** `{count}`")

@app.on_message(filters.command("index") & filters.user(OWNER_ID))
async def index_cmd(c, m):
    msg = await m.reply("🔄 **Indexing...**")
    count, checked = 0, 0
    async for user_msg in c.get_chat_history(CHANNEL_ID):
        checked += 1
        file = user_msg.document or user_msg.video
        if file:
            if await db.save_file(file.file_id, file.file_name, file.file_size, user_msg.caption): count += 1
        if checked % 100 == 0: await msg.edit(f"🔄 Checked: `{checked}` | Saved: `{count}`")
    await msg.edit(f"✅ Indexed `{count}` files!")

@app.on_message(filters.text & ~filters.command(["start", "stats", "index"]))
async def handle_search(c, m):
    if m.text.startswith("/"): return 
    await send_results(m, m.text.lower().strip())

# --- BOOTSTRAP ---
async def main():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("🚀 Bot is LIVE!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
