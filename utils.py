import requests
import sqlite3
import json
from datetime import datetime, timedelta
import random

# Load learned strategy
with open("learned_strategy.json", "r") as f:
    strategy = json.load(f)

# Coinglass API
COINGLASS_API = "https://open-api.coinglass.com/public/v2/liquidation_history"
COINGLASS_KEY = "414eee5fd36f475ab234ad6446419959"

# News API
NEWS_API = "https://cryptopanic.com/api/v1/posts/?auth_token=d5c7df7715729d25ed315f376dc164be623340a9&currencies=BTC&public=true"

# Funding Rate Scoring (placeholder)
def score_funding_rate():
    return round(random.uniform(0.5, 1.0), 2)

# Simulate signal generation
def generate_trade_signal():
    rsi = random.randint(20, 70)
    wick = round(random.uniform(0.3, 1.5), 2)
    liq = random.randint(1000000, 8000000)
    confidence = round((70 - abs(50 - rsi)) / 100 + wick / 2 + (liq / 10000000), 2)

    if liq > strategy["min_liquidation_usd"] and rsi < strategy["rsi_threshold"]:
        store_trade("long", 114000 + random.randint(-500, 500), "open", rsi, wick, liq, confidence)
        return f"🚨 Long Signal: RSI={rsi}, Wick={wick}%, Liq=${liq:,}, Score={confidence}"
    return None

# Store trade in DB
def store_trade(direction, price, result, rsi, wick, liq, confidence):
    conn = sqlite3.connect("trade_logs.db")
    c = conn.cursor()
    c.execute("INSERT INTO trades (time, direction, price, result, rsi, wick, liquidation_usd, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), direction, price, result, rsi, wick, liq, confidence))
    conn.commit()
    conn.close()

# Backtest function
def run_backtest():
    messages = []
    for i in range(7):
        msg = generate_trade_signal()
        if msg:
            messages.append(f"{(datetime.now()-timedelta(days=i)).strftime('%Y-%m-%d')}: {msg}")
    return "\n".join(messages) or "No signals found in backtest."

# Last 10 trades
def get_last_trades():
    conn = sqlite3.connect("trade_logs.db")
    c = conn.cursor()
    c.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return "\n".join([f"{r[1]} | {r[2].upper()} at {r[3]} | Result: {r[4]} | Score: {r[8]}" for r in rows]) or "No recent trades."

# Train from logs
def train_strategy():
    # Dummy training logic to evolve RSI and Liq thresholds
    strategy["rsi_threshold"] = max(30, strategy["rsi_threshold"] - 1)
    strategy["min_liquidation_usd"] = max(2500000, strategy["min_liquidation_usd"] - 100000)
    strategy["last_trained"] = datetime.now().strftime("%Y-%m-%d")
    with open("learned_strategy.json", "w") as f:
        json.dump(strategy, f)
    return f"Strategy updated: RSI<{strategy['rsi_threshold']}, Liq>${strategy['min_liquidation_usd']:,}"

# View logs
def get_logs():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect("trade_logs.db")
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE time LIKE ?", (f"{today}%",))
    rows = c.fetchall()
    conn.close()
    return "\n".join([f"{r[1]} | {r[2]} at {r[3]} | Score: {r[8]}" for r in rows]) or "No trades today."

# View strategy
def get_status():
    return json.dumps(strategy, indent=2)

# Coinglass test
def get_liquidation_data():
    try:
        headers = {"coinglassSecret": COINGLASS_KEY}
        resp = requests.get(COINGLASS_API, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            top = data['data'][0]
            return f"Last Liq: {top['symbol']} | Amount: ${top['amount']} | Side: {top['side']}"
        return "Error fetching Coinglass data."
    except Exception as e:
        return f"Coinglass API Error: {e}"

# News from CryptoPanic
def get_news():
    try:
        resp = requests.get(NEWS_API)
        data = resp.json()
        top3 = data["results"][:3]
        return "\n".join([f"📰 {n['title']}" for n in top3])
    except:
        return "Error fetching news."