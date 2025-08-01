
import os
import logging
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext, Dispatcher
from flask import Flask, request
from dotenv import load_dotenv

# Load .env if exists
load_dotenv()

# Logging setup
logging.basicConfig(
    format='[%(levelname)s] %(message)s',
    level=logging.INFO
)

# Read environment variables safely
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TOKEN:
    logging.error("TELEGRAM_BOT_TOKEN not set in environment.")
    exit(1)
if not WEBHOOK_URL:
    logging.error("WEBHOOK_URL not set in environment.")
    exit(1)

# Boot logs
logging.info("Starting bot with webhook URL: %s", WEBHOOK_URL)

# Bot setup
bot = Bot(token=TOKEN)
updater = Updater(bot=bot, use_context=True)
dispatcher: Dispatcher = updater.dispatcher

# Define a simple command
def start(update: Update, context: CallbackContext):
    update.message.reply_text("🚀 Bot is live and running!")

dispatcher.add_handler(CommandHandler("start", start))

# Flask app for webhook
app = Flask(__name__)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK"

# Set webhook
try:
    bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")
    logging.info("Webhook set successfully.")
except Exception as e:
    logging.error("Failed to set webhook: %s", e)
    exit(1)

# Flask run for Render (port is managed automatically)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
