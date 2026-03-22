import logging
import os
import asyncio
import re
import time
import difflib
from datetime import datetime
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import UserNotParticipant, FloodWait, ChatAdminRequired
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
from flask import Flask
from threading import Thread

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
API_ID = 33841378
API_HASH = "b0cd560d2550670d137bb828439d25fd"
BOT_TOKEN = "8718472144:AAE35OGiq_KlOXZ78DIuzr7oRQNqcUGQXtw"
MONGO_URI = "mongodb+srv://Indrajit12345:Indrajit12345@cluster0.k4l475p.mongodb.net/?appName=Cluster0"

ADMIN_ID = 6783893816
OWNER_ID = 6783893816
CHANNEL_ID = -1003065768519 
app = Client("FilterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- START COMMAND & IMAGE ---
START_IMG = "https://telegra.ph/file/your-image-link.jpg"
START_MSG = "Hello {user}, I am a Movie Filter Bot. Add me to your group!"

@app.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    await message.reply_photo(
        photo=START_IMG,
        caption=START_MSG.format(user=message.from_user.mention),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Add me to Group", url="http://t.me/your_bot?startgroup=true")
        ]])
    )

# --- INDEXING FUNCTION (Get History) ---
@app.on_message(filters.command("index") & filters.user(OWNER_ID))
async def index_files(bot, message):
    await message.reply_text("Indexing started... Please wait.")
    async for msg in bot.get_chat_history(CHANNEL_ID):
        if msg.document or msg.video:
            file_name = msg.document.file_name if msg.document else msg.video.file_name
            file_id = msg.document.file_id if msg.document else msg.video.file_id
            if file_name:
                # Save to MongoDB
                await files_col.update_one(
                    {"file_id": file_id},
                    {"$set": {"file_name": file_name.lower(), "file_id": file_id}},
                    upsert=True
                )
    await message.reply_text("Indexing Complete!")

# --- FILTER LOGIC ---
@app.on_message(filters.text & (filters.group | filters.private))
async def filter_bot(bot, message):
    query = message.text.lower()
    
    # Search in Database
    cursor = files_col.find({"file_name": {"$regex": query}})
    results = await cursor.to_list(length=10)

    if results:
        buttons = []
        for file in results:
            # Create buttons for each result
            buttons.append([InlineKeyboardButton(f"🎬 {file['file_name'].upper()}", callback_data=f"file_{file['file_id']}")])
        
        await message.reply_text(
            f"Hey {message.from_user.mention}, I found these results for: **{query}**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        # If no result found
        instruction_text = (
            "🄼🄰🅈🄱🄴 🅈🄾🅄 🅂🄿🄴🄻🄻🄴🄳 🄸🅃 🅆🅁🄾🄽🄶\n"
            "🄰🅃🅃🄴🄽🅃🄸🄾🄽 🄷🄴🅁🄴\n"
            "𝐌𝐎𝐕𝐈𝐄/𝐒𝐄𝐑𝐈𝐄𝐒 𝐒𝐄𝐀𝐑𝐂𝐇 𝐑𝐔𝐋𝐄𝐒 🍿\n\n"
            "◉ ᴀʟᴡᴀʏꜱ ᴜꜱᴇ ᴄᴏʀʀᴇᴄᴛ ꜱᴘᴇʟʟɪɴɢ. ʏᴏᴜ ᴄᴀɴ ꜰɪɴᴅ ʀɪɢʜᴛ ꜱᴘᴇʟʟɪɴɢ ꜰʀᴏᴍ google.com\n\n"
            "◉ ꜱᴇᴀʀᴄʜ ᴍᴏᴠɪᴇꜱ ʟɪᴋᴇ ᴛʜɪꜱ :-\n"
            "› ꜱᴀʟᴀᴀʀ 2023 ✔️\n"
            "› ꜱᴀʟᴀᴀʀ ʜɪɴᴅɪ ✔️\n"
            "› ꜱᴀʟᴀᴀʀ ᴍᴏᴠɪᴇ ❌\n\n"
            "I couldn't find any file plz sms to @CINESOCIETY_BOT"
        )
        await message.reply_text(instruction_text)

# --- CALLBACK FOR SENDING FILE & AUTO-DELETE ---
@app.on_callback_query(filters.regex(r"^file_"))
async def send_file(bot, query):
    file_id = query.data.split("_")[1]
    
    # Send file to User PM
    try:
        sent_file = await bot.send_cached_media(chat_id=query.from_user.id, file_id=file_id)
        await query.answer("File sent to your PM!", show_alert=True)
        
        # Auto-delete after 2 minutes (120 seconds)
        await asyncio.sleep(120)
        await bot.delete_messages(chat_id=query.from_user.id, message_ids=sent_file.id)
    except Exception:
        await query.answer("Please Start the bot in PM first!", show_alert=True)

app.run()
