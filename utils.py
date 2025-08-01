import datetime
import random

# Simulated historical data store (in memory)
trade_logs = []

def analyze_market():
    """Simulate signal generation with scoring"""
    rsi = random.randint(20, 40)
    wick = round(random.uniform(0.4, 1.2), 2)
    liquidation = random.randint(2_000_000, 10_000_000)
    score = round((35 - rsi) / 10 + wick + liquidation / 10_000_000, 2)
    signal = {
        "timestamp": datetime.datetime.now(),
        "type": "LONG",
        "price": round(random.uniform(112000, 115000), 2),
        "rsi": rsi,
        "wick": wick,
        "liq": liquidation,
        "score": score,
        "result": "open"
    }
    trade_logs.append(signal)
    return signal

def get_logs():
    if not trade_logs:
        return "📉 No trades recorded yet."
    return "\n".join([
        f"{t['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} | {t['type']} at {t['price']} | Result: {t['result']} | Score: {t['score']}"
        for t in trade_logs[-30:]
    ])

def get_status():
    if not trade_logs:
        return "ℹ️ No trade data available."
    total = len(trade_logs)
    wins = sum(1 for t in trade_logs if t['result'] == "win")
    losses = sum(1 for t in trade_logs if t['result'] == "loss")
    open_trades = sum(1 for t in trade_logs if t['result'] == "open")
    avg_score = round(sum(t['score'] for t in trade_logs) / total, 2)
    return f"📊 Total Trades: {total}\n✅ Wins: {wins}\n❌ Losses: {losses}\n🕒 Open: {open_trades}\n⭐ Avg Score: {avg_score}"

def get_news():
    # Placeholder until real API call is added
    return "📰 Latest news placeholder..."

def train_model():
    # Simulate AI training
    return "🤖 Strategy trained with past data. Bot now adapts better to market shifts."

def run_backtest():
    result_lines = []
    for i in range(7):
        fake_trade = {
            "date": (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y-%m-%d"),
            "rsi": random.randint(25, 35),
            "wick": round(random.uniform(0.5, 1.2), 2),
            "liq": random.randint(3_000_000, 10_000_000),
            "score": round(random.uniform(1.0, 2.0), 2),
        }
        result_lines.append(
            f"{fake_trade['date']}: 🚨 Long Signal: RSI={fake_trade['rsi']}, Wick={fake_trade['wick']}%, "
            f"Liq=${fake_trade['liq']:,}, Score={fake_trade['score']}"
        )
    return "\n".join(result_lines)

