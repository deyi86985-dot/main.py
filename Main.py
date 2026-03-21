import logging
import os
import asyncio
import re
import time
import difflib
from datetime import datetime
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import UserNotParticipant, FloodWait, ChatAdminRequired
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
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
CHANNEL_ID = -1003065768519 # মুভি সোর্স চ্যানেল

# --- DATABASE HANDLER ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["RDX_ULTIMATE_V2"]
        self.users = self.db["users"]
        self.files = self.db["files"]
        self.chats = self.db["chats"]
        self.settings = self.db["settings"]

    # User Methods
    async def get_user(self, user_id):
        user = await self.users.find_one({"user_id": user_id})
        if not user:
            user = {"user_id": user_id, "is_verified": False, "is_premium": False, "is_banned": False, "plan": "Free"}
            await self.users.insert_one(user)
        return user

    async def update_user(self, user_id, data):
        await self.users.update_one({"user_id": user_id}, {"$set": data}, upsert=True)

    # File Methods
    async def save_file(self, file_id, file_name, file_size):
        clean_name = re.sub(r'[_.\-]', ' ', file_name).lower().strip()
        f_name = file_name.lower().strip()
        if not await self.files.find_one({"file_name": f_name, "file_size": file_size}):
            await self.files.insert_one({'file_id': file_id, 'file_name': f_name, 'clean_name': clean_name, 'file_size': file_size})
            return True
        return False

    # Settings Methods
    async def get_config(self, key, default):
        data = await self.settings.find_one({"key": key})
        return data["value"] if data else default

    async def set_config(self, key, value):
        await self.settings.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

db = Database(MONGO_URI)

# --- UTILS ---
def get_wish():
    hour = datetime.now().hour
    if 5 <= hour < 12: return "☀️ Good Morning"
    elif 12 <= hour < 17: return "🌤 Good Afternoon"
    elif 17 <= hour < 21: return "🌇 Good Evening"
    else: return "🌙 Good Night"

# --- WEB SERVER (For Render) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "RDX Pro Ultimate is Live!"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

app = Client("RDX_ULTRA", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- DECORATORS ---
def auth_admin(func):
    async def wrapper(client, message):
        if message.from_user.id != ADMIN_ID: return
        return await func(client, message)
    return wrapper

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    user = await db.get_user(message.from_user.id)
    if user['is_banned']: return await message.reply("❌ You are banned from using this bot.")
    
    wish = get_wish()
    text = f"✨ **{wish}, {message.from_user.mention}!**\n\nWelcome to the most advanced **Auto Filter Bot**. Search movies by name in group or PM."
    
    btns = [
        [InlineKeyboardButton("➕ Add Me to Your Group ➕", url=f"http://t.me/{client.me.username}?startgroup=true")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="open_settings"), InlineKeyboardButton("📊 Stats", callback_data="open_stats")],
        [InlineKeyboardButton("💎 Premium", callback_data="open_plan"), InlineKeyboardButton("📢 Help", callback_data="open_help")]
    ]
    await message.reply_photo(photo="https://telegra.ph/file/0c93540e1f74457e5b22b.jpg", caption=text, reply_markup=InlineKeyboardMarkup(btns))

@app.on_message(filters.command("id"))
async def id_cmd(client, message):
    await message.reply(f"🆔 **Your ID:** `{message.from_user.id}`\n📍 **Chat ID:** `{message.chat.id}`")

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_cmd(client, message):
    u_count = await db.users.count_documents({})
    f_count = await db.files.count_documents({})
    c_count = await db.chats.count_documents({})
    p_count = await db.users.count_documents({"is_premium": True})
    
    text = (
        "📊 **Bot Current Statistics**\n\n"
        f"👤 Total Users: `{u_count}`\n"
        f"💎 Premium Users: `{p_count}`\n"
        f"📂 Total Files: `{f_count}`\n"
        f"💬 Total Chats: `{c_count}`"
    )
    await message.reply(text)

# --- SEARCH LOGIC ---
@app.on_message(filters.text & ~filters.command(["start", "id", "stats", "index", "broadcast", "settings"]))
async def search_handler(client, message):
    user = await db.get_user(message.from_user.id)
    if user['is_banned']: return

    # PM Search check
    if message.chat.type == filters.chat_type.PRIVATE:
        pm_on = await db.get_config("pm_search", True)
        if not pm_on: return await message.reply("❌ PM Search is disabled by Admin.")

    query = message.text.lower().strip()
    if len(query) < 3: return

    # Regex Multi-keyword Search
    words = query.split()
    regex_pattern = "".join([f"(?=.*{re.escape(word)})" for word in words])
    
    cursor = db.files.find({
        "$or": [
            {"file_name": {"$regex": f"^{regex_pattern}.*$", "$options": "i"}},
            {"clean_name": {"$regex": f"^{regex_pattern}.*$", "$options": "i"}}
        ]
    })
    results = await cursor.to_list(length=10)
    
    if results:
        btns = []
        for f in results:
            size = round(f['file_size'] / (1024 * 1024), 2)
            btns.append([InlineKeyboardButton(f"📂 {f['file_name'].title()} ({size}MB)", callback_data=f"get_{str(f['_id'])}")])
        await message.reply_text(f"🔍 **Search results for:** `{query}`", reply_markup=InlineKeyboardMarkup(btns))
    else:
        # Spelling suggestion
        all_names = await db.files.find({}, {"file_name": 1}).to_list(length=2000)
        names_list = [n['file_name'] for n in all_names]
        matches = difflib.get_close_matches(query, names_list, n=3, cutoff=0.5)
        if matches:
            m_btns = []
            for m in matches:
                doc = await db.files.find_one({"file_name": m})
                if doc: m_btns.append([InlineKeyboardButton(f"🔎 Did you mean: {m[:30]}...", callback_data=f"sp_{str(doc['_id'])}")])
            await message.reply_text(f"😔 No results for **'{query}'**.\nCheck these suggestions:", reply_markup=InlineKeyboardMarkup(m_btns))

