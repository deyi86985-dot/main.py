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
CHANNEL_ID = -1003065768519 

DELETE_WARNING = "⚠️ ❌👉This file automatically❗delete after 2 minute❗so please forward in another chat👈❌"

SEARCH_RULES = """🄰🅃🅃🄴🄽🅃🄸🄾🄽 🄷🄴🅁🄴
𝐌𝐎𝐕𝐈𝐄/𝐒𝐄𝐑𝐈𝐄𝐒 𝐒𝐄𝐀𝐑𝐂𝐇 𝐑𝐔𝐋𝐄𝐒 🍿

◉ ᴀʟᴡᴀʏꜱ ᴜꜱᴇ ᴄᴏʀʀᴇᴄᴛ ꜱᴘᴇʟʟɪɴɢ. ʏᴏᴜ ᴄᴀɴ ꜰɪɴᴅ ʀɪɢʜᴛ ꜱᴘᴇʟʟɪɴɢ ꜰʀᴏᴍ google.com

◉ ꜱᴇᴀʀᴄʜ ᴍᴏᴠɪᴇꜱ ʟɪᴋᴇ ᴛʜɪꜱ :- 
› ꜱᴀʟᴀᴀʀ 2023 ✔️ 
› ꜱᴀʟᴀᴀʀ ʜɪɴᴅɪ ✔️ 

◉ ꜱᴇᴀʀᴄʜ ꜱᴇʀɪᴇꜱ ʟɪᴋᴇ ᴛʜɪꜱ :- 
› ᴠɪᴋɪɴɢꜱ ✔️ 
› ᴠɪᴋɪɴɢꜱ ꜱ01 ✔️ 

◉ ᴅᴏɴᴛ ʀᴇ𝚀ᴜᴇꜱᴛ ᴀɴʏᴛʜɪɴɢ ᴏᴛʜᴇʀ ᴛʜᴀɴ ᴍᴏᴠɪᴇ , ꜱᴇʀɪᴇ𝒔 , ᴀɴɪᴍᴇ."""

# --- DATABASE ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["INDRA_ULTRA_V5_MASTER"]
        self.files = self.db["files"]
        self.admins = self.db["admins"]

    async def add_admin(self, user_id):
        await self.admins.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)

    async def is_admin(self, user_id):
        if user_id == OWNER_ID: return True
        admin = await self.admins.find_one({"user_id": user_id})
        return True if admin else False

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

db = Database(MONGO_URI)

# --- WEB SERVER ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "INDRA Ultra PM-Index Server is Online! 🚀"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

app = Client("INDRA_FINAL_PRO", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- HELPERS ---
def format_button_label(filename):
    res = re.search(r'(480p|720p|1080p|2160p|4k)', filename, re.I)
    year = re.search(r'(19|20)\d{2}', filename)
    res_str = res.group(0).upper() if res else "HD"
    year_str = year.group(0) if year else ""
    clean = re.sub(r'(480p|720p|1080p|2160p|4k|19\d{2}|20\d{2})', '', filename, flags=re.I)
    clean = re.sub(r'[_.\-]', ' ', clean).strip().title()
    return f"{res_str} / {clean} {year_str}".strip()

async def auto_delete(client, chat_id, message_ids):
    await asyncio.sleep(120)
    try: await client.delete_messages(chat_id, message_ids)
    except: pass

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
    await message.reply_text(f"👋 **Hello {message.from_user.mention}!**\n.𝒊 𝑨𝒎 𝑻𝒉𝒆 𝑴𝒐𝒔𝒕 𝑷𝒐𝒘𝒆𝒓𝒇𝒖𝒍 𝑨𝒖𝒕𝒐 𝑭𝒊𝒍𝒕𝒆𝒓 𝑩𝒐𝒕 𝑾𝒊𝒕𝒉 𝑷𝒓𝒆𝒎𝒊𝒖𝒎 𝑭𝒆𝒂𝒕𝒖𝒓𝒆.")

@app.on_message(filters.command("stats"))
async def stats_handler(client, message):
    if not await db.is_admin(message.from_user.id): return
    count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Total Indexed Files:** `{count}`")

@app.on_message(filters.command("index"))
async def index_handler(client, message):
    if not await db.is_admin(message.from_user.id): return
    target = CHANNEL_ID if len(message.command) < 2 else message.command[1]
    m = await message.reply("🔄 **Scanning Channel & Captions...**")
    count = 0
    try:
        async for user_msg in client.get_chat_history(target):
            file = user_msg.document or user_msg.video
            if file:
                if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size, user_msg.caption):
                    count += 1
        await m.edit(f"✅ Indexed `{count}` files with original captions!")
    except Exception as e:
        await m.edit(f"❌ Error: `{e}`")

@app.on_message(filters.command("add_admin") & filters.user(OWNER_ID))
async def add_admin_cmd(client, message):
    if len(message.command) < 2: return
    try:
        uid = int(message.command[1])
        await db.add_admin(uid)
        await message.reply(f"✅ User `{uid}` is now Admin!")
    except: await message.reply("Invalid ID!")

# --- AUTO SAVE & PM AUTO INDEX ---
@app.on_message((filters.chat(CHANNEL_ID) | filters.forwarded | filters.private) & (filters.document | filters.video))
async def auto_save_handler(client, message):
    # Check if the sender is Admin/Owner for PM indexing
    if message.chat.type == filters.chat_type.PRIVATE:
        if not await db.is_admin(message.from_user.id):
            return # User-er PM file index hobe na

    file = message.document or message.video
    f_name = getattr(file, "file_name", "Untitled")
    f_caption = message.caption or f_name.upper()

    if await db.save_file(file.file_id, f_name, file.file_size, f_caption):
        # Jodi PM-e Admin file pathai, tobe reply dibe
        if message.chat.type == filters.chat_type.PRIVATE:
            await message.reply_text(f"✅ **File Auto-Indexed!**\n\n📂 **Name:** `{f_name}`\n📦 **Size:** `{round(file.file_size/(1024*1024), 2)} MB`")
        else:
            logger.info(f"New file indexed from Channel: {f_name}")

# Search Logic
@app.on_message(filters.text & ~filters.command(["start", "stats", "index", "add_admin"]))
async def search_handler(client, message):
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
            label = format_button_label(f['file_name'])
            f_url = f"https://t.me/{bot_info.username}?start=file_{str(f['_id'])}"
            btns.append([InlineKeyboardButton(label, url=f_url)])
        
        resp = f"🔍 **Results for:** ` {query} `\n\n*(Check your Inbox for files)*"
        if await db.is_admin(message.from_user.id):
            for f in results: resp += f"\n• `{str(f['_id'])}`"
            
        await message.reply_text(resp, reply_markup=InlineKeyboardMarkup(btns))
    else:
        await message.reply_text(SEARCH_RULES)

# Bootstrap
async def start_bot():
    Thread(target=lambda: Flask(__name__).run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080))), daemon=True).start()
    await app.start()
    logger.info("🚀 RDX MASTER IS ONLINE!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
