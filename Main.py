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

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

ADMIN_ID = 6783893816
CHANNEL_ID = -1003065768519 # Movie Source Channel

# Default Caption Format
CAPTION_TEXT = "<b>📂 File Name:</b> <code>{file_name}</code>\n<b>📦 Size:</b> <code>{file_size}</code>\n\n<b>⚜️ Powered By: [INDRA]</b>"

# --- DATABASE HANDLER ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["INDRA_MASTER_PRO_DB"]
        self.files = self.db["files"]
        self.users = self.db["users"]

    async def save_file(self, file_id, file_name, file_size):
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

# --- WEB SERVER (Render) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "INDRA Redirect Bot is Live! 🚀"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

app = Client("RDX_ULTRA", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- SEARCH HELPER ---
def build_regex(query):
    words = query.split()
    pattern = "".join([f"(?=.*{re.escape(word)})" for word in words])
    return f"^{pattern}.*$"

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    # PM-e link-er maddhome ashle (Deep Linking)
    if len(message.command) > 1:
        data = message.command[1]
        if data.startswith("file_"):
            doc_id = data.split("_")[1]
            try:
                doc = await db.files.find_one({"_id": ObjectId(doc_id)})
                if doc:
                    size = round(doc['file_size'] / (1024 * 1024), 2)
                    caption = CAPTION_TEXT.format(
                        file_name=doc['file_name'].upper(),
                        file_size=f"{size} MB"
                    )
                    # File ebong Caption eksathe pathano hochche
                    await client.send_cached_media(
                        chat_id=message.from_user.id,
                        file_id=doc['file_id'],
                        caption=caption
                    )
                    return
                else:
                    await message.reply("😔 File not found in database!")
                    return
            except Exception as e:
                logger.error(f"Error sending file: {e}")
                return

    # Normal Start Message
    text = "<b>🚩 JAI SRI KRISHNA 🚩</b>\n\n👋 <b>Hello {mention}!</b>\nAmi INDRA Master Filter Bot. Movie khunjte group-e nam likhun."
    await message.reply_text(text.format(mention=message.from_user.mention))

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message):
    f_count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Total Indexed Files:** `{f_count}`")

@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def index_handler(client, message):
    if len(message.command) < 2: return
    target = message.command[1]
    m = await message.reply("🔄 **Scanning...**")
    count = 0
    try:
        async for user_msg in client.get_chat_history(target):
            file = user_msg.document or user_msg.video
            if file:
                if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size):
                    count += 1
        await m.edit(f"✅ Indexed `{count}` files successfully!")
    except Exception as e:
        await m.edit(f"❌ Error: `{e}`")

# --- GROUP SEARCH LOGIC (Redirect to PM) ---
@app.on_message(filters.text & ~filters.command(["start", "stats", "index", "id"]))
async def handle_search(client, message):
    query = message.text.lower().strip()
    if len(query) < 3: return
    
    regex_pattern = build_regex(query)
    cursor = db.files.find({
        "$or": [
            {"file_name": {"$regex": regex_pattern, "$options": "i"}},
            {"clean_name": {"$regex": regex_pattern, "$options": "i"}}
        ]
    })
    results = await cursor.to_list(length=10)
    
    me = await client.get_me() # Bot username pawar jonno

    if results:
        btns = []
        for f in results:
            size = round(f['file_size'] / (1024 * 1024), 2)
            # URL Button to redirect to PM with file ID
            f_url = f"https://t.me/{me.username}?start=file_{str(f['_id'])}"
            btns.append([InlineKeyboardButton(f"📂 {f['file_name'].title()} ({size}MB)", url=f_url)])
        
        await message.reply_text(
            f"🔍 **Found {len(results)} results for:** <code>{query}</code>\n\nClick below buttons to get file in PM 👇",
            reply_markup=InlineKeyboardMarkup(btns)
        )
    else:
        # Spelling Suggestion Logic
        all_names = await db.get_all_names()
        matches = difflib.get_close_matches(query, all_names, n=3, cutoff=0.5)
        if matches:
            m_btns = []
            for m in matches:
                doc = await db.files.find_one({"file_name": m})
                if doc:
                    f_url = f"https://t.me/{me.username}?start=file_{str(doc['_id'])}"
                    m_btns.append([InlineKeyboardButton(f"🔎 Did you mean: {m[:30]}...", url=f_url)])
            await message.reply_text("<b>Spelling Mistake Bro ‼️</b>\nChoose the correct one to get file in PM 👇", reply_markup=InlineKeyboardMarkup(m_btns))

# --- AUTO SAVE ---
@app.on_message((filters.chat(CHANNEL_ID) | filters.forwarded) & (filters.document | filters.video))
async def auto_save(client, message):
    file = message.document or message.video
    if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size):
        logger.info("New file auto-indexed!")

# --- BOOTSTRAP ---
async def start_rdx():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("🚀 INDRA REDIRECT BOT IS ONLINE!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_rdx())
