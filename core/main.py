import telebot
import os
from dotenv import load_dotenv
from openai import OpenAI
from telebot import apihelper
import pprint
import json
import logging
logger = telebot.logger
import requests
import sqlite3
from datetime import datetime
telebot.logger.setLevel(logging.INFO)
import re
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPEN_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
if not BOT_TOKEN:
    raise ValueError("خطا: توکن ربات تلگرام (BOT_TOKEN) در فایل .env یافت نشد!")
bot = telebot.TeleBot(BOT_TOKEN)
if OPENAI_BASE_URL:
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL
    )
else:
    client = OpenAI(
        api_key=OPENAI_API_KEY
    )
print("Bot and AI clients are ready...")






DB_NAME = "chat_history.db"
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS message(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL
    )
""")
    conn.commit()
    conn.close()
def save_message(user_id: str, role: str, content: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO message (user_id, role, content, timestamp)
        VALUES (?, ?, ?, ?)

    """, (str(user_id), role, content, timestamp))
    conn.commit()
    conn.close()
def get_user_history(user_id: str, limit: int = 10):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM (
            SELECT role, content, timestamp
            FROM message
            WHERE user_id = ? 
            ORDER BY id DESC
            LIMIT ?
        ) ORDER BY id ASC  

    """, (str(user_id), limit))
    rows = cursor.fetchall()
    conn.close()
    history = []
    for row in rows:
        history.append({
            "role": row[0],
            "content": row[1]
        })
    return history

@bot.message_handler(func= lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text
    bot.send_chat_action(chat_id=user_id, action="typing")
    history = get_user_history(str(user_id), limit=10)
    history.append({
        "role": "user",
        "content": user_text
    })

    save_message(str(user_id), "user", user_text)
    try:
        response = client.chat.completions.create(
            model="gen-lang-client-0049376852",
            messages=history
        )
        ai_reply = response.choices[0].message.content
        save_message(str(user_id), "assistant", ai_reply)
        sanitized_reply = escape_markdown_v2(ai_reply)
        bot.reply_to(message, sanitized_reply, parse_mode='MarkdownV2')
    except Exception as e:
        bot.reply_to(message, ai_reply)


def escape_markdown_v2(text: str) -> str:
    parts = re.split(r'(```[\s\S]*?```|`[^`]*`)', text)
    escaped_parts = []
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for i, part in enumerate(parts):
        if i % 2 == 1:
            escaped_parts.append(part)
        else:
            escaped = re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', part)
            escaped_parts.append(escaped)
    return "".join(escaped_parts)


if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()

