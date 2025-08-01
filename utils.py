
import os
import json
import pandas as pd
from datetime import datetime, timedelta

TRADES_FILE = "trades.txt"

def log_trade(trade):
    with open(TRADES_FILE, "a") as f:
        f.write(json.dumps(trade) + "\n")

def read_trades():
    if not os.path.exists(TRADES_FILE):
        return []
    with open(TRADES_FILE, "r") as f:
        return [json.loads(line.strip()) for line in f if line.strip()]

def get_last_trades(n=30):
    trades = read_trades()
    return trades[-n:]

def evaluate_trade(entry_price, current_price, direction):
    if direction == "long":
        return round(((current_price - entry_price) / entry_price) * 100, 2)
    else:
        return round(((entry_price - current_price) / entry_price) * 100, 2)

def run_backtest(historical_data, threshold_score=1.0):
    signals = []
    for row in historical_data:
        score = row.get("score", 0)
        if score >= threshold_score:
            signals.append({
                "timestamp": row["timestamp"],
                "direction": row["direction"],
                "entry_price": row["price"],
                "rsi": row["rsi"],
                "wick": row["wick"],
                "liq": row["liq"],
                "score": score
            })
    return signals
