import logging
import os
import asyncio
import re
import difflib
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
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

OWNER_ID = 6783893816 
CHANNEL_ID = -1003776932894

DELETE_WARNING = "⚠️ ❌👉This file automatically❗delete after 2 minute❗so please forward in another chat👈❌"

# --- DATABASE HANDLER ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["RDX_ULTRA_V9_STABLE"] # একদম নতুন ডাটাবেস
        self.files = self.db["files"]
        self.admins = self.db["admins"]
        self.banned = self.db["banned"]

    async def add_admin(self, user_id):
        await self.admins.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)

    async def is_admin(self, user_id):
        if user_id == OWNER_ID: return True
        return await self.admins.find_one({"user_id": user_id}) is not None

    async def save_file(self, file_id, file_name, file_size, caption):
        clean_name = re.sub(r'[_.\-]', ' ', file_name).lower().strip()
        f_name = file_name.lower().strip()
        if not await self.files.find_one({"file_name": f_name, "file_size": file_size}):
            await self.files.insert_one({
                'file_id': file_id, 
                'file_name': f_name, 
                'clean_name': clean_name, 
                'file_size': file_size,
                'caption': caption or f_name.upper()
            })
            return True
        return False

    async def get_all_names(self):
        cursor = self.files.find({}, {"file_name": 1})
        res = await cursor.to_list(length=15000)
        return [f['file_name'] for f in res]

db = Database(MONGO_URI)

# --- HELPERS ---
def format_label(filename):
    res_match = re.search(r'(480p|720p|1080p|2160p|4k)', filename, re.I)
    res = res_match.group(0).upper() if res_match else "HD"
    year_match = re.search(r'(19|20)\d{2}', filename)
    year = year_match.group(0) if year_match else ""
    clean = re.sub(r'(480p|720p|1080p|2160p|4k|19\d{2}|20\d{2})', '', filename, flags=re.I)
    clean = re.sub(r'[@\[\].\-_]', ' ', clean).strip().title()
    clean = re.sub(r'\s+', ' ', clean)
    # Format: Resolution / Movie Name Year
    return f"{res} / {clean} {year}".strip()

async def auto_delete(client, chat_id, message_ids):
    await asyncio.sleep(120)
    try: await client.delete_messages(chat_id, message_ids)
    except: pass

# --- WEB SERVER ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "RDX Ultra Final Pro is Live! 🚀"

app = Client("RDX_V9", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    if len(message.command) > 1 and message.command[1].startswith("file_"):
        doc_id = message.command[1].split("_")[1]
        doc = await db.files.find_one({"_id": ObjectId(doc_id)})
        if doc:
            sent_file = await client.send_cached_media(
                chat_id=message.from_user.id,
                file_id=doc['file_id'],
                caption=doc['caption']
            )
            warn_msg = await message.reply_text(DELETE_WARNING)
            asyncio.create_task(auto_delete(client, message.from_user.id, [sent_file.id, warn_msg.id]))
            return
    await message.reply_text(f"👋 **Hello {message.from_user.mention}!**\nSearch movies in group. If you make spelling mistakes, I will still find them!")

@app.on_message(filters.command("stats"))
async def stats_handler(client, message):
    if not await db.is_admin(message.from_user.id): return
    count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Total Indexed Files:** `{count}`")

# --- SMART INDEX COMMAND ---
@app.on_message(filters.command("index"))
async def index_handler(client, message):
    if not await db.is_admin(message.from_user.id): return
    
    target = CHANNEL_ID if len(message.command) < 2 else message.command[1]
    
    m = await message.reply(f"🔄 **Scanning `{target}`...**\n*(If this fails, forward a file from the channel to me)*")
    count = 0
    try:
        async for user_msg in client.get_chat_history(target):
            file = user_msg.document or user_msg.video
            if file:
                if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size, user_msg.caption):
                    count += 1
        await m.edit(f"✅ Indexed `{count}` files successfully!")
    except Exception as e:
        await m.edit(f"❌ **Indexing Failed!**\n\n**Error:** `{e}`\n\n**Trick:** আপনার মুভি চ্যানেল থেকে যেকোনো ১টি মুভি আমার ইনবক্সে Forward করুন। আমি চ্যাট আইডি চিনে নেব।")

