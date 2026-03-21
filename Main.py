import logging
import os
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION (Directly using your details) ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

# Change these two!
ADMIN_ID = 6783893816
CHANNEL_ID = -1003065768519

# --- DATABASE HANDLER ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["Ultimate_RDX_DB"]
        self.files = self.db["files"]
        self.settings = self.db["settings"]

    async def save_file(self, file_id, file_name, file_size):
        file_name = file_name.lower().strip()
        exists = await self.files.find_one({"file_name": file_name, "file_size": file_size})
        if not exists:
            await self.files.insert_one({'file_id': file_id, 'file_name': file_name, 'file_size': file_size})
            return True
        return False

    async def get_setting(self, key, default):
        doc = await self.settings.find_one({"key": key})
        return doc['value'] if doc else default

    async def set_setting(self, key, value):
        await self.settings.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

db = Database(MONGO_URI)

# --- WEB SERVER (For Render Uptime) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is Online and Ready!"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- BOT CLIENT ---
app = Client("Ultimate_RDX_Bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- ADMIN DECORATOR ---
def admin_only(func):
    async def wrapper(client, message):
        if message.from_user.id != ADMIN_ID: return
        return await func(client, message)
    return wrapper

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    # Dynamic content from DB
    text = await db.get_setting("start_text", f"👋 **Welcome {message.from_user.mention}!**\n\nI am the most powerful Auto Filter Bot. Search movies in Group or Private!")
    img = await db.get_setting("start_img", "https://telegra.ph/file/0c93540e1f74457e5b22b.jpg")
    
    buttons = [
        [InlineKeyboardButton("➕ Add Me to Your Group ➕", url=f"http://t.me/{client.me.username}?startgroup=true")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats_btn"), InlineKeyboardButton("📢 Updates", url="https://t.me/CINESOCIETY_OFFICIAL")],
        [InlineKeyboardButton("🛠 Help", callback_data="help_btn"), InlineKeyboardButton("ℹ️ About", callback_data="about_btn")]
    ]
    
    try:
        await message.reply_photo(photo=img, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- ADMIN COMMANDS ---

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_cmd(client, message):
    count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Database Statistics:**\n\nTotal Files Indexed: `{count}`")

@app.on_message(filters.command("setstart") & filters.user(ADMIN_ID))
async def set_start_txt(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/setstart Your New Message`")
    new_text = message.text.split(None, 1)[1]
    await db.set_setting("start_text", new_text)
    await message.reply("✅ **Welcome Text updated!**")

@app.on_message(filters.command("setimg") & filters.user(ADMIN_ID))
async def set_start_pht(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/setimg Direct_Image_Link`")
    new_img = message.command[1]
    await db.set_setting("start_img", new_img)
    await message.reply("✅ **Welcome Image updated!**")

@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def index_cmd(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/index @ChannelUsername`")
    target = message.command[1]
    status = await message.reply("🔄 **Starting Indexing Process...**")
    
    count = 0
    try:
        async for user_msg in client.get_chat_history(target):
            file = user_msg.document or user_msg.video or user_msg.audio
            if file:
                if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size):
                    count += 1
        await status.edit(f"✅ **Indexing Successful!**\nAdded **{count}** files to the database.")
    except Exception as e:
        await status.edit(f"❌ **Error:** `{e}`\n\n*Tip: Forward files to the bot if this fails.*")

# --- SEARCH LOGIC (Works in Private and Groups) ---

@app.on_message(filters.text & ~filters.command(["start", "index", "stats", "setstart", "setimg", "plan"]))
async def search_handler(client, message):
    query = message.text.lower().strip()
    if len(query) < 3: return

    # Mongo Search using regex
    cursor = db.files.find({"file_name": {"$regex": query}})
    results = await cursor.to_list(length=10)
    
    if results:
        buttons = []
        for f in results:
            size_mb = round(f['file_size'] / (1024 * 1024), 2)
            btn_text = f"📂 {f['file_name'].title()} ({size_mb} MB)"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"get_{f['file_id']}")])
        
        await message.reply_text(
            f"🔍 **Found {len(results)} results for:** `{query}`",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    elif message.chat.type == "private":
        await message.reply_text(f"❌ **No results found for:** `{query}`\nTry checking the spelling or indexing files.")

# --- AUTO INDEXING (When files are forwarded or posted in channel) ---

@app.on_message((filters.chat(CHANNEL_ID) | filters.forwarded) & (filters.document | filters.video | filters.audio))
async def auto_save(client, message):
    file = message.document or message.video or message.audio
    file_name = getattr(file, "file_name", "Untitled")
    if await db.save_file(file.file_id, file_name, file.file_size):
        logger.info(f"Auto-indexed: {file_name}")

# --- CALLBACKS ---

@app.on_callback_query(filters.regex(r"^get_"))
async def send_file_cb(client, query: CallbackQuery):
    file_id = query.data.split("_")[1]
    try:
        await client.send_cached_media(chat_id=query.from_user.id, file_id=file_id)
        await query.answer("Check your Inbox! File sent.", show_alert=True)
    except:
        await query.answer("Please START the bot in private first!", show_alert=True)

@app.on_callback_query(filters.regex(r"_btn$"))
async def ui_callbacks(client, query: CallbackQuery):
    data = query.data
    if data == "stats_btn":
        count = await db.files.count_documents({})
        await query.answer(f"Database Stats: {count} Files Indexed", show_alert=True)
    elif data == "help_btn":
        await query.message.edit_caption("💡 **Help Menu:**\n1. Add me to a group.\n2. Search movie names.\n3. Click results to get file.")

# --- RUN BOT ---

async def start_rdx_pro():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    bot_info = await app.get_me()
    logger.info(f"🚀 @{bot_info.username} is fully Operational!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_rdx_pro())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal Startup Error: {e}")
