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

# --- WEB SERVER ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "CINESOCIETY MASTER SPEED-UP! 🚀"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- DATABASE ---
class Database:
    def __init__(self, url):
        self.client = AsyncIOMotorClient(url)
        self.db = self.client["CINESOCIETY_FINAL_V6"]
        self.files = self.db["files"]
        self.users = self.db["users"]

    async def get_user(self, user_id):
        user = await self.users.find_one({"user_id": user_id})
        if not user:
            user = {"user_id": user_id, "is_ban": False, "is_premium": False, "last_verify": 0}
            await self.users.insert_one(user)
        return user

    async def save_file(self, f_id, f_name, f_size, caption):
        clean = re.sub(r'(@\w+|\[.*?\])', '', f_name).lower().strip()
        if not await self.files.find_one({"file_name": f_name, "file_size": f_size}):
            await self.files.insert_one({
                'file_id': f_id, 'file_name': f_name, 
                'clean_name': clean, 'file_size': f_size, 'caption': caption
            })
            return True
        return False

db = Database(MONGO_URI)
app = Client("CINESOCIETY_PRO", API_ID, API_HASH, bot_token=BOT_TOKEN)

# --- HELPERS ---
def format_btn(filename):
    clean = re.sub(r'(@\w+|\[.*?\])', '', filename)
    res = re.search(r'(480p|720p|1080p|4k)', filename, re.I)
    res = res.group(0).upper() if res else "HD"
    se = re.search(r'(S\d+|E\d+|Season\s*\d+)', filename, re.I)
    se_info = se.group(0).upper() if se else ""
    clean = re.sub(r'(480p|720p|1080p|4k|S\d+|E\d+|Season\s*\d+)', '', clean, flags=re.I)
    clean = re.sub(r'[_.\-]', ' ', clean).strip().title()
    return f"🎬 {res} / {se_info} {clean[:22]}"

async def auto_delete(c, chat_id, msg_ids):
    await asyncio.sleep(120)
    try: await c.delete_messages(chat_id, msg_ids)
    except: pass

# --- SEARCH ENGINE (Optimized for Speed) ---
async def send_results(m, query, page=0, is_cb=False):
    words = query.strip().split()
    regex = f".*{'.*'.join([re.escape(w) for w in words])}.*"
    
    # Projection ব্যবহার করা হয়েছে যাতে শুধু প্রয়োজনীয় ডেটা আসে
    projection = {"file_name": 1, "clean_name": 1}
    
    cursor = db.files.find(
        {"clean_name": {"$regex": regex, "$options": "i"}},
        projection
    ).limit(60) # ৫০-৬০টি রেজাল্ট খুঁজলে সার্চ ফাস্ট হয়
    
    results = await cursor.to_list(length=60)

    if not results:
        txt = "❌ **No results found!**\n\n**Edit by INDRA**"
        if is_cb: return await m.answer("No more files!", show_alert=True)
        return await m.reply_text(txt)

    start, end = page * 10, (page + 1) * 10
    page_items = results[start:end]
    total_pages = (len(results) + 9) // 10

    btns = [[
        InlineKeyboardButton("🌐 Language", callback_data=f"flt_lang_{query}_{page}"),
        InlineKeyboardButton("📂 Session", callback_data=f"flt_sess_{query}_{page}")
    ]]

    for f in page_items:
        btns.append([InlineKeyboardButton(format_btn(f['file_name']), url=f"https://t.me/{(await app.get_me()).username}?start=file_{f['_id']}")])

    nav = []
    if page > 0: nav.append(InlineKeyboardButton("<", callback_data=f"pg_{query}_{page-1}"))
    if end < len(results): nav.append(InlineKeyboardButton(">", callback_data=f"pg_{query}_{page+1}"))
    if nav: btns.append(nav)

    text = f"🔍 **Results for:** `{query.upper()}`\n📄 **Page:** `{page+1}/{total_pages}`\n\n**Edit by INDRA**"
    
    if is_cb:
        await m.message.edit(text, reply_markup=InlineKeyboardMarkup(btns))
    else:
        sent = await m.reply_text(text, reply_markup=InlineKeyboardMarkup(btns))
        if m.chat.type in ["group", "supergroup"]:
            asyncio.create_task(auto_delete(app, m.chat.id, [sent.id]))

