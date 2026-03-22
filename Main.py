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

ADMIN_ID = 6783893816
CHANNEL_ID = -1003065768519 

# Custom Caption and Messages
CAPTION_TEMPLATE = """{file_name}"""

DELETE_WARNING = "⚠️ ❌👉This file automatically❗delete after 2 minute❗so please forward in another chat👈❌"

NO_RESULTS_TEXT = """🄰🅃🅃🄴🄽🅃🄸🄾🄽 🄷🄴🅁🄴
𝐌𝐎𝐕𝐈𝐄/𝐒𝐄𝐑𝐈𝐄𝐒 𝐒𝐄𝐀𝐑𝐂𝐇 𝐑𝐔𝐋𝐄𝐒 🍿

◉ ᴀʟᴡᴀʏꜱ ᴜꜱᴇ ᴄᴏʀʀᴇᴄᴛ ꜱᴘᴇʟʟɪɴɢ. ʏᴏᴜ ᴄᴀɴ ꜰɪɴᴅ ʀɪɢʜᴛ ꜱᴘᴇʟʟɪɴɢ ꜰʀᴏᴍ google.com

◉ ꜱᴇᴀʀᴄʜ ᴍᴏᴠɪᴇꜱ ʟɪᴋᴇ ᴛʜɪꜱ :- 
› ꜱᴀʟᴀᴀʀ 2023 ✔️ 
› ꜱᴀʟᴀᴀʀ ʜɪɴᴅɪ ✔️ 
› ꜱᴀʟᴀᴀʀ ᴍᴏᴠɪᴇ ❌ 
› ꜱᴀʟᴀᴀʀ ꜱᴏᴜᴛʜ ᴍᴏᴠɪᴇ ❌ 
› ꜱᴀʟᴀᴀʀ ʜɪɴᴅɪ ᴅᴜʙʙᴇᴅ ❌  

◉ ꜱᴇᴀʀᴄʜ ꜱᴇʀɪᴇꜱ ʟɪᴋᴇ ᴛʜɪꜱ :- 
› ᴠɪᴋɪɴɢꜱ ✔️ 
› ᴠɪᴋɪɴɢꜱ ꜱ01 ✔️ 
› ᴠɪᴋɪɴɢꜱ ꜱ01ᴇ01 ✔️ 
› ᴠɪᴋɪɴɢꜱ ꜱ01 ᴇ01 ✔️ 
› ᴠɪᴋɪɴɢꜱ ꜱ01 ʜɪɴᴅɪ ✔️
› ᴠɪᴋɪɴɢꜱ ꜱᴇᴀꜱᴏɴ 1 ❌  
› ᴠɪᴋɪɴɢꜱ ᴇᴘɪsᴏᴅᴇ 1 ❌  
› ᴠɪᴋɪɴɢꜱ ᴡᴇʙ ꜱᴇʀɪᴇꜱ ❌   
› ᴠɪᴋɪɴɢꜱ ꜱ01ᴇ01 ʜɪɴᴅɪ ❌ 
› ᴠɪᴋɪɴɢꜱ ꜱ01 ʜɪɴᴅɪ ᴅᴜʙʙᴇᴅ ❌ 

◉ ᴅᴏɴᴛ ʀᴇ𝚀ᴜᴇꜱᴛ ᴀɴʏᴛʜɪɴɢ ᴏᴛʜᴇʀ ᴛʜᴀɴ ᴍᴏᴠɪᴇ , ꜱᴇʀɪᴇꜱ , ᴀɴɪᴍᴇ."""

# --- DATABASE ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["RDX_MASTER_PRO_DB"]
        self.files = self.db["files"]

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

# --- WEB SERVER ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "RDX Auto-Delete Bot is Active!"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

app = Client("RDX_ULTRA", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- HELPERS ---
def build_regex(query):
    words = query.split()
    pattern = "".join([f"(?=.*{re.escape(word)})" for word in words])
    return f"^{pattern}.*$"

async def auto_delete(client, chat_id, message_ids):
    """Wait 2 minutes then delete specified messages"""
    await asyncio.sleep(120)
    try:
        await client.delete_messages(chat_id, message_ids)
        logger.info(f"Auto-deleted messages in {chat_id}")
    except Exception as e:
        logger.error(f"Auto-delete failed: {e}")

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    if len(message.command) > 1 and message.command[1].startswith("file_"):
        doc_id = message.command[1].split("_")[1]
        try:
            doc = await db.files.find_one({"_id": ObjectId(doc_id)})
            if doc:
                caption = CAPTION_TEMPLATE.format(file_name=doc['file_name'].upper())
                
                # Send File
                sent_file = await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=doc['file_id'],
                    caption=caption
                )
                
                # Send Delete Warning
                warn_msg = await message.reply_text(DELETE_WARNING)
                
                # Schedule deletion for both messages
                asyncio.create_task(auto_delete(client, message.chat.id, [sent_file.id, warn_msg.id]))
                return
        except Exception as e:
            logger.error(f"Error in deep link start: {e}")
            return

    await message.reply_text(f"👋 **​​​​​​​​​​🚩 WellCome My User 🚩 {message.from_user.mention}!**\n​​​​​​​​​​
    ɪ ᴀᴍ ᴛʜᴇ ᴍᴏsᴛ ᴘᴏᴡᴇʀғᴜʟ ᴀᴜᴛᴏ ғɪʟᴛᴇʀ ʙᴏᴛ ᴡɪᴛʜ ᴘʀᴇᴍɪᴜᴍ ғᴇᴀᴛᴜʀᴇ..")

@app.on_message(filters.command("stats") & filters.user(ADMIN_ID))
async def stats_handler(client, message):
    count = await db.files.count_documents({})
    await message.reply_text(f"📊 **Total Indexed Files:** `{count}`")

# --- GROUP/PM SEARCH LOGIC ---
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
    
    bot_info = await client.get_me()

    if results:
        btns = []
        for f in results:
            size = round(f['file_size'] / (1024 * 1024), 2)
            # URL to redirect to bot PM with start param
            f_url = f"https://t.me/{bot_info.username}?start=file_{str(f['_id'])}"
            btns.append([InlineKeyboardButton(f"📂 {f['file_name'].title()} ({size}MB)", url=f_url)])
        
        await message.reply_text(
            f"🔍 **Found {len(results)} results for:** <code>{query}</code>\n\nClick button to get file in PM (Auto-delete in 2 min) 👇",
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
                    f_url = f"https://t.me/{bot_info.username}?start=file_{str(doc['_id'])}"
                    m_btns.append([InlineKeyboardButton(f"🔎 Did you mean: {m[:30]}...", url=f_url)])
            await message.reply_text("<b>Spelling Mistake Bro ‼️</b>\nChoose correct one to get file in PM 👇", reply_markup=InlineKeyboardMarkup(m_btns))
        else:
            # NO RESULTS FOUND - Show Special Message
            await message.reply_text(NO_RESULTS_TEXT)

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
    logger.info("🚀 INDRA AUTO-DELETE REDIRECT BOT IS LIVE!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_rdx())
