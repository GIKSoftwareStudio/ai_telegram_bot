import telebot
from telebot import TeleBot
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
from datetime import datetime, timedelta
telebot.logger.setLevel(logging.INFO)
import re
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import threading
from openai import APITimeoutError, APIConnectionError, APIStatusError
from requests.exceptions import Timeout, ConnectionError, HTTPError, RequestException
user_click_cooldown = {}
user_click_lock = threading.Lock()
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
print("Telegram API key loaded:", bool(OPENAI_API_KEY))
print("Telegram Base URL:", OPENAI_BASE_URL)
if not BOT_TOKEN:
    raise ValueError("خطا: توکن ربات تلگرام (BOT_TOKEN) در فایل .env یافت نشد!")
bot = telebot.TeleBot(BOT_TOKEN)
DB_NAME = "chat_history.db"
user_chat_active = set()
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
def create_welcome_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🚀 شروع گفتگو با مدل", callback_data="start_chat"),
               InlineKeyboardButton("⚙️ Settings", callback_data="open_settings"),
               InlineKeyboardButton("🌐 زبان / Language", callback_data="open_languages")
            )
    return markup



def create_settings_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "⬅️ بازگشت",
            callback_data="back_to_welcome"
        )
    )
    return markup




def create_languages_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(
            "🇮🇷 فارسی",
            callback_data="language_fa"
        ),
        InlineKeyboardButton(
            "🇬🇧 English",
            callback_data="language_en"
        ),
        InlineKeyboardButton(
            "⬅️ بازگشت",
            callback_data="back_to_welcome"
        )
    )
    return markup







def clear_user_history_db(user_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM message WHERE user_id = ?", (str(user_id),))
    conn.commit()
    conn.close()




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
         SELECT role, content
    FROM (
        SELECT id, role, content
        FROM message
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    )
    ORDER BY id ASC
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
@bot.message_handler(commands=["start"])
def start_command(message):
    user_id = message.from_user.id
    user_chat_active.discard(user_id)
    bot.send_message(
        message.chat.id,
        "سلام! 👋\n"
        "به دستیار هوش مصنوعی خوش اومدی.\n\n"
        "برای شروع، یکی از گزینه‌های زیر رو انتخاب کن:",
        reply_markup = create_welcome_keyboard()
    )
                     

@bot.message_handler(content_types=["text"])
def handle_message(message):
    user_id = message.from_user.id
    user_text = message.text
    if user_id not in user_chat_active:
        bot.reply_to(
            message,
        "برای شروع گفتگو، ابتدا دستور /start رو بزن."
        )
        return
    if not user_text:
        bot.reply_to(message, "لطفاً یک پیام متنی ارسال کنید.")
        return
    if "پشتیبانی" in user_text:
        bot.reply_to(message, "" )
        return
    bot.send_chat_action(chat_id=user_id, action="typing")
    history = get_user_history(str(user_id), limit=10)
    history.append({
        "role": "user",
        "content": user_text
    })

    save_message(str(user_id), "user", user_text)
    stop_typing = threading.Event()
    def typing_background_loop():
        while not stop_typing.is_set():
            try:
                bot.send_chat_action(chat_id=user_id, action="typing")
            except Exception:
                pass
            stop_typing.wait(4.5)
    typing_thread = threading.Thread(target=typing_background_loop)
    typing_thread.start()
    print("ENV URL:", repr(os.getenv("OPENAI_BASE_URL")))
    print("REQUEST URL:", repr(OPENAI_BASE_URL))
    try:
        response = requests.post(
            OPENAI_BASE_URL,
            json={
                "messages": history,
                "user_id":str(user_id)
            },
            timeout=90
        )
        print("STATUS CODE:", response.status_code)
        print("RESPONSE BODY:", response.text[:3000])
        response.raise_for_status()
        data = response.json()
        ai_reply = data["choices"][0]["message"]["content"]
        if not ai_reply:
            ai_reply = "didnt get response from server"
        save_message(str(user_id), "assistant", ai_reply)
        
    except APITimeoutError:
        logger.warning("AI API timeout error occurred.")
        ai_reply = "server took too Long to respond, please try again Later"
    except APIConnectionError:
        logger.exception("AI API connection error")
        ai_reply = "server error please try again Later"
    except APIStatusError as e:
        logger.exception("AI API HTTP error: %s", e.status_code)
        ai_reply = f"an error occurred while processing your request {str(e)}"
    except Exception as e:
        logger.exception("Unexpected error")
        ai_reply = "an unexpected error occurred, please try again Later"
        print(f"ERROR TYPE: {type(e).__name__}")
        print(f"ERROR DETAILS: {e!r}")
    finally:
        stop_typing.set() 
        typing_thread.join(timeout=2)
    try:
        sanitized_reply = escape_markdown_v2(ai_reply)
        # this part should be fix 
    except Exception:
        bot.reply_to(message)
    


def escape_markdown_v2(text: str) -> str:
    link_pattern = r'\[([^\]]+)\]\((https?://[^)\s]+)\)'
    
    parts = re.split(r'(```[\s\S]*?```|`[^`]*`|' + link_pattern + r')', text)
    escaped_parts = []
    escape_chars = r'_*[]()~`>#+-=|{}.!\\'

    for i, part in enumerate(parts):
        if not part:
            continue
        if part.startswith('```') or part.startswith('`'):
            escaped_parts.append(part)
        elif part.startswith('[') and '](' in part:
            match = re.match(link_pattern, part)
            if match:
                link_text, link_url = match.groups()
                escaped_text = re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', link_text)
                escaped_parts.append(f"[{escaped_text}]({link_url})")
            else:
                escaped_parts.append(part)
        else:
            escaped = re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', part)
            escaped_parts.append(escaped)

    return "".join(escaped_parts)
@bot.callback_query_handler(func=lambda call:True)
def handle_callback_query(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    action = call.data
    bot.answer_callback_query(call.id)
    if action == "start_chat":
        user_chat_active.add(user_id)
        try:
            bot.delete_message(chat_id, message_id)
        except Exception:
            pass
        bot.send_message(
            chat_id,
            "💬 گفتگو با مدل شروع شد!\n"
            "پیامت رو ارسال کن."
        )
    elif action == "open_settings":
        bot.edit_message_text(
            "⚙️ پنل تنظیمات\n\n"
            "گزینه‌های این بخش رو بعداً اضافه می‌کنیم.",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=create_settings_keyboard()
        )
    elif action == "open_languages":
        bot.edit_message_text(
            "🌐 انتخاب زبان / Choose language\n\n"
            "این بخش فعلاً غیرفعاله.",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=create_languages_keyboard()
        )
    elif action == "back_to_welcome":
        bot.edit_message_text(
             "سلام! 👋\n"
            "به دستیار هوش مصنوعی خوش اومدی.\n\n"
            "برای شروع، یکی از گزینه‌های زیر رو انتخاب کن:",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=create_welcome_keyboard()
        )
    elif action in ("language_fa", "language_en"):
        bot.answer_callback_query(
            call.id,
            text="این قابلیت فعلاً غیرفعاله."
        )


if __name__ == "__main__":
    init_db()
    print("Bot is running...")
    bot.infinity_polling()