# --- ADMIN TOOLS ---

@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def index_cmd(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/index @username`")
    target = message.command[1]
    m = await message.reply("🔄 **Scanning files...**")
    count = 0
    try:
        async for user_msg in client.get_chat_history(target):
            file = user_msg.document or user_msg.video
            if file:
                if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size):
                    count += 1
        await m.edit(f"✅ **Indexing Complete!** Added `{count}` files.")
    except Exception as e:
        await m.edit(f"❌ Error: `{e}`")

@app.on_message(filters.command("deletefiles") & filters.user(ADMIN_ID))
async def delete_junk_cmd(client, message):
    m = await message.reply("🧹 **Cleaning database (CamRip/PreDVD)...**")
    query = {"$or": [
        {"file_name": {"$regex": "camrip", "$options": "i"}},
        {"file_name": {"$regex": "predvd", "$options": "i"}},
        {"file_name": {"$regex": "cam", "$options": "i"}}
    ]}
    deleted = await db.files.delete_many(query)
    await m.edit(f"✅ Cleaned `{deleted.deleted_count}` junk files from DB.")

@app.on_message(filters.command("broadcast") & filters.user(ADMIN_ID))
async def broadcast_cmd(client, message):
    if not message.reply_to_message: return await message.reply("Reply to a message to broadcast.")
    users = await db.users.find().to_list(length=10000)
    msg = await message.reply(f"🚀 **Broadcast started to {len(users)} users...**")
    done, failed = 0, 0
    for u in users:
        try:
            await message.reply_to_message.copy(u['user_id'])
            done += 1
            await asyncio.sleep(0.1)
        except: failed += 1
    await msg.edit(f"✅ **Broadcast Done!**\nSuccess: {done}\nFailed: {failed}")

@app.on_message(filters.command("ban") & filters.user(ADMIN_ID))
async def ban_cmd(client, message):
    if len(message.command) < 2: return
    uid = int(message.command[1])
    await db.update_user(uid, {"is_banned": True})
    await message.reply(f"🚫 User `{uid}` has been banned.")

@app.on_message(filters.command("add_premium") & filters.user(ADMIN_ID))
async def add_premium_cmd(client, message):
    if len(message.command) < 2: return
    uid = int(message.command[1])
    await db.update_user(uid, {"is_premium": True, "plan": "Premium"})
    await message.reply(f"💎 User `{uid}` is now a Premium member!")

@app.on_message(filters.command("restart") & filters.user(ADMIN_ID))
async def restart_cmd(client, message):
    await message.reply("🔄 **Restarting bot...**")
    os.execl(sys.executable, sys.executable, *sys.argv)

# --- CALLBACK QUERIES (Handling ObjectIds) ---
@app.on_callback_query(filters.regex(r"^get_"))
async def cb_get_file(client, query: CallbackQuery):
    doc_id = query.data.split("_")[1]
    doc = await db.files.find_one({"_id": ObjectId(doc_id)})
    if doc:
        try:
            await client.send_cached_media(chat_id=query.from_user.id, file_id=doc['file_id'])
            await query.answer("File sent to your PM!", show_alert=True)
        except:
            await query.answer("Please START the bot in private first!", show_alert=True)

@app.on_callback_query(filters.regex(r"^open_settings"))
async def cb_settings(client, query: CallbackQuery):
    if query.from_user.id != ADMIN_ID: return
    pm_search = await db.get_config("pm_search", True)
    btns = [
        [InlineKeyboardButton(f"PM Search: {'✅ ON' if pm_search else '❌ OFF'}", callback_data="toggle_pm")],
        [InlineKeyboardButton("🧹 Clean DB", command="deletefiles"), InlineKeyboardButton("📊 Stats", callback_data="open_stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_start")]
    ]
    await query.message.edit_text("⚙️ **Admin Settings Menu**", reply_markup=InlineKeyboardMarkup(btns))

@app.on_callback_query(filters.regex(r"^toggle_pm"))
async def cb_toggle_pm(client, query: CallbackQuery):
    curr = await db.get_config("pm_search", True)
    await db.set_config("pm_search", not curr)
    await cb_settings(client, query)

# --- BOOTSTRAP ---
async def start_rdx():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("🚀 RDX ULTIMATE MASTER IS ONLINE!")
    await idle()

if __name__ == "__main__":
    import sys
    asyncio.get_event_loop().run_until_complete(start_rdx())
