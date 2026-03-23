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

# --- WEB SERVER (Render Port Fix) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "CINESOCIETY Master is Alive! 🚀"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- DATABASE ---
class Database:
    def __init__(self, url):
        self.client = AsyncIOMotorClient(url)
        self.db = self.client["CINESOCIETY_ULTRA_V3"]
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

    async def save_file(self, file_id, file_name, file_size, caption):
        # বাটন ক্লিন করার জন্য প্রি-ফিল্টারিং
        clean_name = re.sub(r'(@\w+|\[.*?\])', '', file_name).lower().strip()
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

db = Database(MONGO_URI)
app = Client("CINESOCIETY_PRO", API_ID, API_HASH, bot_token=BOT_TOKEN)

# --- HELPERS ---
def format_btn(filename):
    clean = re.sub(r'(@\w+|\[.*?\])', '', filename)
    res_match = re.search(r'(480p|720p|1080p|2160p|4k)', filename, re.I)
    res = res_match.group(0).upper() if res_match else "HD"
    clean = re.sub(r'[_.\-]', ' ', clean).strip().title()
    return f"🎬 {res} | {clean[:35]}"

async def get_shortlink(url):
    api_url = await db.get_setting("shortlink_api_url", "https://gplinks.in/api")
    api_key = await db.get_setting("shortlink_api_key", "YOUR_API_KEY") 
    try:
        res = requests.get(f"{api_url}?api={api_key}&url={url}").json()
        return res["shortenedUrl"]
    except: return url

async def get_imdb_data(query):
    try:
        search = ia.search_movie(query)
        if search:
            m = ia.get_movie(search[0].movieID)
            return {'title': m.get('title'), 'year': m.get('year'), 'rating': m.get('rating', 'N/A'),
                    'genres': ", ".join(m.get('genres', [])), 'poster': m.get('full-size cover url')}
    except: return None

async def auto_delete(client, chat_id, message_ids):
    await asyncio.sleep(120) 
    try: await client.delete_messages(chat_id, message_ids)
    except: pass

# --- HANDLERS ---

# ১. সরাসরি ফাইল দিলে ইনডেক্স হবে (অ্যাডমিনদের জন্য)
@app.on_message(filters.private & (filters.document | filters.video))
async def handle_incoming_file(c, m):
    if not await db.is_admin(m.from_user.id): return
    file = m.document or m.video
    if await db.save_file(file.file_id, file.file_name, file.file_size, m.caption):
        await m.reply_text(f"✅ **সফলভাবে ইনডেক্স হয়েছে!**\n📄 নাম: `{file.file_name}`\n\n**Edit by INDRA**")
    else:
        await m.reply_text("⚠️ এই ফাইলটি অলরেডি ডাটাবেসে আছে।")

