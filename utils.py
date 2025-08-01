
import datetime
import random

def get_fake_trade():
    price = round(random.uniform(110000, 120000), 1)
    score = round(random.uniform(1.0, 2.0), 2)
    result = random.choice(["win", "loss", "open"])
    rsi = random.randint(20, 35)
    wick = round(random.uniform(0.4, 1.2), 2)
    liq = random.randint(3000000, 8000000)
    tp_hit = result == "win"
    sl_hit = result == "loss"
    return {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "side": "LONG",
        "price": price,
        "score": score,
        "rsi": rsi,
        "wick": wick,
        "liq": liq,
        "result": result,
        "tp_hit": tp_hit,
        "sl_hit": sl_hit
    }

def run_backtest(limit=30):
    results = []
    for _ in range(limit):
        trade = get_fake_trade()
        results.append(trade)
    return results

def format_trade(trade):
    line = f"{trade['timestamp']} | {trade['side']} at {trade['price']} | Score: {trade['score']}"
    if trade["result"] != "open":
        line += f" | Result: {trade['result']}"
    if trade["tp_hit"]:
        line += " ✅ TP HIT"
    if trade["sl_hit"]:
        line += " ❌ SL HIT"
    return line
