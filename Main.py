import logging
import os
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- LOGGING SETUP ---
# This will show exactly what is happening in your Render logs
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
ADMIN_ID =  6783893816 # Change this to your Telegram User ID (Get it from @MissRose_bot using /id)

# --- WEB SERVER (Required for Render Health Check) ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot Server is Online and Healthy!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting Web Server on port {port}")
    web_app.run(host='0.0.0.0', port=port)

# --- BOT INITIALIZATION ---
app = Client(
    "Indra_Filter_Bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True  # Avoids session file database locks on Render
)

# --- DATABASE SETUP ---
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["AutoFilterBot"]
files_col = db["files"]

# --- HANDLERS ---

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    logger.info(f"Start command received from user: {message.from_user.id}")
    text = (
        f"Hello **{message.from_user.first_name}**!\n\n"
        "I am an Advanced Auto Filter Bot. Add me to your group, "
        "and I will provide files based on the names you search for.\n\n"
        "**Main Features:**\n"
        "1. Automatic search in groups\n"
        "2. Private file delivery\n"
        "3. High-speed indexing"
    )
    buttons = [[
        InlineKeyboardButton("➕ Add Me to Group ➕", url=f"http://t.me/{client.me.username}?startgroup=true")
    ]]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command("index") & filters.private)
async def index_files(client, message):
    """Admin command to index channel files into the database"""
    if message.from_user.id != ADMIN_ID:
        return
    
    if len(message.command) < 2:
        return await message.reply_text("Usage: `/index @ChannelUsername`")
    
    chat_id = message.command[1]
    msg = await message.reply_text("🔄 Indexing started... Please wait.")
    
    count = 0
    try:
        async for user_msg in client.get_chat_history(chat_id):
            file = user_msg.document or user_msg.video or user_msg.audio
            if file:
                file_name = getattr(file, "file_name", "Untitled")
                # Save to MongoDB
                exists = await files_col.find_one({"file_name": file_name.lower(), "file_size": file.file_size})
                if not exists:
                    await files_col.insert_one({
                        "file_id": file.file_id,
                        "file_name": file_name.lower(),
                        "file_size": file.file_size
                    })
                    count += 1
        await msg.edit(f"✅ Indexing Complete! Added **{count}** new files to the database.")
    except Exception as e:
        await msg.edit(f"❌ Error: {str(e)}")

@app.on_message(filters.text & filters.group)
async def auto_filter(client, message):
    """Search files in the database when someone types in a group"""
    query = message.text.lower().strip()
    if len(query) < 3:
        return

    logger.info(f"Searching for: {query} in group: {message.chat.id}")
    cursor = files_col.find({"file_name": {"$regex": query}})
    results = await cursor.to_list(length=10)
    
    if results:
        buttons = []
        for file in results:
            size_mb = round(file['file_size'] / (1024 * 1024), 2)
            btn_text = f"📂 {file['file_name'].title()} ({size_mb} MB)"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"get_{file['file_id']}")])
        
        await message.reply_text(
            f"🔍 Results found for: **{query}**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

@app.on_callback_query(filters.regex(r"^get_"))
async def deliver_file(client, query: CallbackQuery):
    """Sends the actual file to the user's PM when they click a button"""
    file_id = query.data.split("_")[1]
    try:
        await client.send_cached_media(
            chat_id=query.from_user.id, 
            file_id=file_id,
            caption="✅ Here is your file! Request more in the group."
        )
        await query.answer("Check your Inbox (PM)! I have sent the file.", show_alert=True)
    except Exception:
        await query.answer("Please START the bot in private first!", show_alert=True)

# --- EXECUTION LOGIC ---

async def main():
    # Start the Flask Web Server in a background thread
    Thread(target=run_flask, daemon=True).start()
    
    # Initialize and start the Telegram Bot
    logger.info("Connecting to Telegram...")
    await app.start()
    
    # Get Bot details to verify connection
    bot_info = await app.get_me()
    logger.info(f"✅ SUCCESS: Bot is online as @{bot_info.username}")
    
    # Keep the bot running indefinitely
    await idle()
    
    # Graceful shutdown
    await app.stop()

if __name__ == "__main__":
    # Correct way to handle async loop in Python 3.10+
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
    except Exception as e:
        logger.error(f"Fatal error during execution: {e}")
