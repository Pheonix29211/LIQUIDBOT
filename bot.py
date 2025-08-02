import os
import logging
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler
from dotenv import load_dotenv
from utils import (
    generate_trade_signal,
    store_trade,
    evaluate_open_trades,
    get_last_trades,
    get_results_summary,
    run_backtest,
    get_status,
    get_logs,
    fetch_coinglass_liquidation,
    fetch_news,
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")  # chat id where alerts go

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL missing")

# Setup
bot = Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, use_context=True)

# Logging
logging.basicConfig(level=logging.INFO)

# Commands
def start(update: Update, context):
    update.message.reply_text("🚀 LiquidBot is running. Use /menu to see commands.")

def menu(update: Update, context):
    update.message.reply_text(
        "/menu\n"
        "/start\n"
        "/backtest\n"
        "/last30\n"
        "/results\n"
        "/status\n"
        "/logs\n"
        "/liqcheck\n"
        "/news\n"
        "/scan  (force signal + open eval)"
    )

def backtest_cmd(update: Update, context):
    update.message.reply_text(run_backtest())

def last30_cmd(update: Update, context):
    update.message.reply_text(get_last_trades())

def results_cmd(update: Update, context):
    update.message.reply_text(get_results_summary())

def status_cmd(update: Update, context):
    update.message.reply_text(get_status())

def logs_cmd(update: Update, context):
    update.message.reply_text(get_logs())

def liqcheck(update: Update, context):
    liq = fetch_coinglass_liquidation()
    update.message.reply_text(f"Liquidation total: ${liq:,}")

def news_cmd(update: Update, context):
    headlines = fetch_news()
    update.message.reply_text("\n\n".join(headlines))

def scan_cmd(update: Update, context):
    # Force evaluate open trades and generate new signal
    evaluate_open_trades()
    signal = generate_trade_signal()
    if signal:
        store_trade(signal)
        send_signal_message(signal)
        update.message.reply_text("🔍 Scan: new signal sent.")
    else:
        update.message.reply_text("🔍 Scan: no new high-confidence signal.")

def send_signal_message(signal):
    direction = signal["direction"].upper()
    score = signal["score"]
    entry = signal["entry_price"]
    rsi = signal["rsi"]
    wick = signal["wick_percent"]
    liq = signal["liquidation_usd"]
    tp = signal["tp_sl"]["tp_pct"] * 100
    sl = signal["tp_sl"]["sl_pct"] * 100
    strength = "Strong" if score >= 1.5 else ("Moderate" if score >= 1.0 else "Weak")
    msg = (
        f"🚨 {direction} Signal\n"
        f"Entry: {entry:.1f}\n"
        f"RSI: {rsi} | Wick%: {wick:.2f}% | Liq: ${liq:,}\n"
        f"Score: {score} → {strength} setup\n"
        f"TP: +{tp:.2f}% | SL: -{sl:.2f}%"
    )
    if OWNER_CHAT_ID:
        bot.send_message(chat_id=OWNER_CHAT_ID, text=msg)
    else:
        logging.warning("OWNER_CHAT_ID not set; signal not sent to user.")

# Register
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("menu", menu))
dispatcher.add_handler(CommandHandler("backtest", backtest_cmd))
dispatcher.add_handler(CommandHandler("last30", last30_cmd))
dispatcher.add_handler(CommandHandler("results", results_cmd))
dispatcher.add_handler(CommandHandler("status", status_cmd))
dispatcher.add_handler(CommandHandler("logs", logs_cmd))
dispatcher.add_handler(CommandHandler("liqcheck", liqcheck))
dispatcher.add_handler(CommandHandler("news", news_cmd))
dispatcher.add_handler(CommandHandler("scan", scan_cmd))

# Webhook
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "Bot is live."

# Periodic jobs (every 5 mins): evaluate open and auto-scan
def scheduled_tasks():
    try:
        evaluate_open_trades()
        signal = generate_trade_signal()
        if signal:
            store_trade(signal)
            send_signal_message(signal)
    except Exception as e:
        logging.error("Scheduled task error: %s", e)

if __name__ == "__main__":
    # set webhook
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}")
    # schedule with simple loop fallback (to avoid extra scheduler complexity)
    from threading import Thread
    import time

    def loop():
        while True:
            scheduled_tasks()
            time.sleep(300)  # 5 minutes

    Thread(target=loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
