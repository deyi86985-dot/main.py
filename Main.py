import logging
import os
import asyncio
import difflib
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- LOGGING ---
# Render-er Logs-e sob dekhar jonno
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION (Fixed with your IDs) ---
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
        self.db = self._client["RDX_ULTRA_DB_FINAL"]
        self.files = self.db["files"]
        self.settings = self.db["settings"]

    async def save_file(self, file_id, file_name, file_size):
        f_name = file_name.lower().strip()
        # Duplicate check
        exists = await self.files.find_one({"file_name": f_name, "file_size": file_size})
        if not exists:
            await self.files.insert_one({'file_id': file_id, 'file_name': f_name, 'file_size': file_size})
            return True
        return False

    async def get_all_names(self):
        cursor = self.files.find({}, {"file_name": 1})
        names = await cursor.to_list(length=3000)
        return [doc['file_name'] for doc in names]

db = Database(MONGO_URI)

# --- WEB SERVER (Required for Render Health Check) ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "RDX Filter Bot is Live and Running!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Flask Web Server starting on port {port}")
    web_app.run(host='0.0.0.0', port=port)

# --- BOT CLIENT ---
# using in_memory=True to avoid SQLite database lock errors on Render
app = Client(
    "RDX_FINAL_BOT",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# --- HANDLERS ---

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    logger.info(f"Start command received from {message.from_user.id}")
    text = f"👋 **Hello {message.from_user.mention}!**\n\nI am the Advanced Auto Filter Bot. Index files from your channel and search them here or in groups!"
    buttons = [[InlineKeyboardButton("➕ Add Me to Your Group ➕", url=f"http://t.me/{client.me.username}?startgroup=true")]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message):
    count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Database Stats:** `{count}` files indexed.")

@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def index_handler(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: `/index @ChannelUsername`")
    
    target = message.command[1]
    m = await message.reply("🔄 **Indexing Channel Files... Please wait.**")
    
    count = 0
    try:
        async for user_msg in client.get_chat_history(target):
            file = user_msg.document or user_msg.video
            if file:
                f_name = getattr(file, "file_name", "Untitled")
                if await db.save_file(file.file_id, f_name, file.file_size):
                    count += 1
        await m.edit(f"✅ **Success!** Added `{count}` files to database.")
    except Exception as e:
        await m.edit(f"❌ **Error:** `{e}`\n\n*Tip: Forward files to the bot if this fails.*")

# --- SEARCH LOGIC (Spell Check included) ---
@app.on_message(filters.text & ~filters.command(["start", "stats", "index"]))
async def search_handler(client, message):
    query = message.text.lower().strip()
    if len(query) < 3: return
    
    logger.info(f"🔍 New Search: {query} from {message.chat.id}")

    # MongoDB Search
    cursor = db.files.find({"file_name": {"$regex": query, "$options": "i"}})
    results = await cursor.to_list(length=10)
    
    if results:
        btns = []
        for f in results:
            size = round(f['file_size'] / (1024 * 1024), 2)
            btn_text = f"📂 {f['file_name'].title()} ({size}MB)"
            btns.append([InlineKeyboardButton(btn_text, callback_data=f"get_{f['file_id']}")])
        
        await message.reply_text(f"🔍 **Search results for:** `{query}`", reply_markup=InlineKeyboardMarkup(btns))
    else:
        # Spelling Suggestion
        all_names = await db.get_all_names()
        matches = difflib.get_close_matches(query, all_names, n=3, cutoff=0.5)
        if matches:
            m_btns = [[InlineKeyboardButton(f"🔎 Did you mean: {m.title()}?", callback_data=f"search_{m}")] for m in matches]
            await message.reply_text(f"😔 No exact match for `{query}`.\nDid you mean?", reply_markup=InlineKeyboardMarkup(m_btns))
        elif message.chat.type == filters.chat_type.PRIVATE:
            await message.reply_text("❌ No results found. Forward files to me to index them!")

# --- AUTO INDEXING ---
@app.on_message((filters.chat(CHANNEL_ID) | filters.forwarded) & (filters.document | filters.video))
async def auto_save_handler(client, message):
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

# --- MAIN RUNNER (Fixed for Render Compatibility) ---
async def start_bot():
    # Start Web Server in background
    Thread(target=run_flask, daemon=True).start()
    
    # Start Telegram Client
    try:
        logger.info("Connecting to Telegram...")
        await app.start()
        me = await app.get_me()
        logger.info(f"✅ Bot is ONLINE as @{me.username}")
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        return

    await idle()
    await app.stop()

if __name__ == "__main__":
    # Standard entry point to handle loops properly
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
    except Exception as e:
        logger.error(f"Critical Error: {e}")
