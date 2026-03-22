import logging
import os
import asyncio
import re
import difflib
import sys
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

# Apnar ID (Owner)
OWNER_ID = 6783893816
CHANNEL_ID = -1003065768519 

DELETE_WARNING = "⚠️ ❌👉This file automatically❗delete after 2 minute❗so please forward in another chat👈❌"

NO_RESULTS_TEXT = """🄰🅃🅃🄴🄽🅃🄸🄾🄽 🄷🄴🅁🄴
𝐌𝐎𝐕𝐈𝐄/𝐒𝐄𝐑𝐈𝐄𝐒 𝐒𝐄𝐀𝐑𝐂𝐇 𝐑𝐔𝐋𝐄𝐒 🍿

◉ ᴀʟᴡᴀʏꜱ ᴜꜱᴇ ᴄᴏʀʀᴇᴄᴛ ꜱᴘᴇʟʟɪɴɢ. ʏᴏᴜ ᴄᴀɴ ꜰɪɴᴅ ʀɪɢʜᴛ ꜱᴘᴇʟʟɪɴɢ ꜰʀᴏᴍ google.com

◉ ꜱᴇᴀʀᴄʜ ᴍᴏᴠɪᴇꜱ ʟɪᴋᴇ ᴛʜɪꜱ :- 
› ꜱᴀʟᴀᴀʀ 2023 ✔️ 
› ꜱᴀʟᴀᴀʀ ʜɪɴᴅɪ ✔️ 

◉ ꜱᴇᴀʀᴄʜ ꜱᴇʀɪᴇꜱ ʟɪᴋᴇ ᴛʜɪꜱ :- 
› ᴠɪᴋɪɴɢꜱ ✔️ 
› ᴠɪᴋɪɴɢꜱ ꜱ01 ✔️ 
› ᴠɪᴋɪɴɢꜱ ꜱ01ᴇ01 ✔️ """

# --- DATABASE ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["RDX_ULTRA_V4"]
        self.files = self.db["files"]
        self.admins = self.db["admins"]
        self.users = self.db["users"]

    # Admin Management
    async def add_admin(self, user_id):
        await self.admins.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)

    async def remove_admin(self, user_id):
        await self.admins.delete_one({"user_id": user_id})

    async def is_admin(self, user_id):
        if user_id == OWNER_ID: return True
        admin = await self.admins.find_one({"user_id": user_id})
        return True if admin else False

    async def get_admins(self):
        cursor = self.admins.find({})
        return [doc['user_id'] for doc in await cursor.to_list(length=100)]

    # File Management
    async def save_file(self, file_id, file_name, file_size, original_caption):
        clean_name = re.sub(r'[_.\-]', ' ', file_name).lower().strip()
        f_name = file_name.lower().strip()
        if not await self.files.find_one({"file_name": f_name, "file_size": file_size}):
            await self.files.insert_one({
                'file_id': file_id, 
                'file_name': f_name, 
                'clean_name': clean_name, 
                'file_size': file_size,
                'caption': original_caption or f_name.upper()
            })
            return True
        return False

    async def delete_file(self, file_id_obj):
        await self.files.delete_one({"_id": ObjectId(file_id_obj)})

db = Database(MONGO_URI)

# --- HELPERS ---
def extract_info(filename):
    res = re.search(r'(480p|720p|1080p|2160p|4k)', filename, re.I)
    year = re.search(r'(19|20)\d{2}', filename)
    res_str = res.group(0).upper() if res else "HD"
    year_str = year.group(0) if year else ""
    clean = re.sub(r'(480p|720p|1080p|2160p|4k|19\d{2}|20\d{2})', '', filename, flags=re.I)
    clean = re.sub(r'[_.\-]', ' ', clean).strip().title()
    return f"{res_str} / {clean} {year_str}".strip()

async def auto_delete(client, chat_id, message_ids):
    await asyncio.sleep(120)
    try:
        await client.delete_messages(chat_id, message_ids)
    except: pass

# --- WEB SERVER ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "RDX Ultra Admin Mode Active!"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

