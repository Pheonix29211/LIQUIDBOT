import os
from datetime import datetime

BACKTEST_FILE = "backtest.txt"
TRADES_FILE = "trades.txt"
RESULTS_FILE = "results.txt"

def run_backtest():
    if not os.path.exists(BACKTEST_FILE):
        return "No backtest data available."
    
    with open(BACKTEST_FILE, "r") as f:
        lines = f.readlines()
    
    return "📉 Backtest (Last 7 Days):\n\n" + "".join(lines[-10:])  # show last 10 entries

def get_results_summary():
    if not os.path.exists(RESULTS_FILE):
        return "No result summary found."
    
    with open(RESULTS_FILE, "r") as f:
        return "📈 Performance Summary:\n\n" + f.read()

def get_last_trades(n=30):
    if not os.path.exists(TRADES_FILE):
        return []
    
    with open(TRADES_FILE, "r") as f:
        lines = f.readlines()
    
    return lines[-n:]
