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

# --- CONFIGURATION (Fixed for your details) ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

ADMIN_ID = 6783893816
CHANNEL_ID = -1003065768519 # আপনার মুভি চ্যানেল আইডি

# --- DATABASE HANDLER ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        # ডাটাবেস এবং কালেকশন নেম ফিক্সড রাখা হলো যাতে ডাটা হারিয়ে না যায়
        self.db = self._client["RDX_MASTER_PRO_DB"]
        self.files = self.db["files"]
        self.users = self.db["users"]

    async def save_file(self, file_id, file_name, file_size):
        # নাম ক্লিন করা হচ্ছে সার্চ সহজ করার জন্য
        clean_name = re.sub(r'[_.\-]', ' ', file_name).lower().strip()
        f_name = file_name.lower().strip()
        if not await self.files.find_one({"file_name": f_name, "file_size": file_size}):
            await self.files.insert_one({
                'file_id': file_id, 
                'file_name': f_name, 
                'clean_name': clean_name, 
                'file_size': file_size
            })
            return True
        return False

    async def get_all_names(self):
        cursor = self.files.find({}, {"file_name": 1})
        return [doc['file_name'] for doc in await cursor.to_list(length=5000)]

db = Database(MONGO_URI)

# --- WEB SERVER (Render Uptime) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "RDX Pro Master is Live! 🚀"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

app = Client("RDX_ULTRA", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- SEARCH LOGIC (Ultra Flexible) ---
def build_regex(query):
    # 'Avatar Water' লিখলে যেন 'Avatar.The.Way.Of.Water' খুঁজে পায়
    words = query.split()
    pattern = "".join([f"(?=.*{re.escape(word)})" for word in words])
    return f"^{pattern}.*$"

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    await db.users.update_one({"user_id": message.from_user.id}, {"$set": {"user_id": message.from_user.id}}, upsert=True)
    text = f"<b>🚩 জয় শ্রী রাম 🚩</b>\n\n👋 <b>Hello {message.from_user.mention}!</b>\nSearch movies by name here or in group."
    btns = [[InlineKeyboardButton("➕ Add Me to Your Group ➕", url=f"http://t.me/{client.me.username}?startgroup=true")]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns))

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message):
    f_count = await db.files.count_documents({})
    u_count = await db.users.count_documents({})
    await message.reply_text(f"📊 <b>Database Stats:</b>\n\n📂 Total Files: <code>{f_count}</code>\n👤 Total Users: <code>{u_count}</code>")

@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def index_handler(client, message):
    if len(message.command) < 2: return await message.reply("Usage: <code>/index @channel</code>")
    target = message.command[1]
    m = await message.reply("🔄 <b>Scanning Channel...</b>")
    count = 0
    try:
        async for user_msg in client.get_chat_history(target):
            file = user_msg.document or user_msg.video
            if file:
                if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size):
                    count += 1
        await m.edit(f"✅ <b>Success!</b> Added <code>{count}</code> files to DB.")
    except Exception as e:
        await m.edit(f"❌ <b>Error:</b> <code>{e}</code>")

# --- CORE SEARCH ---
@app.on_message(filters.text & ~filters.command(["start", "stats", "index", "id"]))
async def handle_search(client, message):
    query = message.text.lower().strip()
    if len(query) < 3: return
    
    logger.info(f"Searching: {query}")
    regex_pattern = build_regex(query)
    
    # সার্চ করা হচ্ছে অরিজিনাল নাম এবং ক্লিন করা নাম—উভয় জায়গাতে
    cursor = db.files.find({
        "$or": [
            {"file_name": {"$regex": regex_pattern, "$options": "i"}},
            {"clean_name": {"$regex": regex_pattern, "$options": "i"}}
        ]
    })
    results = await cursor.to_list(length=10)
    
    if results:
        btns = []
        for f in results:
            size = round(f['file_size'] / (1024 * 1024), 2)
            btns.append([InlineKeyboardButton(f"📂 {f['file_name'].title()} ({size}MB)", callback_data=f"get_{str(f['_id'])}")])
        await message.reply_text(f"🔍 <b>Found results for:</b> <code>{query}</code>", reply_markup=InlineKeyboardMarkup(btns))
    else:
        # Spelling Suggestion
        all_names = await db.get_all_names()
        matches = difflib.get_close_matches(query, all_names, n=3, cutoff=0.5)
        if matches:
            m_btns = []
            for m in matches:
                doc = await db.files.find_one({"file_name": m})
                if doc: m_btns.append([InlineKeyboardButton(f"🔎 Did you mean: {m[:30]}...", callback_data=f"sp_{str(doc['_id'])}")])
            await message.reply_text("<b>Spelling Mistake Bro ‼️</b>\nChoose the correct one below 👇", reply_markup=InlineKeyboardMarkup(m_btns))
        elif message.chat.type == filters.chat_type.PRIVATE:
            await message.reply_text("<b>I couldn't find any movie related to this.</b>\nTry checking the spelling or year.")

# --- CALLBACKS (Fixed 64-byte Error) ---
@app.on_callback_query(filters.regex(r"^get_"))
async def cb_send_file(client, query: CallbackQuery):
    doc_id = query.data.split("_")[1]
    doc = await db.files.find_one({"_id": ObjectId(doc_id)})
    if doc:
        try:
            await client.send_cached_media(chat_id=query.from_user.id, file_id=doc['file_id'])
            await query.answer("Check your Inbox! File sent.", show_alert=True)
        except:
            await query.answer("Please START the bot in private first!", show_alert=True)

@app.on_callback_query(filters.regex(r"^sp_"))
async def cb_suggest(client, query: CallbackQuery):
    doc_id = query.data.split("_")[1]
    doc = await db.files.find_one({"_id": ObjectId(doc_id)})
    if doc:
        # সাজেশন ক্লিক করলে সেই ফাইলটি সরাসরি দিয়ে দিবে
        btns = [[InlineKeyboardButton(f"📂 {doc['file_name'].title()}", callback_data=f"get_{str(doc['_id'])}")]]
        await query.message.edit_text(f"🔍 <b>Results for suggested keyword:</b>", reply_markup=InlineKeyboardMarkup(btns))

# --- AUTO SAVE (When you forward files to bot) ---
@app.on_message((filters.chat(CHANNEL_ID) | filters.forwarded) & (filters.document | filters.video))
async def auto_save(client, message):
    file = message.document or message.video
    if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size):
        logger.info("New movie auto-saved to DB!")

# --- BOOTSTRAP ---
async def start_rdx():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("🚀 RDX MASTER IS ONLINE!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_rdx())
