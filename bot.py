import os
import logging
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Dispatcher, CommandHandler, CallbackContext
from utils import analyze_market, train_model, get_logs, get_status, get_news

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=4, use_context=True)

logging.basicConfig(level=logging.INFO)

# Command handlers
def start(update: Update, context: CallbackContext):
    update.message.reply_text("🚀 Liquidation Rebound Bot is active.")

def train(update: Update, context: CallbackContext):
    result = train_model()
    update.message.reply_text(f"Model retrained. 📈\n{result}")

def logs(update: Update, context: CallbackContext):
    result = get_logs()
    update.message.reply_text(result)

def status(update: Update, context: CallbackContext):
    result = get_status()
    update.message.reply_text(result)

def news(update: Update, context: CallbackContext):
    result = get_news()
    update.message.reply_text(result)

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("train", train))
dispatcher.add_handler(CommandHandler("logs", logs))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("news", news))

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
