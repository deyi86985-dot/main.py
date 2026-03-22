import logging
import os
import asyncio
import re
import difflib
import sys
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
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

OWNER_ID = 6783893816 
CHANNEL_ID = -1003065768519 

DELETE_WARNING = "⚠️ ❌👉This file automatically❗delete after 2 minute❗so please forward in another chat👈❌"

RULES_MSG = """🄰🅃🅃🄴🄽🅃🄸🄾🄽 🄷🄴🅁🄴
𝐌𝐎𝐕𝐈𝐄/𝐒𝐄𝐑𝐈𝐄𝐒 𝐒𝐄𝐀𝐑𝐂𝐇 𝐑𝐔𝐋𝐄𝐒 🍿

◉ ᴀʟᴡᴀʏꜱ ᴜꜱᴇ ᴄᴏʀʀᴇᴄᴛ ꜱᴘᴇʟʟɪɴɢ.
◉ ꜱᴇᴀʀᴄʜ ᴍᴏᴠɪᴇꜱ ʟɪᴋᴇ ᴛʜɪꜱ :- ꜱᴀʟᴀᴀʀ 2023 ✔️
◉ ꜱᴇᴀʀᴄʜ ꜱᴇʀɪᴇꜱ ʟɪᴋᴇ ᴛʜɪꜱ :- ᴠɪᴋɪɴɢꜱ ꜱ01 ✔️"""

# --- DATABASE HANDLER ---
class Database:
    def __init__(self, url):
        self._client = AsyncIOMotorClient(url)
        self.db = self._client["CINESOCIETY_ULTRA_V1"]
        self.files = self.db["files"]
        self.admins = self.db["admins"]

    async def add_admin(self, user_id):
        await self.admins.update_one({"user_id": user_id}, {"$set": {"user_id": user_id}}, upsert=True)

    async def is_admin(self, user_id):
        if user_id == OWNER_ID: return True
        return await self.admins.find_one({"user_id": user_id}) is not None

    async def save_file(self, file_id, file_name, file_size, caption):
        clean_name = re.sub(r'[_.\-]', ' ', file_name).lower().strip()
        f_name = file_name.lower().strip()
        # চেক করা হচ্ছে ফাইলটি অলরেডি আছে কি না
        if not await self.files.find_one({"file_name": f_name, "file_size": file_size}):
            await self.files.insert_one({
                'file_id': file_id, 
                'file_name': f_name, 
                'clean_name': clean_name, 
                'file_size': file_size,
                'caption': caption or f_name.upper()
            })
            return True
        return False

    async def get_all_names(self):
        cursor = self.files.find({}, {"file_name": 1})
        res = await cursor.to_list(length=15000)
        return [f['file_name'] for f in res]

db = Database(MONGO_URI)

# --- WEB SERVER (For Deployment) ---
web_app = Flask(__name__)
@web_app.route('/')
def home(): return "RDX Ultra Pro is Running! 🚀"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

app = Client("RDX_MASTER_PRO", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- HELPERS ---
def format_btn(filename):
    res_match = re.search(r'(480p|720p|1080p|2160p|4k)', filename, re.I)
    res = res_match.group(0).upper() if res_match else "HD"
    year_match = re.search(r'(19|20)\d{2}', filename)
    year = year_match.group(0) if year_match else ""
    clean = re.sub(r'(480p|7
