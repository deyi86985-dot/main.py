import logging
import os
import asyncio
import re
import difflib
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
from flask import Flask
from threading import Thread
from spellchecker import SpellChecker
from imdb import Cinemagoer

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

OWNER_ID = 6783893816 
CHANNEL_ID = -1003065768519 

# Tools
spell = SpellChecker()
ia = Cinemagoer()

DELETE_WARNING = "⚠️ ❌👉 This file automatically delete after 2 minutes so please forward in another chat 👈❌"

# --- DATABASE HANDLER ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["CINESOCIETY_ULTRA_V1"]
        self.files = self.db["files"]
        self.admins = self.db["admins"]

    async def is_admin(self, user_id):
        if user_id == OWNER_ID: return True
        admin = await self.admins.find_one({"user_id": user_id})
        return admin is not None

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

    async def total_files(self):
        return await self.files.count_documents({})

db = Database(MONGO_URI)

# --- WEB SERVER ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "Bot is Alive! 🚀"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

app = Client("RDX_MASTER_PRO", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- HELPERS ---

def format_btn(filename):
    """বাটন থেকে @username এবং [text] রিমুভ করার ফাংশন"""
    # ১. @ দিয়ে শুরু হওয়া যেকোনো ইউজারনেম রিমুভ করবে (যেমন: @cinesociety02)
    clean = re.sub(r'@\w+', '', filename)
    # ২. থার্ড ব্র্যাকেট এবং তার ভেতরের লেখা রিমুভ করবে (যেমন: [Dual Audio])
    clean = re.sub(r'\[.*?\]', '', clean)
    
    # রেজোলিউশন বের করা
    res_match = re.search(r'(480p|720p|1080p|2160p|4k)', filename, re.I)
    res = res_match.group(0).upper() if res_match else "HD"
    
    # সাল বের করা
    year_match = re.search(r'(19|20)\d{2}', filename)
    year = year_match.group(0) if year_match else ""
    
    # বাকি আজেবাজে চিহ্ন পরিষ্কার করা
    clean = re.sub(r'(480p|720p|1080p|2160p|4k|19\d{2}|20\d{2})', '', clean, flags=re.I)
    clean = re.sub(r'[_.\-]', ' ', clean).strip().title()
    
    # ফাইনাল টেক্সট (বেশি লম্বা হলে কেটে ছোট করবে)
    final_text = f"🎬 {res} / {clean} {year}".strip()
    return final_text[:45] + "..." if len(final_text) > 48 else final_text

def check_spelling(text):
    words = text.split()
    corrected = [spell.correction(w) if w.isalpha() and spell.correction(w) else w for w in words]
    return " ".join(corrected)

async def get_imdb_data(query):
    try:
        search = ia.search_movie(query)
        if search:
            m = ia.get_movie(search[0].movieID)
            return {
                'title': m.get('title', 'N/A'),
                'year': m.get('year', 'N/A'),
                'rating': m.get('rating', 'N/A'),
                'genres': ", ".join(m.get('genres', [])),
                'poster': m.get('full-size cover url'),
            }
    except Exception as e:
        logger.error(f"IMDb Error: {e}")
        return None

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
            sent_file = await client.send_cached_media(chat_id=message.chat.id, file_id=doc['file_id'], caption=doc['caption'])
            warn = await message.reply(DELETE_WARNING)
            asyncio.create_task(auto_delete(client, message.chat.id, [sent_file.id, warn.id]))
            return
    await message.reply_text(f"👋 **Hello {message.from_user.mention}!**\nSearch movies here.\n\n**Edit by INDRA**")

@app.on_message(filters.command("stats"))
async def stats_handler(client, message):
    if not await db.is_admin(message.from_user.id):
        return
    count = await db.total_files()
    await message.reply_text(f"📊 **Total Indexed Files:** `{count}`\n\n**Edit by INDRA**")

@app.on_message(filters.command("index"))
async def index_cmd(client, message):
    if not await db.is_admin(message.from_user.id): return
    target = CHANNEL_ID if len(message.command) < 2 else message.command[1]
    m = await message.reply("🔄 **Indexing...**")
    count = 0
    async for user_msg in client.get_chat_history(target):
        file = user_msg.document or user_msg.video
        if file:
            if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size, user_msg.caption):
                count += 1
    await m.edit(f"✅ Indexed `{count}` files!")

@app.on_message(filters.text & ~filters.command(["start", "stats", "index"]))
async def search_handler(client, message):
    orig_query = message.text.lower().strip()
    if len(orig_query) < 2: return
    
    query = check_spelling(orig_query)
    words = query.split()
    regex = f"^{''.join([f'(?=.*{re.escape(word)})' for word in words])}.*$"
    
    cursor = db.files.find({"$or": [{"file_name": {"$regex": regex, "$options": "i"}}, {"clean_name": {"$regex": regex, "$options": "i"}}]})
    results = await cursor.to_list(length=10)
    
    if not results:
        all_names = await db.get_all_names()
        matches = difflib.get_close_matches(query, all_names, n=5, cutoff=0.4)
        for m_name in matches:
            doc = await db.files.find_one({"file_name": m_name})
            if doc and doc not in results: results.append(doc)

    if results:
        imdb = await get_imdb_data(query)
        bot = await client.get_me()
        # এখানে format_btn ফাংশনটি ব্যবহার করা হয়েছে বাটন ক্লিন করার জন্য
        btns = [[InlineKeyboardButton(format_btn(f['file_name']), url=f"https://t.me/{bot.username}?start=file_{f['_id']}")] for f in results]
        
        caption = f"🎬 **Name:** `{imdb['title'] if imdb else query.title()}`\n"
        if imdb:
            caption += f"🌟 **Rating:** `{imdb['rating']}/10` | 📅 **Year:** `{imdb['year']}`\n🎭 **Genre:** `{imdb['genres']}`\n\n"
        
        caption += "**Edit by INDRA**"

        if imdb and imdb['poster']:
            await message.reply_photo(photo=imdb['poster'], caption=caption, reply_markup=InlineKeyboardMarkup(btns))
        else:
            await message.reply_text(caption, reply_markup=InlineKeyboardMarkup(btns))
    else:
        await message.reply_text("❌ No results found. Check spelling!\n\n**Edit by INDRA**")

# --- BOOTSTRAP ---
async def start_bot():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("🚀 Bot is live with Clean Buttons!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
