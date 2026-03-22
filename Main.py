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
from spellchecker import SpellChecker  # নতুন যুক্ত করা হয়েছে

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

OWNER_ID = 6783893816 

# স্পেল চেকার ইনিশিয়ালাইজেশন
spell = SpellChecker()

DELETE_WARNING = "⚠️ ❌👉This file automatically❗delete after 2 minute❗so please forward in another chat👈❌"

RULES_MSG = """🄰🅃🅃🄴🄽🅃🄸🄾🄽 🄷🄴🅁🄴
𝐌𝐎𝐕𝐈𝐄/𝐒𝐄𝐑𝐈𝐄𝐒 𝐒𝐄𝐀𝐑𝐂𝐇 𝐑𝐔𝐋𝐄𝐒 🍿

◉ ᴀʟᴡᴀʏꜱ ᴜꜱᴇ ᴄᴏʀʀᴇᴄᴛ ꜱᴘᴇʟʟɪɴɢ.
◉ ꜱᴇᴀʀᴄʜ ᴍᴏᴠɪᴇꜱ ʟɪᴋᴇ ᴛʜɪꜱ :- ꜱᴀʟᴀᴀʀ 2023 ✔️
◉ ꜱᴇᴀʀᴄʜ ꜱᴇʀɪᴇꜱ ʟɪᴋᴇ ᴛʜɪꜱ :- ᴠɪᴋɪɴɢꜱ ꜱ01 ✔️"""

# --- DATABASE HANDLER ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["CINESOCIETY_ULTRA_V1"]
        self.files = self.db["files"]
        self.admins = self.db["admins"]

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

# --- WEB SERVER ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "RDX Ultra Pro is Running! 🚀"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

app = Client("RDX_MASTER_PRO", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- HELPERS ---
def check_spelling(text):
    """ভুল বানান ঠিক করার ফাংশন"""
    words = text.split()
    corrected_words = []
    for word in words:
        # মুভির নামের ক্ষেত্রে অনেক সময় সংখ্যা বা স্পেশাল ক্যারেক্টার থাকে, সেগুলো বাদ দিয়ে চেক করবে
        if word.isalpha():
            cor = spell.correction(word)
            corrected_words.append(cor if cor else word)
        else:
            corrected_words.append(word)
    return " ".join(corrected_words)

def format_btn(filename):
    res_match = re.search(r'(480p|720p|1080p|2160p|4k)', filename, re.I)
    res = res_match.group(0).upper() if res_match else "HD"
    year_match = re.search(r'(19|20)\d{2}', filename)
    year = year_match.group(0) if year_match else ""
    clean = re.sub(r'(480p|720p|1080p|2160p|4k|19\d{2}|20\d{2})', '', filename, flags=re.I)
    clean = re.sub(r'[_.\-]', ' ', clean).strip().title()
    return f"{res} / {clean} {year}".strip()

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
    await message.reply_text(f"👋 **Hello {message.from_user.mention}!**\nI am CINESOCIETY Pro Filter Bot.")

@app.on_message(filters.command("stats"))
async def stats_handler(client, message):
    if not await db.is_admin(message.from_user.id): return
    count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Total Indexed Files:** `{count}`")

@app.on_message(filters.command("index"))
async def index_cmd(client, message):
    if not await db.is_admin(message.from_user.id): return
    target = CHANNEL_ID if len(message.command) < 2 else message.command[1]
    m = await message.reply("🔄 **Indexing...**")
    count = 0
    try:
        async for user_msg in client.get_chat_history(target):
            file = user_msg.document or user_msg.video
            if file:
                if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size, user_msg.caption):
                    count += 1
        await m.edit(f"✅ Indexed `{count}` files!")
    except Exception as e:
        await m.edit(f"❌ Error: `{e}`")

# --- SEARCH LOGIC WITH SPELL CHECK ---
@app.on_message(filters.text & ~filters.command(["start", "stats", "index", "add_admin"]))
async def search_handler(client, message):
    original_query = message.text.lower().strip()
    if len(original_query) < 2: return
    
    # বানান চেক করে নতুন কুয়েরি তৈরি করা
    query = check_spelling(original_query)
    
    words = query.split()
    regex_pattern = f"^{''.join([f'(?=.*{re.escape(word)})' for word in words])}.*$"
    
    cursor = db.files.find({
        "$or": [
            {"file_name": {"$regex": regex_pattern, "$options": "i"}},
            {"clean_name": {"$regex": regex_pattern, "$options": "i"}}
        ]
    })
    results = await cursor.to_list(length=10)
    
    # বানান ঠিক করার পরেও রেজাল্ট না পেলে ডিফলিব ব্যবহার করা
    if not results:
        all_names = await db.get_all_names()
        matches = difflib.get_close_matches(query, all_names, n=5, cutoff=0.4)
        for m in matches:
            doc = await db.files.find_one({"file_name": m})
            if doc and doc not in results:
                results.append(doc)

    bot = await client.get_me()
    if results:
        btns = []
        for f in results:
            label = format_btn(f['file_name'])
            f_url = f"https://t.me/{bot.username}?start=file_{str(f['_id'])}"
            btns.append([InlineKeyboardButton(label, url=f_url)])
        
        # যদি বানান সংশোধন করা হয়, তবে ইউজারকে জানানো
        search_text = f"🔍 **Results for:** `{query}`"
        if query != original_query:
            search_text = f"🔎 **Showing results for:** `{query}`\n_(Corrected from '{original_query}')_"
            
        await message.reply_text(search_text, reply_markup=InlineKeyboardMarkup(btns))
    else:
        await message.reply_text(RULES_MSG)

@app.on_message(filters.private & (filters.document | filters.video))
async def auto_save(client, message):
    if not await db.is_admin(message.from_user.id): return
    file = message.document or message.video
    file_name = getattr(file, "file_name", "Untitled")
    if await db.save_file(file.file_id, file_name, file.file_size, message.caption):
        await message.reply_text(f"✅ Indexed: `{file_name}`")
    else:
        await message.reply_text(f"⚠️ Already exists!")

async def start_bot():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("🚀 CINESOCIETY MASTER IS LIVE!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
