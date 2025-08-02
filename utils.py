import os
import json
import requests
from datetime import datetime, timedelta
import math

TRADES_FILE = "trades.txt"
STRATEGY_FILE = "strategy.json"

# --- Helpers for market data ---

def fetch_binance_ohlcv(symbol="BTCUSDT", interval="5m", limit=50):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    # Each kline: [open_time, open, high, low, close, ...]
    return [{
        "open_time": item[0],
        "open": float(item[1]),
        "high": float(item[2]),
        "low": float(item[3]),
        "close": float(item[4]),
    } for item in data]

def compute_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains.append(delta)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(-delta)
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def fetch_coinglass_liquidation():
    key = os.getenv("COINGLASS_API_KEY", "")
    if not key:
        return 0
    try:
        headers = {"accept": "application/json", "coinglassSecret": key}
        # Adjust endpoint as per your plan; using public v2 if available
        resp = requests.get("https://open-api.coinglass.com/public/v2/liquidation/chart?symbol=BTC", headers=headers, timeout=10)
        data = resp.json()
        # Attempt to extract total liquidation in last chunk
        liq_sum = 0
        if isinstance(data.get("data"), list):
            for entry in data["data"]:
                liq_sum += entry.get("sumAmount", 0)
        return liq_sum
    except Exception:
        return 0

def fetch_news():
    key = os.getenv("NEWS_API_KEY", "")
    if not key:
        return ["No news API key set."]
    try:
        url = f"https://cryptopanic.com/api/v1/posts/?auth_token={key}&currencies=BTC"
        r = requests.get(url, timeout=10)
        data = r.json()
        items = data.get("results", [])[:5]
        headlines = []
        for it in items:
            title = it.get("title", "No title")
            link = it.get("url", "")
            headlines.append(f"• {title}\n{link}")
        return headlines if headlines else ["No recent news found."]
    except Exception as e:
        return [f"News fetch error: {e}"]

# --- Trade storage & evaluation ---

def load_trades():
    if not os.path.exists(TRADES_FILE):
        return []
    with open(TRADES_FILE, "r") as f:
        lines = [line.strip() for line in f if line.strip()]
    trades = []
    for line in lines:
        try:
            trades.append(json.loads(line))
        except:
            continue
    return trades

def store_trade(trade):
    # trade is a dict
    with open(TRADES_FILE, "a") as f:
        f.write(json.dumps(trade) + "\n")

def save_strategy(strategy):
    with open(STRATEGY_FILE, "w") as f:
        json.dump(strategy, f)

def load_strategy():
    if not os.path.exists(STRATEGY_FILE):
        return {"rsi_threshold": 35, "wick_threshold": 0.5, "liq_threshold": 2_000_000}
    with open(STRATEGY_FILE, "r") as f:
        return json.load(f)

# --- Scoring & signal logic ---

def calculate_score(rsi, wick_percent, liquidation_usd, funding_rate=1.0):
    score = 0
    # Oversold/overbought benefit
    if rsi < 35:
        score += (35 - rsi) * 0.05  # long
    elif rsi > 65:
        score += (rsi - 65) * 0.03  # short
    # Wick significance
    score += min(wick_percent, 5) * 0.2
    # Liquidation
    score += min(liquidation_usd / 5_000_000, 2) * 0.5
    # Funding rate modifier
    score *= funding_rate
    return round(score, 2)

def check_tp_sl(entry_price, current_price, direction, tp_pct=0.015, sl_pct=0.01):
    if direction == "long":
        tp = entry_price * (1 + tp_pct)
        sl = entry_price * (1 - sl_pct)
        if current_price >= tp:
            return "TP HIT"
        elif current_price <= sl:
            return "SL HIT"
    else:  # short
        tp = entry_price * (1 - tp_pct)
        sl = entry_price * (1 + sl_pct)
        if current_price <= tp:
            return "TP HIT"
        elif current_price >= sl:
            return "SL HIT"
    return "open"

