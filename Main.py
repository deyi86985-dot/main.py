import logging
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread

# --- WEB SERVER FOR RENDER (Keep Alive) ---
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is Running!"

def run_web():
    # Render default port 10000 ব্যবহার করে
    app_web.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- CONFIGURATION ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

# --- BOT SETUP ---
db_client = AsyncIOMotorClient(MONGO_URI)
db = db_client["AutoFilterBot"]
files_col = db["files"]

bot = Client(
    "IndrajitBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply_text("👋 Hello! Ami Render-e host kora ekti Auto Filter Bot.")

# Filter logic (Same as before)
@bot.on_message(filters.text & filters.group)
async def search(client, message):
    query = message.text
    if len(query) < 3: return
    cursor = files_col.find({"file_name": {"$regex": query.lower()}})
    results = await cursor.to_list(length=5)
    if results:
        btn = [[InlineKeyboardButton(f"📂 {f['file_name']}", callback_data=f"get_{f['file_id']}")] for f in results]
        await message.reply_text(f"Results for: {query}", reply_markup=InlineKeyboardMarkup(btn))

if __name__ == "__main__":
    # Web server start kora background thread-e
    Thread(target=run_web).start()
    print("🚀 Bot starting on Render...")
    bot.run()
