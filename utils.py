
import os
import json
from datetime import datetime, timedelta
import random

TRADES_FILE = "trades.txt"
STRATEGY_FILE = "strategy.json"
LOG_FILE = "logs.txt"

def save_trade(trade):
    with open(TRADES_FILE, "a") as f:
        f.write(json.dumps(trade) + "\n")

def load_trades():
    if not os.path.exists(TRADES_FILE):
        return []
    with open(TRADES_FILE, "r") as f:
        return [json.loads(line.strip()) for line in f if line.strip()]

def get_last_trades(n=30):
    trades = load_trades()
    return trades[-n:]

def log_event(event):
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.utcnow().isoformat()} - {event}\n")

def get_logs(n=20):
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()
    return lines[-n:]

def calculate_score(rsi, wick, liquidation, funding_rate=0):
    score = 0
    if rsi < 30:
        score += (30 - rsi) * 0.05
    score += min(wick, 3.0) * 0.5
    score += min(liquidation / 5_000_000, 1.5)
    score += funding_rate * 2
    return round(score, 2)

def check_tp_sl(entry_price, current_price, direction, tp_percent=0.02, sl_percent=0.01):
    if direction == "long":
        tp = entry_price * (1 + tp_percent)
        sl = entry_price * (1 - sl_percent)
        if current_price >= tp:
            return "TP HIT"
        elif current_price <= sl:
            return "SL HIT"
    else:
        tp = entry_price * (1 - tp_percent)
        sl = entry_price * (1 + sl_percent)
        if current_price <= tp:
            return "TP HIT"
        elif current_price >= sl:
            return "SL HIT"
    return "open"

def run_backtest(days=7):
    # Fake signals for backtest (replace with real data logic)
    fake_results = []
    start_time = datetime.utcnow() - timedelta(days=days)
    for _ in range(15):
        rsi = random.randint(20, 38)
        wick = round(random.uniform(0.3, 1.5), 2)
        liq = random.randint(3_000_000, 10_000_000)
        entry = random.randint(112000, 115500)
        score = calculate_score(rsi, wick, liq)
        fake_results.append({
            "time": (start_time + timedelta(minutes=random.randint(10, 300))).strftime("%Y-%m-%d %H:%M:%S"),
            "type": "long",
            "entry": entry,
            "score": score,
            "result": "WIN" if score > 1.5 else "LOSS"
        })
    return fake_results

def get_status():
    if not os.path.exists(STRATEGY_FILE):
        return {"rsi": 30, "wick": 0.5, "liq": 5_000_000}
    with open(STRATEGY_FILE, "r") as f:
        return json.load(f)

def update_strategy(new_data):
    with open(STRATEGY_FILE, "w") as f:
        json.dump(new_data, f)

def learn_from_trades():
    trades = load_trades()
    if not trades:
        return
    total = len(trades)
    wins = [t for t in trades if t.get("result") == "TP HIT"]
    win_rate = len(wins) / total if total else 0
    avg_rsi = sum(t["rsi"] for t in trades) / total
    avg_wick = sum(t["wick"] for t in trades) / total
    avg_liq = sum(t["liquidation"] for t in trades) / total
    strategy = {
        "rsi": round(avg_rsi - 1, 2),
        "wick": round(avg_wick, 2),
        "liq": int(avg_liq * 0.95),
        "win_rate": round(win_rate, 2)
    }
    update_strategy(strategy)