def generate_trade_signal():
    # Fetch recent market data
    ohlcv = fetch_binance_ohlcv()
    if not ohlcv:
        return None
    closes = [c["close"] for c in ohlcv]
    rsi = compute_rsi(closes[-15:])
    last = ohlcv[-1]
    open_p = last["open"]
    close_p = last["close"]
    high = last["high"]
    low = last["low"]
    body = abs(close_p - open_p)
    total_range = high - low if high - low != 0 else 1
    # Lower wick percent (for longs)
    lower_wick = min(open_p, close_p) - low
    lower_wick_pct = (lower_wick / total_range) * 100
    upper_wick = high - max(open_p, close_p)
    upper_wick_pct = (upper_wick / total_range) * 100

    liquidation = fetch_coinglass_liquidation()
    # For simplicity, funding rate 1.0 (could extend)
    funding_rate = 1.0

    signal = None
    direction = None
    wick_pct = 0
    if rsi is None:
        return None

    # Long condition: oversold + decent lower wick
    if rsi < 35 and lower_wick_pct > 0.5:
        direction = "long"
        wick_pct = lower_wick_pct
    # Short: overbought + upper wick
    elif rsi > 65 and upper_wick_pct > 0.5:
        direction = "short"
        wick_pct = upper_wick_pct
    else:
        return None  # no strong signal

    score = calculate_score(rsi, wick_pct, liquidation, funding_rate)

    # Build trade object
    entry_price = close_p
    signal = {
        "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "direction": direction,
        "entry_price": entry_price,
        "rsi": rsi,
        "wick_percent": round(wick_pct, 2),
        "liquidation_usd": liquidation,
        "score": score,
        "result": "open",
        "tp_sl": {"tp_pct": 0.015, "sl_pct": 0.01},
    }
    return signal

# --- Open trade evaluation (TP/SL hit) ---

def evaluate_open_trades():
    trades = load_trades()
    updated = False
    if not trades:
        return
    # Fetch current price
    try:
        ohlcv = fetch_binance_ohlcv(limit=2)
        current_price = ohlcv[-1]["close"]
    except:
        return
    for trade in trades:
        if trade.get("result") != "open":
            continue
        direction = trade["direction"]
        entry = trade["entry_price"]
        tp_pct = trade.get("tp_sl", {}).get("tp_pct", 0.015)
        sl_pct = trade.get("tp_sl", {}).get("sl_pct", 0.01)
        status = check_tp_sl(entry, current_price, direction, tp_pct=tp_pct, sl_pct=sl_pct)
        if status in ("TP HIT", "SL HIT"):
            trade["result"] = status
            trade["exit_price"] = current_price
            trade["exit_time"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            updated = True
    if updated:
        # Rewrite file atomically
        with open(TRADES_FILE, "w") as f:
            for t in trades:
                f.write(json.dumps(t) + "\n")

# --- Reporting utilities ---

def format_trade(t):
    base = f"{t['time']} | {t['direction'].upper()} at {t['entry_price']:.1f} | RSI={t['rsi']} | Wick={t['wick_percent']}% | Liq=${t['liquidation_usd']:,} | Score={t['score']}"
    if t.get("result") and t["result"] != "open":
        base += f" | {t['result']}"
    return base

def get_last_trades(n=30):
    trades = load_trades()
    if not trades:
        return "No trades logged yet."
    sliced = trades[-n:]
    return "\n".join(format_trade(t) for t in sliced)

def get_logs(n=20):
    trades = load_trades()
    if not trades:
        return "No logs."
    return "\n".join(format_trade(t) for t in trades[-n:])

def get_status():
    strategy = load_strategy()
    return f"Current thresholds: RSI< {strategy.get('rsi_threshold',35)} / >{100 - strategy.get('rsi_threshold',35)}, Wick>{strategy.get('wick_threshold',0.5)}%, Liq>{strategy.get('liq_threshold',2000000):,}"

def run_backtest(days=7):
    cutoff = datetime.utcnow() - timedelta(days=days)
    trades = load_trades()
    if not trades:
        return "No backtest data."
    relevant = [t for t in trades if datetime.strptime(t["time"], "%Y-%m-%d %H:%M:%S") >= cutoff]
    if not relevant:
        return f"No trades in last {days} days."
    lines = [format_trade(t) for t in relevant]
    return "📉 Backtest:\n" + "\n".join(lines[-30:])

def get_results_summary():
    trades = load_trades()
    if not trades:
        return "No trade data."
    wins = sum(1 for t in trades if t.get("result") == "TP HIT")
    losses = sum(1 for t in trades if t.get("result") == "SL HIT")
    total = wins + losses
    win_rate = round((wins / total) * 100, 2) if total else 0
    avg_score = round(sum(t.get("score", 0) for t in trades if "score" in t) / len(trades), 2) if trades else 0
    return (
        f"Total closed trades: {total}\n"
        f"Wins (TP): {wins}\n"
        f"Losses (SL): {losses}\n"
        f"Win rate: {win_rate}%\n"
        f"Avg score: {avg_score}"
    )
