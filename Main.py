import logging
import os
import asyncio
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
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

# --- WEB SERVER (For Render) ---
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "Bot is Alive and Running!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- BOT CLIENT ---
app = Client(
    "IndrajitBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- DATABASE ---
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["AutoFilterBot"]
files_col = db["files"]

@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply_text(f"👋 Hello {message.from_user.first_name}!\nAmi Render-e safollobhabe run hyechi.")

@app.on_message(filters.text & filters.group)
async def group_search(client, message):
    query = message.text
    if len(query) < 3: return
    
    cursor = files_col.find({"file_name": {"$regex": query.lower()}})
    results = await cursor.to_list(length=5)
    
    if results:
        buttons = []
        for file in results:
            buttons.append([InlineKeyboardButton(f"📂 {file['file_name']}", callback_data=f"get_{file['file_id']}")])
        await message.reply_text(f"Search Results for: {query}", reply_markup=InlineKeyboardMarkup(buttons))

# --- MAIN RUNNER ---
async def main():
    # Flask start in a separate thread
    Thread(target=run_flask, daemon=True).start()
    
    # Start the Pyrogram client
    await app.start()
    print("🚀 Bot Started Successfully!")
    
    # Keep the bot running
    await idle()
    
    # Stop the bot properly
    await app.stop()

if __name__ == "__main__":
    # Modern way to run asyncio in Python 3.10+
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
