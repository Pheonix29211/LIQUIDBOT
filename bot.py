import os
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
from dotenv import load_dotenv
from utils import (
    run_backtest,
    get_results_summary,
    get_last_trades,
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=TELEGRAM_BOT_TOKEN)

WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = Bot(token=TOKEN)
app = Flask(__name__)

dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

# --- Command Handlers ---

def start(update, context):
    update.message.reply_text("🚀 Welcome to LiquidBot!\nUse /menu to see available commands.")

def menu(update, context):
    commands = """
📋 Available Commands:
/start - Start the bot
/menu - Show this menu
/backtest - Simulate last 7 days of trades
/results - Show performance summary
/last30 - Show last 30 trades
"""
    update.message.reply_text(commands)

def backtest(update, context):
    result = run_backtest()
    update.message.reply_text(result or "No backtest data available.")

def results(update, context):
    summary = get_results_summary()
    update.message.reply_text(summary or "No results yet.")

def last30(update, context):
    trades = get_last_trades(30)
    if not trades:
        update.message.reply_text("No trade history found.")
    else:
        msg = "📊 Last 30 Trades:\n\n" + "\n".join(trades)
        update.message.reply_text(msg)

# --- Register Handlers ---

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("menu", menu))
dispatcher.add_handler(CommandHandler("backtest", backtest))
dispatcher.add_handler(CommandHandler("results", results))
dispatcher.add_handler(CommandHandler("last30", last30))

# --- Webhook route ---

@app.route(f"/{TOKEN}", methods=["POST"])
def receive_update():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok", 200

# --- Set webhook ---

if __name__ == "__main__":
    print("[INFO] Starting bot with webhook URL:", f"{WEBHOOK_URL}/{TOKEN}")
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=10000)
