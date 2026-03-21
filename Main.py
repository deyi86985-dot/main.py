import logging
import os
import asyncio
import difflib
import re
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

ADMIN_ID = 6783893816
CHANNEL_ID = -1003065768519

# --- DATABASE ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["RDX_ULTRA_FILTER_DB"]
        self.files = self.db["files"]

    async def save_file(self, file_id, file_name, file_size):
        f_name = file_name.lower().strip()
        # Duplicate check to save DB space
        exists = await self.files.find_one({"file_name": f_name, "file_size": file_size})
        if not exists:
            await self.files.insert_one({'file_id': file_id, 'file_name': f_name, 'file_size': file_size})
            return True
        return False

    async def get_all_names(self):
        cursor = self.files.find({}, {"file_name": 1})
        names = await cursor.to_list(length=10000) # Increased length for full scan
        return [doc['file_name'] for doc in names]

db = Database(MONGO_URI)

# --- WEB SERVER (For Uptime) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "RDX Server is Active! 🚀"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

app = Client("RDX_ULTRA_BOT", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- SEARCH HELPER ---
def get_regex_query(query):
    # Regex e space gulo ke dot ba wildcard diye replace kora jate sob file ashe
    query_parts = query.split()
    regex_pattern = ".*".join(map(re.escape, query_parts))
    return f".*{regex_pattern}.*"

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    await message.reply_text(f"👋 **Hello {message.from_user.mention}!**\nSearch movies here or in group. Use /stats to see indexed files.")

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message):
    count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Total Indexed Files:** `{count}`")

@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def index_handler(client, message):
    if len(message.command) < 2: return
    target = message.command[1]
    m = await message.reply(f"🔄 **Scanning `{target}`...**")
    count = 0
    try:
        async for user_msg in client.get_chat_history(target):
            # Scan both Videos and Documents
            file = user_msg.document or user_msg.video
            if file:
                f_name = getattr(file, "file_name", "Untitled")
                if await db.save_file(file.file_id, f_name, file.file_size):
                    count += 1
        await m.edit(f"✅ Indexed `{count}` files successfully!")
    except Exception as e:
        await m.edit(f"❌ Error: `{e}`")

# --- IMPROVED SEARCH LOGIC ---
@app.on_message(filters.text & ~filters.command(["start", "stats", "index"]))
async def search_handler(client, message):
    query = message.text.lower().strip()
    if len(query) < 3: return
    
    # Advanced Regex Search
    regex_q = get_regex_query(query)
    cursor = db.files.find({"file_name": {"$regex": regex_q, "$options": "i"}})
    results = await cursor.to_list(length=20) # Showing more results
    
    if results:
        btns = []
        for f in results:
            size = round(f['file_size'] / (1024 * 1024), 2)
            btns.append([InlineKeyboardButton(f"📂 {f['file_name'].title()} ({size}MB)", callback_data=f"get_{f['file_id']}")])
        await message.reply_text(f"🔍 **Search Results for:** `{query}`", reply_markup=InlineKeyboardMarkup(btns))
    else:
        # Suggestion Logic if no direct results
        all_names = await db.get_all_names()
        matches = difflib.get_close_matches(query, all_names, n=5, cutoff=0.4) # Looser cutoff for better matching
        if matches:
            # Shortened callback data to avoid Telegram's 64-byte limit
            m_btns = []
            for i, m in enumerate(matches):
                # We store the match name in a way that we can search again
                m_btns.append([InlineKeyboardButton(f"🔎 Did you mean: {m[:40].title()}...", callback_data=f"sp_{m[:50]}")])
            await message.reply_text(f"😔 **'{query}'** namer kichu paini.\nDid you mean one of these?", reply_markup=InlineKeyboardMarkup(m_btns))

# --- CALLBACKS FIX ---

@app.on_callback_query(filters.regex(r"^sp_"))
async def cb_spell_fix(client, query: CallbackQuery):
    # Suggestion click korle seiti ke Regex diye search korbe
    target_name = query.data.split("sp_")[1]
    await query.answer(f"Searching for {target_name}...")
    
    regex_q = get_regex_query(target_name)
    cursor = db.files.find({"file_name": {"$regex": regex_q, "$options": "i"}})
    res = await cursor.to_list(length=15)
    
    if res:
        btns = [[InlineKeyboardButton(f"📂 {f['file_name'].title()}", callback_data=f"get_{f['file_id']}")] for f in res]
        await query.message.edit_text(f"🔍 **Results for:** `{target_name.title()}`", reply_markup=InlineKeyboardMarkup(btns))
    else:
        await query.answer("No files found for this suggestion!", show_alert=True)

@app.on_callback_query(filters.regex(r"^get_"))
async def cb_get_file(client, query: CallbackQuery):
    f_id = query.data.split("_")[1]
    try:
        await client.send_cached_media(chat_id=query.from_user.id, file_id=f_id)
        await query.answer("File sent to your PM!", show_alert=True)
    except:
        await query.answer("Please START the bot in private (PM) first!", show_alert=True)

# --- AUTO SAVE ---
@app.on_message((filters.chat(CHANNEL_ID) | filters.forwarded) & (filters.document | filters.video))
async def auto_save(client, message):
    file = message.document or message.video
    if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size):
        logger.info("New file indexed.")

# --- RUN ---
async def start_rdx():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("🚀 BOT STARTED SUCCESSFULLY!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_rdx()) 
