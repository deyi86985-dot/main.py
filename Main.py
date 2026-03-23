import logging, os, asyncio, re, time, requests
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
from flask import Flask
from threading import Thread
from imdb import Cinemagoer

# --- CONFIG ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"
OWNER_ID = 6783893816 
CHANNEL_ID = -1003065768519 

ia = Cinemagoer()

# --- DATABASE ---
class Database:
    def __init__(self, url):
        self.client = AsyncIOMotorClient(url)
        self.db = self.client["CINESOCIETY_ULTRA_V4"]
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
    res = re.search(r'(480p|720p|1080p|4k)', filename, re.I)
    res = res.group(0).upper() if res else "HD"
    se_match = re.search(r'(S\d+|E\d+)', filename, re.I)
    se = se_match.group(0).upper() if se_match else ""
    clean = re.sub(r'(480p|720p|1080p|4k|S\d+|E\d+)', '', clean, flags=re.I)
    clean = re.sub(r'[_.\-]', ' ', clean).strip().title()
    return f"🎬 {res} / {se} {clean[:25]}".strip()

async def auto_delete(c, chat_id, msg_id):
    await asyncio.sleep(180) # ৩ মিনিট
    try: await c.delete_messages(chat_id, msg_id)
    except: pass

# --- SEARCH & PAGINATION ---
async def send_results(m, query, page=0, is_cb=False):
    words = query.split()
    regex = f"^{''.join([f'(?=.*{re.escape(w)})' for w in words])}.*$"
    cursor = db.files.find({"clean_name": {"$regex": regex, "$options": "i"}})
    results = await cursor.to_list(length=100)

    if not results:
        return await m.reply("❌ No results found!") if not is_cb else await m.answer("No results!")

    start = page * 10
    end = start + 10
    page_items = results[start:end]
    total_pages = (len(results) + 9) // 10

    # Top Filter Buttons
    btns = [[
        InlineKeyboardButton("🌐 Language", callback_data=f"filt_lang_{query}_{page}"),
        InlineKeyboardButton("📂 Session", callback_data=f"filt_sess_{query}_{page}")
    ]]

    for f in page_items:
        btns.append([InlineKeyboardButton(format_btn(f['file_name']), url=f"https://t.me/{(await app.get_me()).username}?start=file_{f['_id']}")])

    # Pagination Row
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("<", callback_data=f"pg_{query}_{page-1}"))
    if end < len(results): nav.append(InlineKeyboardButton(">", callback_data=f"pg_{query}_{page+1}"))
    if nav: btns.append(nav)

    text = f"🔍 **Results for:** `{query.upper()}`\n📄 **Page:** `{page+1}/{total_pages}`\n\n**Edit by INDRA**"
    
    if is_cb:
        await m.message.edit(text, reply_markup=InlineKeyboardMarkup(btns))
    else:
        sent = await m.reply_text(text, reply_markup=InlineKeyboardMarkup(btns))
        asyncio.create_task(auto_delete(app, m.chat.id, sent.id))

# --- HANDLERS ---
@app.on_message(filters.text & ~filters.command(["start", "index", "stats", "commands", "pm_search_off", "pm_search_on"]))
async def handle_search(c, m):
    user = await db.get_user(m.from_user.id)
    pm_off = await db.get_setting("pm_search_off", False)
    if m.chat.type == "private" and pm_off and not user["is_premium"]:
        return await m.reply("⚠️ PLZ REQUEST ON GROUP")
    
    await send_results(m, m.text.lower().strip())

@app.on_callback_query()
async def cb_handler(c, cb: CallbackQuery):
    data = cb.data.split("_")
    
    if data[0] == "pg": # Page Change
        await send_results(cb, data[1], int(data[2]), is_cb=True)

    elif data[0] == "filt": # Filter Menu
        f_type, query, page = data[1], data[2], data[3]
        if f_type == "lang":
            langs = ["Hindi", "English", "Bengali", "Tamil", "Telugu"]
            btn_list = [[InlineKeyboardButton(l, callback_data=f"apply_lang_{l}_{query}")] for l in langs]
            btn_list.append([InlineKeyboardButton("🔙 Back", callback_data=f"pg_{query}_{page}")])
            await cb.message.edit(f"🌍 **Select Language for {query.title()}:**", reply_markup=InlineKeyboardMarkup(btn_list))
        elif f_type == "sess":
            btn_list = []
            for i in range(1, 11, 2):
                btn_list.append([InlineKeyboardButton(f"S{i}", callback_data=f"apply_sess_{i}_{query}"),
                                 InlineKeyboardButton(f"S{i+1}", callback_data=f"apply_sess_{i+1}_{query}")])
            btn_list.append([InlineKeyboardButton("🔙 Back", callback_data=f"pg_{query}_{page}")])
            await cb.message.edit(f"📂 **Select Session for {query.title()}:**", reply_markup=InlineKeyboardMarkup(btn_list))

    elif data[0] == "apply": # Apply Filter Logic
        f_type, val, query = data[1], data[2], data[3]
        if f_type == "lang":
            cursor = db.files.find({"clean_name": {"$regex": query}, "file_name": {"$regex": val, "$options": "i"}})
        else:
            pattern = f"S{int(val):02d}|Season {val}"
            cursor = db.files.find({"clean_name": {"$regex": query}, "file_name": {"$regex": pattern, "$options": "i"}})
        
        filtered = await cursor.to_list(length=15)
        if not filtered:
            btn = [[InlineKeyboardButton("🔙 Back", callback_data=f"pg_{query}_0")]]
            return await cb.message.edit("❌ **This is the language file here.**", reply_markup=InlineKeyboardMarkup(btn))

        btns = [[InlineKeyboardButton(format_btn(f['file_name']), url=f"https://t.me/{(await c.get_me()).username}?start=file_{f['_id']}")] for f in filtered]
        btns.append([InlineKeyboardButton("🔙 Back to Results", callback_data=f"pg_{query}_0")])
        await cb.message.edit(f"✅ **Results for {val}:**", reply_markup=InlineKeyboardMarkup(btns))

# (বাকি সব অ্যাডমিন কমান্ড/স্টার্ট লজিক আগের কোডের মতই থাকবে...)
@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    # (আগের ভেরিফিকেশন ও স্টার্ট মেসেজ লজিক)
    await m.reply_text("👋 Hello! Search movies here.")

# --- BOOTSTRAP ---
if __name__ == "__main__":
    app.run()
