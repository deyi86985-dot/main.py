import logging
import os
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

# IMPORTANT: Set your Channel ID here (where your files are stored)
# You can get this ID by forwarding a message from the channel to @MissRose_bot
CHANNEL_ID = -1002447915570 

# --- WEB SERVER FOR RENDER ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is Running and Healthy!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Web server starting on port {port}")
    web_app.run(host='0.0.0.0', port=port)

# --- BOT INITIALIZATION ---
app = Client(
    "Indra_Simple_Filter",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# --- DATABASE SETUP ---
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["AutoFilterBot"]
files_col = db["files"]

# --- 1. AUTOMATIC INDEXING (Saves files from your channel) ---
@app.on_message(filters.chat(CHANNEL_ID) & (filters.document | filters.video | filters.audio))
async def auto_index_handler(client, message):
    file = message.document or message.video or message.audio
    file_name = getattr(file, "file_name", "Untitled").lower()
    
    # Check if file already exists in database
    exists = await files_col.find_one({"file_name": file_name, "file_size": file.file_size})
    
    if not exists:
        await files_col.insert_one({
            "file_id": file.file_id,
            "file_name": file_name,
            "file_size": file.file_size
        })
        logger.info(f"Successfully Indexed: {file_name}")

# --- 2. GROUP SEARCH HANDLER ---
@app.on_message(filters.text & filters.group)
async def search_handler(client, message):
    query = message.text.lower().strip()
    if len(query) < 3:
        return

    logger.info(f"Searching for: {query} in group {message.chat.id}")
    
    # Search using regex for partial matches
    cursor = files_col.find({"file_name": {"$regex": query}})
    results = await cursor.to_list(length=10)
    
    if results:
        buttons = []
        for file in results:
            size_mb = round(file['file_size'] / (1024 * 1024), 2)
            btn_text = f"📂 {file['file_name'].title()} ({size_mb} MB)"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"get_{file['file_id']}")])
        
        await message.reply_text(
            f"🔍 Results for: **{query}**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# --- 3. FILE DELIVERY (Callback Query) ---
@app.on_callback_query(filters.regex(r"^get_"))
async def delivery_handler(client, query: CallbackQuery):
    file_id = query.data.split("_")[1]
    try:
        await client.send_cached_media(
            chat_id=query.from_user.id,
            file_id=file_id,
            caption="✅ Here is the file you requested!"
        )
        await query.answer("Check your PM! I have sent the file.", show_alert=True)
    except Exception:
        await query.answer("Please START the bot in private (PM) first!", show_alert=True)

# --- 4. START COMMAND ---
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    await message.reply_text(
        f"Hello {message.from_user.first_name}!\n\n"
        "I am an Auto Filter Bot. Add me to your group and I will search files from my database automatically."
    )

# --- MAIN EXECUTION ---
async def start_bot():
    # Start the Flask web server
    Thread(target=run_flask, daemon=True).start()
    
    # Start the Telegram Client
    await app.start()
    me = await app.get_me()
    logger.info(f"✅ SUCCESS: @{me.username} is now online!")
    
    # Keep the bot running
    await idle()
    
    # Stop correctly
    await app.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_bot())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal Error: {e}")