# ২. স্টার্ট হ্যান্ডলার (শর্টলিংক ও ১২ ঘণ্টা ভেরিফিকেশন সহ)
@app.on_message(filters.command("start"))
async def start(c, m):
    user = await db.get_user(m.from_user.id)
    if user["is_ban"]: return

    if len(m.command) > 1 and m.command[1].startswith("file_"):
        shortlink_on = await db.get_setting("shortlink_on", False)
        if shortlink_on and not user["is_premium"]:
            if (time.time() - user["last_verify"]) > 43200:
                v_msg = await db.get_setting("shortlink_info", "ʜᴇʏ {user_name}, ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴠᴇʀɪғɪᴇᴅ...")
                v_url = await get_shortlink(f"https://t.me/{(await c.get_me()).username}?start=verify_{m.from_user.id}")
                return await m.reply(v_msg.replace("{user_name}", m.from_user.first_name), 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Verify ✅", url=v_url)]]))

        doc_id = m.command[1].split("_")[1]
        doc = await db.files.find_one({"_id": ObjectId(doc_id)})
        if doc:
            sent = await c.send_cached_media(m.chat.id, doc['file_id'], caption=doc['caption'])
            warn = await m.reply("⚠️ Deleted in 2 mins! Forward it.")
            asyncio.create_task(auto_delete(c, m.chat.id, [sent.id, warn.id]))
            return

    text = await db.get_setting("start_text", f"Welcome {m.from_user.mention}!")
    img = await db.get_setting("start_img", "https://default_image_url.jpg")
    await m.reply_photo(img, caption=text + "\n\n**Edit by INDRA**")

# ৩. ইনডেক্স কমান্ড (চ্যানেল থেকে প্রোগ্রেস আপডেট সহ)
@app.on_message(filters.command("index"))
async def index_cmd(client, message):
    if not await db.is_admin(message.from_user.id): return
    target = CHANNEL_ID if len(message.command) < 2 else message.command[1]
    m = await message.reply("🔄 **ইনডেক্সিং শুরু হচ্ছে...**")
    count, checked = 0, 0
    try:
        async for user_msg in client.get_chat_history(target):
            checked += 1
            file = user_msg.document or user_msg.video
            if file:
                if await db.save_file(file.file_id, getattr(file, "file_name", "Untitled"), file.file_size, user_msg.caption):
                    count += 1
            if checked % 100 == 0:
                await m.edit(f"🔄 ইনডেক্সিং চলছে...\nচেক করা হয়েছে: `{checked}`\nসেভ হয়েছে: `{count}`")
        await m.edit(f"✅ **ইনডেক্সিং সম্পন্ন!**\nমোট চেক: `{checked}`\nনতুন সেভ: `{count}`\n\n**Edit by INDRA**")
    except Exception as e:
        await m.edit(f"❌ এরর: `{e}`")

# ৪. সার্চ হ্যান্ডলার (IMDb ও ক্লিন বাটন সহ)
@app.on_message(filters.text & ~filters.command(["start", "stats", "index", "plan", "commands", "add_premium"]))
async def search_handler(c, m):
    user = await db.get_user(m.from_user.id)
    if user["is_ban"]: return

    pm_off = await db.get_setting("pm_search_off", False)
    if m.chat.type == "private" and pm_off and not user["is_premium"]:
        pm_msg = await db.get_setting("pm_search_msg", "PLZ REQUEST ON GROUP")
        return await m.reply(pm_msg)

    query = m.text.lower().strip()
    words = query.split()
    regex = f"^{''.join([f'(?=.*{re.escape(w)})' for w in words])}.*$"
    cursor = db.files.find({"$or": [{"file_name": {"$regex": regex, "$options": "i"}}, {"clean_name": {"$regex": regex, "$options": "i"}}]})
    results = await cursor.to_list(length=10)

    if results:
        imdb = await get_imdb_data(query)
        bot = await c.get_me()
        btns = [[InlineKeyboardButton(format_btn(f['file_name']), url=f"https://t.me/{bot.username}?start=file_{f['_id']}")] for f in results]
        
        caption = f"🎬 **Name:** `{imdb['title'] if imdb else query.title()}`\n"
        if imdb:
            caption += f"🌟 **Rating:** `{imdb['rating']}/10` | 📅 **Year:** `{imdb['year']}`\n🎭 **Genre:** `{imdb['genres']}`\n\n"
        caption += "**Edit by INDRA**"

        if imdb and imdb['poster']:
            await m.reply_photo(photo=imdb['poster'], caption=caption, reply_markup=InlineKeyboardMarkup(btns))
        else:
            await m.reply_text(caption, reply_markup=InlineKeyboardMarkup(btns))
    else:
        await m.reply_text("❌ No results found!\n\n**Edit by INDRA**")

# ৫. ওনার ও অ্যাডমিন কমান্ড
@app.on_message(filters.command("stats"))
async def stats(c, m):
    if not await db.is_admin(m.from_user.id): return
    count = await db.files.count_documents({})
    await m.reply(f"📊 Total Files: `{count}`\n\n**Edit by INDRA**")

@app.on_message(filters.command("add_premium") & filters.user(OWNER_ID))
async def add_prem(c, m):
    uid = int(m.command[1])
    await db.users.update_one({"user_id": uid}, {"$set": {"is_premium": True}})
    await m.reply(f"✅ User `{uid}` is now Premium!")

# --- BOOTSTRAP ---
async def start_bot():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("🚀 Master Bot is LIVE! Edit by INDRA")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
