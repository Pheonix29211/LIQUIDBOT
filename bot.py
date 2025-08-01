
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

dispatcher = Dispatcher(bot, None, use_context=True)

# Telegram commands
def start(update, context):
    update.message.reply_text("Welcome to LiquidBot!\nType /menu to view all available commands.")

def menu(update, context):
    update.message.reply_text("Available Commands:\n"
                              "/menu - Show this menu\n"
                              "/start - Start the bot\n"
                              "/backtest - Run a 7-day backtest with trade details\n"
                              "/train - Retrain the strategy from past data\n"
                              "/status - Show current strategy parameters\n"
                              "/logs - Show recent logs\n"
                              "/results - Show strategy performance\n"
                              "/last30 - Show last 30 live trades (wins/losses)\n"
                              "/news - Show recent Bitcoin news headlines")

def backtest(update, context):
    result = run_backtest()
    update.message.reply_text(result)

def train(update, context):
    train_strategy()
    update.message.reply_text("Strategy retrained from past data.")

def status(update, context):
    status_msg = get_status()
    update.message.reply_text(status_msg)

def logs(update, context):
    log_data = get_logs()
    update.message.reply_text(log_data)

def results(update, context):
    try:
        with open("trades.txt", "r") as file:
            lines = file.readlines()[-30:]
        if not lines:
            update.message.reply_text("No trade data found.")
            return
        formatted = ""
        for line in lines:
            if "LONG" in line or "SHORT" in line:
                formatted += line
        update.message.reply_text("Last 30 Trades:\n" + formatted)
    except Exception as e:
        update.message.reply_text("Failed to load results.")

def last30(update, context):
    last = get_last_trades()
    update.message.reply_text(last)

def news(update, context):
    headlines = get_news()
    update.message.reply_text("Latest Bitcoin News:\n" + headlines)

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("menu", menu))
dispatcher.add_handler(CommandHandler("backtest", backtest))
dispatcher.add_handler(CommandHandler("train", train))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("logs", logs))
dispatcher.add_handler(CommandHandler("results", results))
dispatcher.add_handler(CommandHandler("last30", last30))
dispatcher.add_handler(CommandHandler("news", news))

# Signal checker
def check_signals():
    signal = generate_trade_signal()
    if signal:
        store_trade(signal)
        bot.send_message(chat_id=os.getenv("OWNER_CHAT_ID"), text=signal)

@app.route(f'/{TOKEN}', methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

if __name__ == "__main__":
    logging.info("Starting bot with webhook URL: %s", f"{WEBHOOK_URL}/{TOKEN}")
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=10000)
