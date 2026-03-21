import logging
import os
import asyncio
import difflib
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION (Updated with your IDs) ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

ADMIN_ID = 6783893816
CHANNEL_ID = -1003065768519

# --- DATABASE HANDLER ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["RDX_ULTRA_MASTER_DB"]
        self.files = self.db["files"]
        self.settings = self.db["settings"]
        logger.info("✅ Database connected successfully.")

    async def save_file(self, file_id, file_name, file_size):
        f_name = file_name.lower().strip()
        exists = await self.files.find_one({"file_name": f_name, "file_size": file_size})
        if not exists:
            await self.files.insert_one({'file_id': file_id, 'file_name': f_name, 'file_size': file_size})
            return True
        return False

    async def get_all_names(self):
        cursor = self.files.find({}, {"file_name": 1})
        names = await cursor.to_list(length=3000)
        return [doc['file_name'] for doc in names]

    async def get_config(self, key, default):
        data = await self.settings.find_one({"key": key})
        return data["value"] if data else default

    async def set_config(self, key, value):
        await self.settings.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

db = Database(MONGO_URI)

# --- WEB SERVER (For Render Health Check) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "RDX Pro Server is Alive!"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- BOT CLIENT ---
app = Client("RDX_FINAL", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- SEARCH LOGIC (PM & Group) ---
@app.on_message(filters.text & ~filters.command(["start", "stats", "index", "setstart", "setimg"]))
async def handle_search(client, message):
    query = message.text.lower().strip()
    if len(query) < 3: return
    
    logger.info(f"🔍 Searching for: {query} in {message.chat.type}")
    
    # Database Search using Regex
    cursor = db.files.find({"file_name": {"$regex": query, "$options": "i"}})
    results = await cursor.to_list(length=10)
    
    if results:
        btns = []
        for f in results:
            size = round(f['file_size'] / (1024 * 1024), 2)
            btn_text = f"📂 {f['file_name'].title()} ({size}MB)"
            btns.append([InlineKeyboardButton(btn_text, callback_data=f"get_{f['file_id']}")])
        
        await message.reply_text(f"✅ **Results for:** `{query}`", reply_markup=InlineKeyboardMarkup(btns))
    else:
        # Spelling Suggestion Logic
        all_names = await db.get_all_names()
        matches = difflib.get_close_matches(query, all_names, n=3, cutoff=0.5)
        if matches:
            m_btns = [[InlineKeyboardButton(f"🔎 Did you mean: {m.title()}?", callback_data=f"search_{m}")] for m in matches]
            await message.reply_text(f"😔 No exact match for `{query}`.\nDid you mean one of these?", reply_markup=InlineKeyboardMarkup(m_btns))
        elif message.chat.type == filters.chat_type.PRIVATE:
            await message.reply_text(f"❌ No results found for `{query}`.\nTry checking the spelling or forwarding files to index them.")

# --- ADMIN COMMANDS ---
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    text = await db.get_config("start_text", f"👋 **Hello {message.from_user.mention}!**\nWelcome to **RDX Filter Bot**. Search movies in Group or Private!")
    img = await db.get_config("start_img", "https://telegra.ph/file/0c93540e1f74457e5b22b.jpg")
    btns = [[InlineKeyboardButton("➕ Add Me to Your Group ➕", url=f"http://t.me/{client.me.username}?startgroup=true")]]
    try:
        await message.reply_photo(photo=img, caption=text, reply_markup=InlineKeyboardMarkup(btns))
    except:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns))

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message):
    count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Database Status:** `{count}` files indexed.")

@app.on_message(filters.command("setstart") & filters.user(ADMIN_ID))
async def set_start(client, message):
    if len(message.command) < 2: return
    await db.set_config("start_text", message.text.split(None, 1)[1])
    await message.reply("✅ Welcome message updated!")

@app.on_message(filters.command("setimg") & filters.user(ADMIN_ID))
async def set_img(client, message):
    if len(message.command) < 2: return
    await db.set_config("start_img", message.command[1])
    await message.reply("✅ Welcome image updated!")

@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def index_handler(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/index @Username`")
    m = await message.reply("🔄 **Scanning channel...**")
    count = 0
    try:
        async for user_msg in client.get_chat_history(message.command[1]):
            file = user_msg.document or user_msg.video
            if file:
                if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size):
                    count += 1
        await m.edit(f"✅ **Success!** Added `{count}` files to database.")
    except Exception as e:
        await m.edit(f"❌ **Error:** `{e}`\n\n*Tip: Forward files manually to the bot to index them.*")

# --- AUTO INDEXING (When files are forwarded/posted) ---
@app.on_message((filters.chat(CHANNEL_ID) | filters.forwarded) & (filters.document | filters.video))
async def auto_index(client, message):
    file = message.document or message.video
    f_name = getattr(file, "file_name", "Untitled")
    if await db.save_file(file.file_id, f_name, file.file_size):
        logger.info(f"Auto-indexed: {f_name}")

# --- CALLBACKS ---
@app.on_callback_query(filters.regex(r"^get_"))
async def cb_send_file(client, query: CallbackQuery):
    try:
        await client.send_cached_media(chat_id=query.from_user.id, file_id=query.data.split("_")[1])
        await query.answer("File sent!", show_alert=True)
    except:
        await query.answer("Please START the bot in private first!", show_alert=True)

@app.on_callback_query(filters.regex(r"^search_"))
async def cb_suggest_search(client, query: CallbackQuery):
    q = query.data.split("_", 1)[1]
    cursor = db.files.find({"file_name": {"$regex": q, "$options": "i"}})
    res = await cursor.to_list(length=10)
    if res:
        btns = [[InlineKeyboardButton(f"📂 {f['file_name'].title()}", callback_data=f"get_{f['file_id']}")] for f in res]
        await query.message.edit_text(f"🔍 **Results for:** `{q}`", reply_markup=InlineKeyboardMarkup(btns))

# --- MAIN RUNNER ---
async def start_rdx():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("🚀 BOT IS ONLINE AND READY")
    await idle()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_rdx())
