import logging
import os
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

# আপনার টেলিগ্রাম আইডি এখানে দিন (আইডি পেতে @MissRose_bot এ /id লিখুন)
ADMIN_ID = 6783893816

# আপনার ফাইল চ্যানেলের আইডি (উদাহরণ: -10012345678)
CHANNEL_ID = -1003065768519

# --- DATABASE ---
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["RDX_Advanced_Bot"]
files_col = db["files"]
settings_col = db["settings"]

# --- WEB SERVER ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "RDX Pro Bot is Running!"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- BOT INIT ---
app = Client("RDX_Pro_Bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- SETTINGS HELPERS ---
async def get_config(key, default):
    data = await settings_col.find_one({"key": key})
    return data["value"] if data else default

async def set_config(key, value):
    await settings_col.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

# --- HANDLERS ---

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    text = await get_config("start_text", f"👋 **Hello {message.from_user.mention}!**\n\nWelcome to **RDX Auto Filter Bot**. I can provide files automatically in groups.")
    img = await get_config("start_img", "https://telegra.ph/file/0c93540e1f74457e5b22b.jpg")
    
    buttons = [
        [InlineKeyboardButton("➕ Add Me to Your Group ➕", url=f"http://t.me/{client.me.username}?startgroup=true")],
        [InlineKeyboardButton("📢 Updates", url="https://t.me/CINESOCIETY_OFFICIAL"), InlineKeyboardButton("🛠 Support", url="@CINESOCIETY_BOT")],
        [InlineKeyboardButton("⚙️ Settings (Admin)", callback_data="admin_settings")]
    ]
    
    try:
        await message.reply_photo(photo=img, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- ADMIN SETTINGS COMMANDS ---

@app.on_message(filters.command("setstart") & filters.user(ADMIN_ID))
async def cmd_setstart(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/setstart Your welcome message`")
    new_text = message.text.split(None, 1)[1]
    await set_config("start_text", new_text)
    await message.reply("✅ **Start message updated!**")

@app.on_message(filters.command("setimg") & filters.user(ADMIN_ID))
async def cmd_setimg(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/setimg Image_Link`")
    new_img = message.command[1]
    await set_config("start_img", new_img)
    await message.reply("✅ **Start image updated!**")

# --- SMART INDEXING (Manual & Auto) ---

@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def manual_index(client, message):
    if len(message.command) < 2: return await message.reply("Usage: `/index @ChannelUsername`")
    target = message.command[1]
    msg = await message.reply("🔄 **Attempting to index...**")
    
    count = 0
    try:
        # Try to get history (Works if bot is Admin and channel is public)
        async for user_msg in client.get_chat_history(target):
            file = user_msg.document or user_msg.video or user_msg.audio
            if file:
                file_name = getattr(file, "file_name", "Untitled").lower()
                if not await files_col.find_one({"file_name": file_name, "file_size": file.file_size}):
                    await files_col.insert_one({"file_id": file.file_id, "file_name": file_name, "file_size": file.file_size})
                    count += 1
        await msg.edit(f"✅ **Success!** Added **{count}** files.")
    except Exception as e:
        await msg.edit(f"❌ **Error:** `{e}`\n\n**Tip:** If this fails, forward the files from your channel to the bot. It will index them automatically!")

# --- AUTO INDEX (When files are forwarded or posted) ---
@app.on_message((filters.chat(CHANNEL_ID) | filters.forwarded) & (filters.document | filters.video | filters.audio))
async def auto_index(client, message):
    file = message.document or message.video or message.audio
    file_name = getattr(file, "file_name", "Untitled").lower()
    if not await files_col.find_one({"file_name": file_name, "file_size": file.file_size}):
        await files_col.insert_one({"file_id": file.file_id, "file_name": file_name, "file_size": file.file_size})
        logger.info(f"Indexed: {file_name}")

# --- SEARCH LOGIC ---
@app.on_message(filters.text & filters.group)
async def group_search(client, message):
    query = message.text.lower().strip()
    if len(query) < 3: return
    cursor = files_col.find({"file_name": {"$regex": query}})
    results = await cursor.to_list(length=10)
    if results:
        buttons = []
        for f in results:
            size = round(f['file_size'] / (1024 * 1024), 2)
            buttons.append([InlineKeyboardButton(f"📂 {f['file_name'].title()} ({size}MB)", callback_data=f"get_{f['file_id']}")])
        await message.reply_text(f"🔍 **Results for:** `{query}`", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^get_"))
async def get_file(client, query: CallbackQuery):
    try:
        await client.send_cached_media(chat_id=query.from_user.id, file_id=query.data.split("_")[1])
        await query.answer("Check your PM!", show_alert=True)
    except:
        await query.answer("Please START the bot in private first!", show_alert=True)

# --- RUN ---
async def main():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    logger.info("Bot is Live!")
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