app = Client("RDX_ULTRA_V4", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- DECORATORS ---
def admin_only(func):
    async def wrapper(client, message):
        if await db.is_admin(message.from_user.id):
            return await func(client, message)
    return wrapper

def owner_only(func):
    async def wrapper(client, message):
        if message.from_user.id == OWNER_ID:
            return await func(client, message)
    return wrapper

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
            asyncio.create_task(auto_delete(client, message.chat.id, [sent_file.id, warn_msg.id]))
            return

    await message.reply_text(f"👋 **Hello {message.from_user.mention}!**\nI am INDRA Pro. Search movies in group.")

# Admin Management Commands (Owner Only)
@app.on_message(filters.command("add_admin") & filters.user(OWNER_ID))
async def add_admin_cmd(client, message):
    if len(message.command) < 2: return
    user_id = int(message.command[1])
    await db.add_admin(user_id)
    await message.reply(f"✅ User `{user_id}` ekhon theke Admin!")

@app.on_message(filters.command("remove_admin") & filters.user(OWNER_ID))
async def rem_admin_cmd(client, message):
    if len(message.command) < 2: return
    user_id = int(message.command[1])
    await db.remove_admin(user_id)
    await message.reply(f"❌ User `{user_id}` ke Admin list theke sorano hoyeche.")

@app.on_message(filters.command("admins") & filters.user(OWNER_ID))
async def list_admins_cmd(client, message):
    admins = await db.get_admins()
    text = "👮 **Admin List:**\n\n" + "\n".join([f"• `{uid}`" for uid in admins])
    await message.reply(text)

# Stats (Admin and Owner)
@app.on_message(filters.command("stats"))
@admin_only
async def stats_handler(client, message):
    count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Total Indexed Files:** `{count}`")

# Index (Admin and Owner)
@app.on_message(filters.command("index"))
@admin_only
async def index_handler(client, message):
    if len(message.command) < 2: return
    target = message.command[1]
    m = await message.reply("🔄 **Scanning & Indexing...**")
    count = 0
    async for user_msg in client.get_chat_history(target):
        file = user_msg.document or user_msg.video
        if file:
            if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size, user_msg.caption):
                count += 1
    await m.edit(f"✅ Indexed `{count}` files successfully!")

# File Management: Delete specific file (Admin and Owner)
@app.on_message(filters.command("delete"))
@admin_only
async def delete_file_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply("Usage: `/delete <File_ID>`")
    doc_id = message.command[1]
    try:
        await db.delete_file(doc_id)
        await message.reply("🗑️ File-ti database theke delete kora hoyeche!")
    except Exception as e:
        await message.reply(f"❌ Error: `{e}`")

# Search Logic
@app.on_message(filters.text & ~filters.command(["start", "stats", "index", "delete", "add_admin", "remove_admin", "admins"]))
async def handle_search(client, message):
    query = message.text.lower().strip()
    if len(query) < 2: return
    
    words = query.split()
    regex_pattern = f"^{''.join([f'(?=.*{re.escape(word)})' for word in words])}.*$"
    cursor = db.files.find({
        "$or": [
            {"file_name": {"$regex": regex_pattern, "$options": "i"}},
            {"clean_name": {"$regex": regex_pattern, "$options": "i"}}
        ]
    })
    results = await cursor.to_list(length=10)
    
    bot_info = await client.get_me()

    if results:
        btns = []
        for f in results:
            label = extract_info(f['file_name'])
            # Owner-er jonno delete ID show kora (Optionally)
            f_url = f"https://t.me/{bot_info.username}?start=file_{str(f['_id'])}"
            btns.append([InlineKeyboardButton(label, url=f_url)])
            
        # Admin hole File ID dekhar subidha (যাতে পরে ডিলিট করা যায়)
        resp_text = f"🔍 **Results for:** <code>{query}</code>"
        if await db.is_admin(message.from_user.id):
            resp_text += "\n\n*(Admins can use /delete <ID> to remove file)*"
            for f in results:
                resp_text += f"\n• `{str(f['_id'])}`"

        await message.reply_text(resp_text, reply_markup=InlineKeyboardMarkup(btns))
    else:
        await message.reply_text(NO_RESULTS_TEXT)

# Bootstrap
async def start_rdx():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("🚀 RDX ULTRA V4 IS ONLINE!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_rdx())
