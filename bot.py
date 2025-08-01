
import os
from dotenv import load_dotenv
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
import logging

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

if not TOKEN or not WEBHOOK_URL:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or WEBHOOK_URL")

bot = Bot(token=TOKEN)
app = Flask(__name__)

dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

# Command handlers
def start(update, context):
    update.message.reply_text("✅ Bot is live. Use /menu to see available commands.")

def menu(update, context):
    commands = (
        "/start - Check if bot is online\n"
        "/menu - List all commands\n"
        "/status - Show current strategy thresholds\n"
        "/results - Show recent signal stats\n"
        "/logs - View logged trades\n"
        "/last30 - Show last 30 trades\n"
        "/backtest - Run backtest on past 7 days\n"
        "/news - Get latest Bitcoin-related news\n"
    )
    update.message.reply_text(f"📋 Available Commands:\n{commands}")

# Register handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("menu", menu))
dispatcher.add_handler(CommandHandler("status", lambda u, c: u.message.reply_text("ℹ️ Strategy status coming soon.")))
dispatcher.add_handler(CommandHandler("results", lambda u, c: u.message.reply_text("📊 Results not implemented yet.")))
dispatcher.add_handler(CommandHandler("logs", lambda u, c: u.message.reply_text("📄 Logs placeholder.")))
dispatcher.add_handler(CommandHandler("last30", lambda u, c: u.message.reply_text("🕒 Showing last 30 trades...")))
dispatcher.add_handler(CommandHandler("backtest", lambda u, c: u.message.reply_text("🔁 Running backtest...")))
dispatcher.add_handler(CommandHandler("news", lambda u, c: u.message.reply_text("📰 Latest news placeholder...")))

# Webhook route
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

# Root test route
@app.route("/", methods=["GET"])
def index():
    return "Bot is running."

if __name__ == "__main__":
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    logging.info(f"✅ Webhook set: {WEBHOOK_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=10000)
