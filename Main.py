import logging
import os
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

# IMPORTANT: Ekhane apnar nijer Telegram ID boshon (ID pete @MissRose_bot e /id likhun)
ADMIN_ID = 6783893816 # Replace with your ID

# --- DATABASE SETUP ---
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["RDX_Filter_Bot"]
files_col = db["files"]
settings_col = db["settings"]

# --- WEB SERVER (For Render) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "RDX Auto Filter is Online!"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- BOT INITIALIZATION ---
app = Client("RDX_Bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- SETTINGS HELPERS ---
async def get_setting(key, default):
    data = await settings_col.find_one({"key": key})
    return data["value"] if data else default

async def set_setting(key, value):
    await settings_col.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

# --- HANDLERS ---

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    # Dynamic settings load
    start_text = await get_setting("start_text", "👋 **Hello! I am a Powerful Auto Filter Bot.**")
    start_img = await get_setting("start_img", "https://telegra.ph/file/default_image.jpg")
    
    buttons = [
        [InlineKeyboardButton("📢 Updates", url="https://t.me/YourChannel"),
         InlineKeyboardButton("🛠 Support", url="https://t.me/YourSupport")],
        [InlineKeyboardButton("➕ Add Me to Your Group ➕", url=f"http://t.me/{client.me.username}?startgroup=true")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about"),
         InlineKeyboardButton("💰 Earn Money", callback_data="earn")]
    ]
    
    try:
        await message.reply_photo(photo=start_img, caption=start_text, reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await message.reply_text(start_text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command("setstart") & filters.user(ADMIN_ID))
async def set_start_text(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/setstart Your New Welcome Message`")
    new_text = message.text.split(None, 1)[1]
    await set_setting("start_text", new_text)
    await message.reply_text("✅ **Start Message updated successfully!**")

@app.on_message(filters.command("setimg") & filters.user(ADMIN_ID))
async def set_start_img(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/setimg Image_URL_Link`")
    new_img = message.command[1]
    await set_setting("start_img", new_img)
    await message.reply_text("✅ **Start Image updated successfully!**")

@app.on_message(filters.command("index") & filters.user(ADMIN_ID))
async def index_files(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/index @ChannelUsername`")
    
    target = message.command[1]
    status = await message.reply_text("🔄 **Indexing started... Please wait.**")
    
    count = 0
    try:
        async for user_msg in client.get_chat_history(target):
            file = user_msg.document or user_msg.video or user_msg.audio
            if file:
                file_name = getattr(file, "file_name", "Untitled").lower()
                exists = await files_col.find_one({"file_name": file_name, "file_size": file.file_size})
                if not exists:
                    await files_col.insert_one({
                        "file_id": file.file_id,
                        "file_name": file_name,
                        "file_size": file.file_size
                    })
                    count += 1
        await status.edit(f"✅ **Indexing Complete!**\nTotal **{count}** files added to database.")
    except Exception as e:
        await status.edit(f"❌ **Error:** {str(e)}\n\n*Make sure the bot is Admin in that channel.*")

@app.on_message(filters.text & filters.group)
async def group_search(client, message):
    query = message.text.lower().strip()
    if len(query) < 3: return

    cursor = files_col.find({"file_name": {"$regex": query}})
    results = await cursor.to_list(length=10)
    
    if results:
        buttons = []
        for file in results:
            size = round(file['file_size'] / (1024 * 1024), 2)
            btn_text = f"📂 {file['file_name'].title()} ({size} MB)"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"get_{file['file_id']}")])
        
        await message.reply_text(
            f"🔍 **Results for:** `{query}`\n\nFound {len(results)} files in database.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

@app.on_callback_query(filters.regex(r"^get_"))
async def deliver_file(client, query: CallbackQuery):
    file_id = query.data.split("_")[1]
    try:
        await client.send_cached_media(chat_id=query.from_user.id, file_id=file_id, caption="✅ **Here is your requested file!**")
        await query.answer("Check your PM! File sent.", show_alert=True)
    except:
        await query.answer("Please START the bot in private first!", show_alert=True)

# --- RUN BOT ---
async def start_rdx():
    Thread(target=run_flask, daemon=True).start()
    await app.start()
    bot_info = await app.get_me()
    logger.info(f"🚀 @{bot_info.username} is Online!")
    await idle()
    await app.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_rdx())