# --- COMMANDS ---
@app.on_message(filters.command("start"))
async def start_cmd(c, m):
    if len(m.command) > 1 and m.command[1].startswith("file_"):
        doc = await db.files.find_one({"_id": ObjectId(m.command[1].split("_")[1])})
        if doc:
            f_msg = await c.send_cached_media(m.chat.id, doc['file_id'], caption=doc['caption'])
            w_msg = await m.reply("⚠️ **Deleted in 2 mins!**")
            asyncio.create_task(auto_delete(c, m.chat.id, [f_msg.id, w_msg.id]))
        return
    await m.reply_text(f"👋 **Hello {m.from_user.mention}!**\nSearch movies here.\n\n**Edit by INDRA**")

@app.on_message(filters.command("stats"))
async def stats_cmd(c, m):
    count = await db.files.count_documents({})
    await m.reply(f"📊 **Total Indexed Files:** `{count}`\n\n**Edit by INDRA**")

@app.on_message(filters.command("index") & filters.user(OWNER_ID))
async def index_cmd(c, m):
    msg = await m.reply("🔄 **Indexing...**")
    count, checked = 0, 0
    async for user_msg in c.get_chat_history(CHANNEL_ID):
        checked += 1
        file = user_msg.document or user_msg.video
        if file:
            if await db.save_file(file.file_id, file.file_name, file.file_size, user_msg.caption): count += 1
        if checked % 100 == 0: await msg.edit(f"🔄 Checked: `{checked}` | Saved: `{count}`")
    await msg.edit(f"✅ **Done!** Total: `{count}`")

@app.on_message(filters.private & (filters.document | filters.video))
async def pm_index(c, m):
    if m.from_user.id != OWNER_ID: return
    file = m.document or m.video
    if await db.save_file(file.file_id, file.file_name, file.file_size, m.caption):
        await m.reply_text(f"✅ **Indexed:** `{file.file_name}`")

@app.on_message(filters.text & ~filters.command(["start", "stats", "index"]))
async def handle_search(c, m):
    if m.text.startswith("/"): return 
    await send_results(m, m.text.lower().strip())

# --- CALLBACKS ---
@app.on_callback_query()
async def cb_handler(c, cb: CallbackQuery):
    data = cb.data.split("_")
    if data[0] == "pg": await send_results(cb, data[1], int(data[2]), is_cb=True)
    elif data[0] == "flt":
        q, p = data[2], data[3]
        if data[1] == "lang":
            btns = [[InlineKeyboardButton(l, callback_data=f"apl_lang_{l}_{q}")] for l in ["Hindi", "English", "Bengali", "Tamil"]]
            btns.append([InlineKeyboardButton("🔙 Back", callback_data=f"pg_{q}_{p}")])
            await cb.message.edit(f"🌍 **Select Language:**", reply_markup=InlineKeyboardMarkup(btns))
        else:
            btns = [[InlineKeyboardButton(f"S{i}", callback_data=f"apl_sess_{i}_{q}"), InlineKeyboardButton(f"S{i+1}", callback_data=f"apl_sess_{i+1}_{q}")] for i in range(1, 11, 2)]
            btns.append([InlineKeyboardButton("🔙 Back", callback_data=f"pg_{q}_{p}")])
            await cb.message.edit(f"📂 **Select Session:**", reply_markup=InlineKeyboardMarkup(btns))
    elif data[0] == "apl":
        f_t, val, q = data[1], data[2], data[3]
        pat = f"S{int(val):02d}|Season {val}" if f_t == "sess" else val
        cursor = db.files.find({"clean_name": {"$regex": q}, "file_name": {"$regex": pat, "$options": "i"}})
        res = await cursor.to_list(length=15)
        if not res: return await cb.message.edit("❌ **No files in this filter.**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"pg_{q}_0")]]))
        btns = [[InlineKeyboardButton(format_btn(f['file_name']), url=f"https://t.me/{(await c.get_me()).username}?start=file_{f['_id']}")] for f in res]
        btns.append([InlineKeyboardButton("🔙 Back to Results", callback_data=f"pg_{q}_0")])
        await cb.message.edit(f"✅ **Filtered:**", reply_markup=InlineKeyboardMarkup(btns))

# --- BOOTSTRAP ---
async def start_bot():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    print("🚀 Master Bot is LIVE & FAST!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
