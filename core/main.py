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
telebot.logger.setLevel(logging.INFO)
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