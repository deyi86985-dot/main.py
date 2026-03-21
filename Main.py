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
# Render-er log-e sob kichu dekhar jonno logging set kora holo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION (Apnar deya details ekhane set kora holo) ---
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
        self.db = self._client["RDX_GROUP_FILTER_DB"]
        self.files = self.db["files"]
        self.settings = self.db["settings"]

    async def save_file(self, file_id, file_name, file_size):
        # File name-ke lower case-e save kora hoy jate search easy hoy
        f_name = file_name.lower().strip()
        exists = await self.files.find_one({"file_name": f_name, "file_size": file_size})
        if not exists:
            await self.files.insert_one({
                'file_id': file_id, 
                'file_name': f_name, 
                'file_size': file_size
            })
            return True
        return False

    async def get_all_names(self):
        # Spelling suggestion-er jonno sob nam fetch kora
        cursor = self.files.find({}, {"file_name": 1})
        names = await cursor.to_list(length=5000)
        return [doc['file_name'] for doc in names]

    async def get_config(self, key, default):
        data = await self.settings.find_one({"key": key})
        return data["value"] if data else default

    async def set_config(self, key, value):
        await self.settings.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

db = Database(MONGO_URI)

# --- WEB SERVER (Render-e bot active rakhar jonno) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): 
    return "INDRA Filter Bot is Live! 🚀"

def run_flask():
    # Render-er port 8080 default thake
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- BOT CLIENT ---
app = Client(
    "INDRA_GROUP_BOT", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN, 
    in_memory=True
)

# --- COMMAND HANDLERS ---

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    text = await db.get_config("start_text", f"👋 **Hello {message.from_user.mention}!**\n\nAmi INDRA Auto Filter Bot. Movie khunje pete amake group-e add korun!")
    img = await db.get_config("start_img", "https://telegra.ph/file/0c93540e1f74457e5b22b.jpg")
    
    buttons = [[
        InlineKeyboardButton("➕ Add Me to Your Group ➕", url=f"http://t.me/{client.me.username}?startgroup=true")
    ]]
    
    try:
        await message.reply_photo(photo=img, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message):
    count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Current Database Stats:** `{count}` files indexed.")

@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def index_handler(client, message):
    # Channel theke file scan korar command
    if len(message.command) < 2: 
        return await message.reply("Usage: `/index @ChannelUsername`")
    
    m = await message.reply("🔄 **Channel scan kora hochche... Ektu opekkha korun.**")
    count = 0
    try:
        async for user_msg in client.get_chat_history(message.command[1]):
            file = user_msg.document or user_msg.video
            if file:
                f_name = getattr(file, "file_name", "Untitled")
                if await db.save_file(file.file_id, f_name, file.file_size):
                    count += 1
        await m.edit(f"✅ **Success!** Mot `{count}` ti file database-e add kora hoyeche.")
    except Exception as e:
        await m.edit(f"❌ **Error:** `{e}`\n\n*Tip: Bot-ke channel-e Admin banan ba movie forward korun.*")

# --- GROUP SEARCH LOGIC (Core Feature) ---

@app.on_message(filters.text & filters.group)
async def group_search_handler(client, message):
    query = message.text.lower().strip()
    # Search start hobe jodi query 3 ti akkhhor-er beshi hoy
    if len(query) < 3: 
        return

    logger.info(f"Group Search: {query} in {message.chat.title}")
    
    # MongoDB regex search (Partial matching + Case Insensitive)
    cursor = db.files.find({"file_name": {"$regex": query, "$options": "i"}})
    results = await cursor.to_list(length=10)
    
    if results:
        buttons = []
        for f in results:
            size = round(f['file_size'] / (1024 * 1024), 2)
            btn_text = f"📂 {f['file_name'].title()} ({size} MB)"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"get_{f['file_id']}")])
        
        await message.reply_text(
            f"🔍 **I found {len(results)} results for:** `{query}`",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        # Spelling Suggestion (Did you mean?) logic
        all_names = await db.get_all_names()
        matches = difflib.get_close_matches(query, all_names, n=3, cutoff=0.5)
        
        if matches:
            m_btns = [[InlineKeyboardButton(f"🔎 Did you mean: {m.title()}?", callback_data=f"search_{m}")] for m in matches]
            await message.reply_text(
                f"😔 **'{query}'** namer kichu paini.\nNicher gulo ki apni khunjchen?",
                reply_markup=InlineKeyboardMarkup(m_btns)
            )

# --- AUTO INDEXING ---
# Channel-e notun movie ashle ba forward korle auto save hobe
@app.on_message((filters.chat(CHANNEL_ID) | filters.forwarded) & (filters.document | filters.video))
async def auto_index_handler(client, message):
    file = message.document or message.video
    f_name = getattr(file, "file_name", "Untitled")
    if await db.save_file(file.file_id, f_name, file.file_size):
        logger.info(f"Auto-indexed: {f_name}")

# --- CALLBACK QUERIES ---

@app.on_callback_query(filters.regex(r"^get_"))
async def cb_get_file(client, query: CallbackQuery):
    f_id = query.data.split("_")[1]
    try:
        await client.send_cached_media(chat_id=query.from_user.id, file_id=f_id)
        await query.answer("File apnar PM-e pathano hoyeche!", show_alert=True)
    except:
        await query.answer("Doya kore bot-ke age Private-e START korun!", show_alert=True)

@app.on_callback_query(filters.regex(r"^search_"))
async def cb_suggestion_search(client, query: CallbackQuery):
    # Suggestion click korle search hobe
    new_q = query.data.split("_", 1)[1]
    cursor = db.files.find({"file_name": {"$regex": new_q, "$options": "i"}})
    res = await cursor.to_list(length=10)
    if res:
        btns = [[InlineKeyboardButton(f"📂 {f['file_name'].title()}", callback_data=f"get_{f['file_id']}")] for f in res]
        await query.message.edit_text(f"🔍 **Results for:** `{new_q}`", reply_markup=InlineKeyboardMarkup(btns))

# --- SETTINGS COMMANDS ---

@app.on_message(filters.command("setstart") & filters.user(ADMIN_ID))
async def set_start_cmd(client, message):
    if len(message.command) < 2: return
    await db.set_config("start_text", message.text.split(None, 1)[1])
    await message.reply("✅ Welcome text update hoyeche!")

@app.on_message(filters.command("setimg") & filters.user(ADMIN_ID))
async def set_img_cmd(client, message):
    if len(message.command) < 2: return
    await db.set_config("start_img", message.command[1])
    await message.reply("✅ Welcome image update hoyeche!")

# --- BOOTSTRAP ---

async def start_services():
    # Web server background-e start kora
    Thread(target=run_flask, daemon=True).start()
    
    # Bot start kora
    await app.start()
    me = await app.get_me()
    logger.info(f"🚀 @{me.username} is now online and searching in groups!")
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal Startup Error: {e}")
