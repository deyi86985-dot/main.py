import logging, os, asyncio, re, time, requests, difflib
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
from flask import Flask
from threading import Thread
from spellchecker import SpellChecker
from imdb import Cinemagoer

# --- CONFIG ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"
OWNER_ID = 6783893816 

# Tools
spell = SpellChecker()
ia = Cinemagoer()

# --- DATABASE ---
class Database:
    def __init__(self, url):
        self.client = AsyncIOMotorClient(url)
        self.db = self.client["CINESOCIETY_ULTRA_FINAL"]
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
    # @ এবং [] রিমুভ করা
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

@app.on_message(filters.command("start"))
async def start(c, m):
    user = await db.get_user(m.from_user.id)
    if user["is_ban"]: return

    # Deep link for file
    if len(m.command) > 1 and m.command[1].startswith("file_"):
        # Verification Check (12 Hours)
        shortlink_on = await db.get_setting("shortlink_on", False)
        if shortlink_on and not user["is_premium"]:
            if (time.time() - user["last_verify"]) > 43200:
                v_msg = await db.get_setting("shortlink_info", "ʜᴇʏ {user_name}, ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴠᴇʀɪғɪᴇᴅ ᴛᴏᴅᴀʏ...")
                v_url = await get_shortlink(f"https://t.me/{(await c.get_me()).username}?start=verify_{m.from_user.id}")
                return await m.reply(v_msg.replace("{user_name}", m.from_user.first_name), 
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Verify ✅", url=v_url)]]))

        doc_id = m.command[1].split("_")[1]
        doc = await db.files.find_one({"_id": ObjectId(doc_id)})
        if doc:
            sent = await c.send_cached_media(m.chat.id, doc['file_id'], caption=doc['caption'])
            warn = await m.reply("⚠️ This file deletes in 2 mins!")
            asyncio.create_task(auto_delete(c, m.chat.id, [sent.id, warn.id]))
            return

    # Start Message (Owner Editable)
    text = await db.get_setting("start_text", f"Welcome {m.from_user.mention}!")
    img = await db.get_setting("start_img", "https://default_image_url.jpg")
    await m.reply_photo(img, caption=text + "\n\n**Edit by INDRA**")

# Search Logic (PM & Group)
@app.on_message(filters.text & ~filters.command(["start", "stats", "index", "plan", "commands"]))
async def handle_search(c, m):
    user = await db.get_user(m.from_user.id)
    if user["is_ban"]: return

    # PM Search Restriction
    pm_off = await db.get_setting("pm_search_off", False)
    if m.chat.type == "private" and pm_off and not user["is_premium"]:
        pm_msg = await db.get_setting("pm_search_msg", "PLZ REQUEST ON GROUP")
        return await m.reply(pm_msg)

    query = m.text.lower().strip()
    # Database Search with Regex
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

# --- ADMIN & OWNER COMMANDS ---
@app.on_message(filters.command("add_premium") & filters.user(OWNER_ID))
async def add_prem(c, m):
    uid = int(m.command[1])
    await db.users.update_one({"user_id": uid}, {"$set": {"is_premium": True}})
    await m.reply(f"✅ User `{uid}` added to Premium!")

@app.on_message(filters.command("ban") & filters.user(OWNER_ID))
async def ban(c, m):
    uid = int(m.command[1])
    await db.users.update_one({"user_id": uid}, {"$set": {"is_ban": True}})
    await m.reply("🚫 User Banned!")

@app.on_message(filters.command("stats"))
async def stats(c, m):
    if not await db.is_admin(m.from_user.id): return
    count = await db.files.count_documents({})
    await m.reply(f"📊 Total Files: `{count}`")

@app.on_message(filters.command("commands") & filters.user(OWNER_ID))
async def cmd_list(c, m):
    text = "🛠 **Admin Commands:**\n/stats, /index, /add_admin, /ban, /unban\n\n👑 **Owner Settings:**\n/shortlink_on, /pm_search_off, /add_premium"
    await m.reply(text)

# --- BOOTSTRAP ---
if __name__ == "__main__":
    app.start()
    print("🚀 Master Bot is Live! Edit by INDRA")
    idle()
