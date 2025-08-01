import os
import json
import sqlite3
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters
from utils import (
    run_backtest, get_last_trades, train_strategy,
    get_logs, get_status, get_liquidation_data,
    get_news, generate_trade_signal, store_trade
)
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Set timezone to IST
os.environ["TZ"] = "Asia/Kolkata"

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Telegram bot
bot = Bot(token=TOKEN)
app = Flask(__name__)

# Dispatcher setup
dispatcher = Dispatcher(bot, None, workers=4)

# Database
conn = sqlite3.connect("trade_logs.db", check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    time TEXT, direction TEXT, price REAL, result TEXT,
    rsi INTEGER, wick REAL, liquidation_usd REAL, confidence REAL
)''')
conn.commit()

# Handlers
def start(update: Update, context):
    update.message.reply_text("Welcome! Type /menu to view all commands.")

def menu(update: Update, context):
    update.message.reply_text("""Available Commands:
/menu - Show this menu
/backtest - Simulate trades from last 7 days
/last10 - Show last 10 live trades
/train - Retrain strategy from history
/logs - Today's trade logs
/status - View strategy thresholds
/liqcheck - Test Coinglass API
/news - Show recent BTC news
""")

def backtest(update: Update, context):
    result = run_backtest()
    update.message.reply_text(result)

def last10(update: Update, context):
    update.message.reply_text(get_last_trades())

def train(update: Update, context):
    result = train_strategy()
    update.message.reply_text(result)

def logs(update: Update, context):
    update.message.reply_text(get_logs())

def status(update: Update, context):
    update.message.reply_text(get_status())

def liqcheck(update: Update, context):
    update.message.reply_text(get_liquidation_data())

def news(update: Update, context):
    update.message.reply_text(get_news())

# Register handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("menu", menu))
dispatcher.add_handler(CommandHandler("backtest", backtest))
dispatcher.add_handler(CommandHandler("last10", last10))
dispatcher.add_handler(CommandHandler("train", train))
dispatcher.add_handler(CommandHandler("logs", logs))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("liqcheck", liqcheck))
dispatcher.add_handler(CommandHandler("news", news))

# Webhook route
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

# Root route
@app.route("/")
def index():
    return "Bot is running!"

# Set webhook
if __name__ == "__main__":
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))