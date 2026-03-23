import logging, os, asyncio, re, time, requests, difflib
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

# --- CONFIG ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"
OWNER_ID = 6783893816 
CHANNEL_ID = -1003065768519 

# Tools
spell = SpellChecker()
ia = Cinemagoer()

# --- WEB SERVER ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "CINESOCIETY Master is Alive! 🚀"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- DATABASE HANDLER ---
class Database:
    def __init__(self, url):
        self.client = AsyncIOMotorClient(url)
        self.db = self.client["CINESOCIETY_ULTRA_MASTER"]
        self.users = self.db["users"]
        self.settings = self.db["settings"]
        self.files = self.db["files"]
        self.admins = self.db["admins"]

    async def get_setting(self, key, default):
        s = await self.settings.find_one({"key": key})
        return s["value"] if s else default

    async def update_setting(self, key, value):
        await self.settings.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

    async def get_user(self, user_id):
        user = await self.users.find_one({"user_id": user_id})
        if not user:
            user = {"user_id": user_id, "is_ban": False, "is_premium": False, "last_verify": 0}
            await self.users.insert_one(user)
        return user

    async def is_admin(self, user_id):
        if user_id == OWNER_ID: return True
        return await self.admins.find_one({"user_id": user_id}) is not None

db = Database(MONGO_URI)
app = Client("CINESOCIETY_PRO", API_ID, API_HASH, bot_token=BOT_TOKEN)

# --- HELPERS ---
def format_btn(filename):
    clean = re.sub(r'(@\w+|\[.*?\])', '', filename)
    res_match = re.search(r'(480p|720p|1080p|2160p|4k)', filename, re.I)
    res = res_match.group(0).upper() if res_match else "HD"
    se_match = re.search(r'(S\d+|E\d+)', filename, re.I)
    se = se_match.group(0).upper() if se_match else ""
    clean = re.sub(r'(480p|720p|1080p|2160p|4k|S\d+|E\d+)', '', clean, flags=re.I)
    clean = re.sub(r'[_.\-]', ' ', clean).strip().title()
    return f"🎬 {res} / {se} {clean[:30]}".strip()

async def get_shortlink(url):
    api_url = await db.get_setting("shortlink_api_url", "https://gplinks.in/api")
    api_key = await db.get_setting("shortlink_api_key", "YOUR_KEY")
    try:
        res = requests.get(f"{api_url}?api={api_key}&url={url}").json()
        return res["shortenedUrl"]
    except: return url

# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def start(c, m):
    user = await db.get_user(m.from_user.id)
    if user["is_ban"]: return await m.reply("You are BANNED! 🚫")

    # File Link Logic with 12h Verification
    if len(m.command) > 1 and m.command[1].startswith("file_"):
        short_on = await db.get_setting("shortlink_on", False)
        if short_on and not user["is_premium"]:
            if (time.time() - user["last_verify"]) > 43200:
                v_text = await db.get_setting("shortlink_info", "ʜᴇʏ {user_name}, ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴠᴇʀɪғɪᴇᴅ ᴛᴏᴅᴀʏ...")
                v_url = await get_shortlink(f"https://t.me/{(await c.get_me()).username}?start=verify_{m.from_user.id}")
                btn = [[InlineKeyboardButton("Verify ✅", url=v_url)]]
                return await m.reply(v_text.replace("{user_name}", m.from_user.first_name), reply_markup=InlineKeyboardMarkup(btn))

        # Send File
        doc_id = m.command[1].split("_")[1]
        doc = await db.files.find_one({"_id": ObjectId(doc_id)})
        if doc: await c.send_cached_media(m.chat.id, doc['file_id'], caption=doc['caption'])
        return

    # Dynamic Start Message
    s_text = await db.get_setting("start_text", "Welcome to @CINESOCIETY02 ! 🎬")
    s_img = await db.get_setting("start_img", "https://telegra.ph/file/default.jpg")
    s_btns_raw = await db.get_setting("start_btns", "Channel|https://t.me/CINESOCIETY02")
    
    btns = [[InlineKeyboardButton(b.split("|")[0], url=b.split("|")[1])] for b in s_btns_raw.split("\n") if "|" in b]
    await m.reply_photo(s_img, caption=s_text, reply_markup=InlineKeyboardMarkup(btns))

# --- OWNER SETTINGS COMMANDS ---
@app.on_message(filters.command("edit_start") & filters.user(OWNER_ID))
async def edit_s(c, m):
    # Format: /edit_start PhotoURL | Start Text
    try:
        data = m.text.split(None, 1)[1].split("|")
        await db.update_setting("start_img", data[0].strip())
        await db.update_setting("start_text", data[1].strip())
        await m.reply("✅ Start Message Updated!")
    except: await m.reply("Format: `/edit_start URL | Text`")

@app.on_message(filters.command("add_premium") & filters.user(OWNER_ID))
async def add_prem(c, m):
    uid = int(m.command[1])
    await db.update_user(uid, {"is_premium": True})
    await m.reply(f"✅ User {uid} is Premium!")

@app.on_message(filters.command("shortlink_on") & filters.user(OWNER_ID))
async def sl_on(c, m):
    await db.update_setting("shortlink_on", True)
    await m.reply("✅ Shortlink Enabled!")

@app.on_message(filters.command("shortlink_off") & filters.user(OWNER_ID))
async def sl_off(c, m):
    await db.update_setting("shortlink_on", False)
    await m.reply("❌ Shortlink Disabled!")

# --- SEARCH HANDLER ---
@app.on_message(filters.text & ~filters.command(["start", "stats", "index", "plan", "commands"]))
async def search(c, m):
    user = await db.get_user(m.from_user.id)
    pm_search_only = await db.get_setting("pm_search_off", False)
    
    if m.chat.type == "private" and pm_search_only and not user["is_premium"]:
        pm_msg = await db.get_setting("pm_search_msg", "PLZ REQUEST ON GROUP")
        return await m.reply(pm_msg)

    query = m.text.lower().strip()
    # Search logic (Database Regex)
    words = query.split()
    regex = f"^{''.join([f'(?=.*{re.escape(w)})' for w in words])}.*$"
    cursor = db.files.find({"$or": [{"file_name": {"$regex": regex, "$options": "i"}}, {"clean_name": {"$regex": regex, "$options": "i"}}]})
    results = await cursor.to_list(length=10)

    if results:
        imdb = await get_imdb_data(query)
        btns = [[InlineKeyboardButton(format_btn(f['file_name']), url=f"https://t.me/{(await c.get_me()).username}?start=file_{f['_id']}")] for f in results]
        
        caption = f"🎬 **Name:** `{imdb['title'] if imdb else query.title()}`\n"
        if imdb: caption += f"🌟 **Rating:** `{imdb['rating']}/10`\n"
        caption += "**Edit by INDRA**"

        if imdb and imdb['poster']: await m.reply_photo(imdb['poster'], caption=caption, reply_markup=InlineKeyboardMarkup(btns))
        else: await m.reply_text(caption, reply_markup=InlineKeyboardMarkup(btns))
    else: await m.reply_text("❌ No results found!\n\n**Edit by INDRA**")

# --- BOOTSTRAP ---
async def main():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("🚀 CINESOCIETY ULTIMATE MASTER IS LIVE!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