@app.on_message(filters.command("add_admin") & filters.user(OWNER_ID))
async def add_admin_cmd(client, message):
    if len(message.command) < 2: return
    try:
        uid = int(message.command[1])
        await db.add_admin(uid)
        await message.reply(f"✅ User `{uid}` is now an Admin!")
    except: await message.reply("Invalid ID!")

# --- AUTO SAVE & FORWARD TRICK ---
@app.on_message((filters.chat(CHANNEL_ID) | filters.forwarded | filters.private) & (filters.document | filters.video))
async def auto_save_handler(client, message):
    # Admin PM-এ ফরওয়ার্ড করলে সেভ হবে
    if message.chat.type == filters.chat_type.PRIVATE:
        if not await db.is_admin(message.from_user.id): return

    file = message.document or message.video
    f_name = getattr(file, "file_name", "Untitled")
    
    if await db.save_file(file.file_id, f_name, file.file_size, message.caption):
        if message.chat.type == filters.chat_type.PRIVATE:
            # যদি ফরওয়ার্ড করা হয়, তবে একটি বাটন দিবে ফুল চ্যানেল ইনডেক্স করার জন্য
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Index Full Channel", callback_data=f"idx_{message.forward_from_chat.id if message.forward_from_chat else 'none'}")]])
            await message.reply_text(f"✅ **File Indexed!**\n📂 `{f_name}`", reply_markup=btn if message.forward_from_chat else None)

@app.on_callback_query(filters.regex(r"^idx_"))
async def cb_index_full(client, query: CallbackQuery):
    chat_id = query.data.split("_")[1]
    if chat_id == "none": return await query.answer("Forward properly!", show_alert=True)
    
    await query.message.edit_text(f"🔄 **Starting Full Index for `{chat_id}`...**")
    count = 0
    try:
        async for user_msg in client.get_chat_history(int(chat_id)):
            file = user_msg.document or user_msg.video
            if file:
                if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size, user_msg.caption):
                    count += 1
        await query.message.edit_text(f"✅ Indexed `{count}` files from this channel!")
    except Exception as e:
        await query.message.edit_text(f"❌ Failed: {e}")

# --- ADVANCED SEARCH (Fuzzy + Format) ---
@app.on_message(filters.text & ~filters.command(["start", "stats", "index", "add_admin"]))
async def handle_search(client, message):
    query = message.text.lower().strip()
    if len(query) < 2: return
    
    # 1. Regex Multi-keyword
    words = query.split()
    regex_pattern = f"^{''.join([f'(?=.*{re.escape(word)})' for word in words])}.*$"
    cursor = db.files.find({
        "$or": [
            {"file_name": {"$regex": regex_pattern, "$options": "i"}},
            {"clean_name": {"$regex": regex_pattern, "$options": "i"}}
        ]
    })
    results = await cursor.to_list(length=10)
    
    # 2. Fuzzy Match (বানান ভুল হলেও)
    if len(results) < 3:
        all_names = await db.get_all_names()
        matches = difflib.get_close_matches(query, all_names, n=5, cutoff=0.4)
        for m in matches:
            doc = await db.files.find_one({"file_name": m})
            if doc and doc not in results: results.append(doc)

    bot_info = await client.get_me()
    if results:
        btns = []
        for f in results:
            label = format_label(f['file_name'])
            f_url = f"https://t.me/{bot_info.username}?start=file_{str(f['_id'])}"
            btns.append([InlineKeyboardButton(label, url=f_url)])
        await message.reply_text(f"🔍 **Results for:** `{query}`", reply_markup=InlineKeyboardMarkup(btns))

# Bootstrap
async def start_bot():
    Thread(target=lambda: Flask(__name__).run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    await app.start()
    logger.info("🚀 RDX FINAL PRO IS ONLINE!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
