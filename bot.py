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
    fetch_combined_liquidation,
    fetch_news,
    compute_rsi,  # used in debug
    calculate_score,  # used in debug
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")

if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN missing.")
if not WEBHOOK_URL:
    raise RuntimeError("WEBHOOK_URL missing.")

bot = Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, use_context=True)

os.environ["TZ"] = "Asia/Kolkata"
logging.basicConfig(level=logging.INFO)

# --- Handlers ---
def start(update: Update, context):
    update.message.reply_text("🚀 LiquidBot live. Use /menu for commands.")

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
        "/scan\n"
        "/envcheck"
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
    liq, source = fetch_combined_liquidation()
    update.message.reply_text(f"Liquidation proxy: ${liq:,.0f} (source: {source})")

def news_cmd(update: Update, context):
    headlines = fetch_news()
    update.message.reply_text("\n\n".join(headlines))

def envcheck(update: Update, context):
    missing = []
    for name in ["TELEGRAM_BOT_TOKEN", "WEBHOOK_URL", "OWNER_CHAT_ID", "COINGLASS_API_KEY", "NEWS_API_KEY"]:
        if not os.getenv(name):
            missing.append(name)
    if missing:
        update.message.reply_text("Missing env vars: " + ", ".join(missing))
    else:
        update.message.reply_text("All expected env vars are set.")

def send_signal_message(signal):
    direction = signal["direction"].upper()
    score = signal["score"]
    entry = signal["entry_price"]
    rsi = signal["rsi"]
    wick = signal["wick_percent"]
    liq = signal["liquidation_usd"]
    source = signal.get("liquidation_source", "unknown")
    tp = signal.get("tp_pct", 0.015) * 100
    sl = signal.get("sl_pct", 0.01) * 100
    strength = "Strong" if score >= 1.5 else ("Moderate" if score >= 1.0 else "Weak")
    msg = (
        f"🚨 {direction} Signal\n"
        f"Entry: {entry:.1f}\n"
        f"RSI: {rsi} | Wick%: {wick:.2f}% | Liq: ${liq:,.0f} ({source})\n"
        f"Score: {score} → {strength} setup\n"
        f"TP: +{tp:.2f}% | SL: -{sl:.2f}%"
    )
    if OWNER_CHAT_ID:
        bot.send_message(chat_id=OWNER_CHAT_ID, text=msg)
    else:
        logging.warning("OWNER_CHAT_ID not set; cannot send signal.")

def scan_cmd(update: Update, context):
    # Force evaluate open trades
    try:
        evaluate_open_trades()
    except Exception as e:
        update.message.reply_text(f"Error evaluating open trades: {e}")

    # Debug info
    from utils import fetch_binance_ohlcv, fetch_coinglass_liquidation

    ohlcv = fetch_binance_ohlcv()
    if not ohlcv:
        update.message.reply_text("🔍 Scan: failed to fetch OHLCV data.")
        return

    closes = [c["close"] for c in ohlcv]
    rsi = compute_rsi(closes[-15:]) if len(closes) >= 15 else None
    last = ohlcv[-1]
    open_p = last["open"]
    close_p = last["close"]
    high = last["high"]
    low = last["low"]
    total_range = high - low if high - low != 0 else 1
    lower_wick_pct = ((min(open_p, close_p) - low) / total_range) * 100
    upper_wick_pct = ((high - max(open_p, close_p)) / total_range) * 100

    liq, source = fetch_combined_liquidation()
    score_long = calculate_score(rsi, lower_wick_pct, liq)
    score_short = calculate_score(rsi, upper_wick_pct, liq)

    debug_msg = (
        f"🛠️ Debug Info:\n"
        f"RSI: {rsi}\n"
        f"Lower wick %: {lower_wick_pct:.2f}\n"
        f"Upper wick %: {upper_wick_pct:.2f}\n"
        f"Liquidation proxy: ${liq:,.0f} (source: {source})\n"
        f"Score Long: {score_long} | Score Short: {score_short}"
    )
    update.message.reply_text(debug_msg)

    signal = generate_trade_signal()
    if signal:
        try:
            store_trade(signal)
        except Exception as e:
            update.message.reply_text(f"Failed to store signal: {e}")
        send_signal_message(signal)
        update.message.reply_text("🔍 Scan: new signal sent.")
    else:
        update.message.reply_text("🔍 Scan: no new high-confidence signal.")

# Register handlers
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
dispatcher.add_handler(CommandHandler("envcheck", envcheck))

# Webhook route
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "Bot is live."

# Scheduled loop
def scheduled_tasks():
    try:
        evaluate_open_trades()
        signal = generate_trade_signal()
        if signal:
            store_trade(signal)
            send_signal_message(signal)
    except Exception as e:
        logging.error("Scheduled task failed: %s", e)

if __name__ == "__main__":
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}")
    from threading import Thread
    import time

    def loop():
        while True:
            scheduled_tasks()
            time.sleep(300)  # every 5 minutes

    Thread(target=loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
