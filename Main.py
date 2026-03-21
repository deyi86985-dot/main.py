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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
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
        self.db = self._client["RDX_Pro_Database"]
        self.files = self.db["files"]

    async def save_file(self, file_id, file_name, file_size):
        f_name = file_name.lower().strip()
        exists = await self.files.find_one({"file_name": f_name, "file_size": file_size})
        if not exists:
            await self.files.insert_one({'file_id': file_id, 'file_name': f_name, 'file_size': file_size})
            return True
        return False

    async def get_all_file_names(self):
        """Used for spelling suggestions"""
        cursor = self.files.find({}, {"file_name": 1})
        names = await cursor.to_list(length=5000) # Fetching up to 5k names for comparison
        return [doc['file_name'] for doc in names]

db = Database(MONGO_URI)

# --- WEB SERVER (For Render) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is Online with Spell Check!"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- BOT CLIENT ---
app = Client("RDX_SPELL_BOT", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    text = f"👋 **Hello {message.from_user.mention}!**\n\nI am the Advanced Filter Bot. Just send me a movie name with or without typos, and I will find it!"
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ Add Me to Your Group ➕", url=f"http://t.me/{client.me.username}?startgroup=true")
    ]]))

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message):
    count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Database Stats:** `{count}` files indexed.")

@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def index_handler(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/index @username`")
    m = await message.reply("🔄 **Indexing...**")
    count = 0
    try:
        async for user_msg in client.get_chat_history(message.command[1]):
            file = user_msg.document or user_msg.video or user_msg.audio
            if file:
                if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size):
                    count += 1
        await m.edit(f"✅ Indexed `{count}` files.")
    except Exception as e:
        await m.edit(f"❌ Error: `{e}`")

# --- SEARCH LOGIC WITH SPELL CHECK ---
@app.on_message(filters.text & ~filters.command(["start", "index", "stats"]))
async def search_handler(client, message):
    query = message.text.lower().strip()
    if len(query) < 3: return

    # 1. Exact/Regex Search
    cursor = db.files.find({"file_name": {"$regex": query, "$options": "i"}})
    results = await cursor.to_list(length=10)
    
    if results:
        buttons = []
        for f in results:
            size = round(f['file_size'] / (1024 * 1024), 2)
            btn_text = f"📂 {f['file_name'].title()} ({size}MB)"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"get_{f['file_id']}")])
        
        await message.reply_text(f"🔍 **Search Results for:** `{query}`", reply_markup=InlineKeyboardMarkup(buttons))
    
    else:
        # 2. Spell Check (Did you mean?)
        all_names = await db.get_all_file_names()
        suggestions = difflib.get_close_matches(query, all_names, n=5, cutoff=0.5)
        
        if suggestions:
            suggest_btns = []
            for s in suggestions:
                suggest_btns.append([InlineKeyboardButton(f"🔎 Did you mean: {s.title()}?", switch_inline_query_current_chat=s)])
            
            # Since inline query might be complex, we just send text buttons to re-search
            manual_btns = []
            for s in suggestions:
                manual_btns.append([InlineKeyboardButton(f"👉 {s.title()}", callback_data=f"search_{s}")])
            
            await message.reply_text(
                f"😔 **No results for** `{query}`.\n\n**Did you mean one of these?**",
                reply_markup=InlineKeyboardMarkup(manual_btns)
            )
        elif message.chat.type == filters.chat_type.PRIVATE:
            await message.reply_text("❌ No results found and no suggestions available.")

# --- CALLBACKS ---
@app.on_callback_query(filters.regex(r"^get_"))
async def cb_get(client, query: CallbackQuery):
    try:
        await client.send_cached_media(chat_id=query.from_user.id, file_id=query.data.split("_")[1])
        await query.answer("File sent!", show_alert=True)
    except:
        await query.answer("Start the bot in PM first!", show_alert=True)

@app.on_callback_query(filters.regex(r"^search_"))
async def cb_search(client, query: CallbackQuery):
    """Triggered when user clicks a spelling suggestion"""
    new_query = query.data.split("_", 1)[1]
    # We edit the message to show new results
    cursor = db.files.find({"file_name": {"$regex": new_query}})
    results = await cursor.to_list(length=10)
    if results:
        buttons = []
        for f in results:
            size = round(f['file_size'] / (1024 * 1024), 2)
            buttons.append([InlineKeyboardButton(f"📂 {f['file_name'].title()} ({size}MB)", callback_data=f"get_{f['file_id']}")])
        await query.message.edit_text(f"🔍 **Results for suggested keyword:** `{new_query}`", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await query.answer("No results for this suggestion either.")

# --- AUTO SAVE ---
@app.on_message((filters.chat(CHANNEL_ID) | filters.forwarded) & (filters.document | filters.video | filters.audio))
async def auto_save(client, message):
    file = message.document or message.video or message.audio
    if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size):
        logger.info(f"Auto-indexed: {getattr(file, 'file_name', 'Untitled')}")

# --- START ---
async def main():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("✅ Bot with Spell-Check is Live!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
