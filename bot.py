import os
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, CallbackContext
from utils import (
    run_backtest,
    get_status,
    get_last_trades,
    get_liquidation_data,
    generate_trade_signal,
    get_news,
    store_trade
)
from dotenv import load_dotenv

# Load env variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")

# Init bot & flask
bot = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, use_context=True)

# Timezone
os.environ["TZ"] = "Asia/Kolkata"

# Logging
logging.basicConfig(level=logging.INFO)

# Handlers
def start(update: Update, context: CallbackContext):
    update.message.reply_text("🤖 Welcome to LiquidBot! Type /menu to view commands.")

def menu(update: Update, context: CallbackContext):
    update.message.reply_text(
        "📋 Available Commands:\n"
        "/start - Welcome message\n"
        "/menu - Show all commands\n"
        "/backtest - Simulate trades from last 7 days\n"
        "/status - Show current strategy thresholds\n"
        "/last30 - Show last 30 trades\n"
        "/news - Show Bitcoin news\n"
    )

def backtest(update: Update, context: CallbackContext):
    result = run_backtest()
    update.message.reply_text(result)

def status(update: Update, context: CallbackContext):
    update.message.reply_text(get_status())

def last30(update: Update, context: CallbackContext):
    update.message.reply_text(get_last_trades())

def news(update: Update, context: CallbackContext):
    update.message.reply_text(get_news())

# Register handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("menu", menu))
dispatcher.add_handler(CommandHandler("backtest", backtest))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("last30", last30))
dispatcher.add_handler(CommandHandler("news", news))

# Signal checker
def check_signals():
    signal = generate_trade_signal()
    if signal:
        store_trade(signal)
        bot.send_message(chat_id=OWNER_CHAT_ID, text=signal)

# Webhook
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "Bot is live!"

if __name__ == "__main__":
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
