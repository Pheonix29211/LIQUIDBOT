import os
import json
import requests
import sqlite3
import logging
import time
from datetime import datetime, timedelta

# --- Config / filenames ---
DB_FILE = "trade_logs.db"
STRATEGY_FILE = "strategy.json"

# --- Environment keys ---
COINGLASS_API_KEY = os.getenv("COINGLASS_API_KEY", "").strip()
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()

# --- Database helper ---
def _get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT,
            direction TEXT,
            entry_price REAL,
            result TEXT,
            exit_price REAL,
            exit_time TEXT,
            rsi REAL,
            wick_percent REAL,
            liquidation_usd REAL,
            score REAL,
            tp_pct REAL,
            sl_pct REAL,
            liquidation_source TEXT
        )"""
    )
    conn.commit()
    return conn

# --- MEXC integration ---
MEXC_BASE = "https://contract.mexc.com/api/v1/contract"
SYMBOL = "BTC_USDT"  # underscore as required by MEXC

def fetch_mexc_ohlcv(symbol=SYMBOL, interval="Min5", limit=50):
    interval_map = {
        "Min1": 60,
        "Min5": 300,
        "Min15": 900,
        "Min30": 1800,
        "Min60": 3600,
        "Hour4": 4 * 3600,
        "Hour8": 8 * 3600,
        "Day1": 24 * 3600,
    }
    step = interval_map.get(interval, 300)
    end = int(time.time())
    start = end - step * limit
    params = {"interval": interval, "start": start, "end": end}
    try:
        url = f"{MEXC_BASE}/kline/{symbol}"
        r = requests.get(url, params=params, timeout=8, headers={"User-Agent": "LiquidBot/1.0"})
        r.raise_for_status()
        resp = r.json()
        if not resp.get("success"):
            logging.warning("MEXC kline returned not success: %s", resp)
            return []
        data = resp.get("data", {})
        times = data.get("time", [])
        opens = data.get("open", [])
        highs = data.get("high", [])
        lows = data.get("low", [])
        closes = data.get("close", [])
        candles = []
        for i in range(len(times)):
            candles.append(
                {
                    "open_time": times[i] * 1000,
                    "open": float(opens[i]),
                    "high": float(highs[i]),
                    "low": float(lows[i]),
                    "close": float(closes[i]),
                }
            )
        return candles
    except Exception as e:
        logging.warning("Failed to fetch MEXC OHLCV: %s", e)
        return []

def fetch_mexc_ticker(symbol=SYMBOL):
    try:
        url = f"{MEXC_BASE}/ticker"
        r = requests.get(url, params={"symbol": symbol}, timeout=5, headers={"User-Agent": "LiquidBot/1.0"})
        r.raise_for_status()
        resp = r.json()
        if not resp.get("success"):
            logging.warning("MEXC ticker not success: %s", resp)
            return {}
        return resp.get("data", {})
    except Exception as e:
        logging.warning("Failed to fetch MEXC ticker: %s", e)
        return {}

def fetch_mexc_funding_rate(symbol=SYMBOL):
    try:
        url = f"{MEXC_BASE}/funding_rate/{symbol}"
        r = requests.get(url, timeout=5, headers={"User-Agent": "LiquidBot/1.0"})
        r.raise_for_status()
        resp = r.json()
        if not resp.get("success"):
            logging.warning("MEXC funding_rate not success: %s", resp)
            return 0.0
        return float(resp.get("data", {}).get("fundingRate", 0.0))
    except Exception as e:
        logging.warning("Failed to fetch MEXC funding rate: %s", e)
        return 0.0

def infer_liquidation_pressure_from_mexc():
    ticker = fetch_mexc_ticker()
    if not ticker:
        return 0.0, "mexc_failed"
    open_interest = float(ticker.get("holdVol", 0))  # analogous to open interest
    funding_rate = float(ticker.get("fundingRate", 0))
    if open_interest <= 0:
        return 0.0, "mexc_no_oi"
    pressure = (open_interest / 1e9) * (1 + abs(funding_rate) * 10)
    fallback_liq = pressure * 1_000_000  # scale to dollar-like proxy
    return fallback_liq, "mexc_inferred"

# --- CoinGlass liquidation ---
def fetch_coinglass_liquidation():
    if not COINGLASS_API_KEY:
        logging.warning("CoinGlass API key missing.")
        return 0
    try:
        headers = {"accept": "application/json", "coinglassSecret": COINGLASS_API_KEY}
        url = "https://open-api.coinglass.com/public/v2/liquidation/chart?symbol=BTC"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            logging.warning("CoinGlass HTTP %s: %s", resp.status_code, resp.text[:200])
            return 0
        data = resp.json()
        total = 0
        if isinstance(data.get("data"), list):
            for entry in data["data"]:
                total += entry.get("sumAmount", entry.get("liquidationAmount", 0))
        return total
    except Exception as e:
        logging.warning("CoinGlass fetch failed: %s", e)
        return 0

def fetch_combined_liquidation():
    cg = fetch_coinglass_liquidation()
    if cg and cg > 0:
        return cg, "coinglass"
    mexc_liq, source = infer_liquidation_pressure_from_mexc()
    if mexc_liq and mexc_liq > 0:
        return mexc_liq, source
    return 0, "none"

# --- Price fallback via CoinGecko if MEXC fails ---
def fetch_coingecko_price_candle():
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=6,
            headers={"User-Agent": "LiquidBot/1.0"},
        )
        resp.raise_for_status()
        data = resp.json()
        price = float(data.get("bitcoin", {}).get("usd", 0))
        if price > 0:
            t_ms = int(time.time() * 1000)
            return [{"open_time": t_ms, "open": price, "high": price, "low": price, "close": price}]
    except Exception as e:
        logging.warning("CoinGecko fallback failed: %s", e)
    return []

# --- RSI ---
def compute_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

# --- Scoring & signal logic ---
def calculate_score(rsi, wick_pct, liquidation_usd, funding_rate=1.0):
    score = 0
    if rsi is not None:
        if rsi < 35:
            score += (35 - rsi) * 0.05
        elif rsi > 65:
            score += (rsi - 65) * 0.03
    score += min(wick_pct, 5) * 0.2
    score += min(liquidation_usd / 5_000_000, 2) * 0.5
    score *= funding_rate
    return round(score, 2)

def check_tp_sl(entry_price, current_price, direction, tp_pct=0.015, sl_pct=0.01):
    if direction == "long":
        tp = entry_price * (1 + tp_pct)
        sl = entry_price * (1 - sl_pct)
        if current_price >= tp:
            return "TP HIT"
        if current_price <= sl:
            return "SL HIT"
    else:
        tp = entry_price * (1 - tp_pct)
        sl = entry_price * (1 + sl_pct)
        if current_price <= tp:
            return "TP HIT"
        if current_price >= sl:
            return "SL HIT"
    return "open"

def generate_trade_signal():
    ohlcv = fetch_mexc_ohlcv()
    if not ohlcv:
        ohlcv = fetch_coingecko_price_candle()
    if not ohlcv:
        return None
    closes = [c["close"] for c in ohlcv]
    rsi = compute_rsi(closes[-15:]) if len(closes) >= 15 else None
    last = ohlcv[-1]
    open_p = last["open"]
    close_p = last["close"]
    high = last["high"]
    low = last["low"]
    total_range = high - low if high - low != 0 else 1
    lower_wick = min(open_p, close_p) - low
    lower_wick_pct = (lower_wick / total_range) * 100
    upper_wick = high - max(open_p, close_p)
    upper_wick_pct = (upper_wick / total_range) * 100

    liquidation, source = fetch_combined_liquidation()
    funding_rate = 1.0  # could be replaced with real funding from MEXC if desired

    direction = None
    wick_pct = 0
    if rsi is None:
        return None

    if rsi < 35 and lower_wick_pct > 0.5:
        direction = "long"
        wick_pct = lower_wick_pct
    elif rsi > 65 and upper_wick_pct > 0.5:
        direction = "short"
        wick_pct = upper_wick_pct
    else:
        return None

    score = calculate_score(rsi, wick_pct, liquidation, funding_rate)
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
        "tp_pct": 0.015,
        "sl_pct": 0.01,
        "liquidation_source": source,
    }
    return signal

# --- Persistence & evaluation ---
def store_trade(trade):
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO trades 
           (time, direction, entry_price, result, rsi, wick_percent, liquidation_usd, score, tp_pct, sl_pct, liquidation_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            trade.get("time"),
            trade.get("direction"),
            trade.get("entry_price"),
            trade.get("result", "open"),
            trade.get("rsi"),
            trade.get("wick_percent"),
            trade.get("liquidation_usd"),
            trade.get("score"),
            trade.get("tp_pct"),
            trade.get("sl_pct"),
            trade.get("liquidation_source"),
        ),
    )
    conn.commit()
    conn.close()

def evaluate_open_trades():
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE result = 'open'")
    rows = c.fetchall()
    if not rows:
        conn.close()
        return
    # get current price from MEXC or fallback
    ohlcv = fetch_mexc_ohlcv(limit=2) if hasattr(fetch_mexc_ohlcv, "__call__") else []
    if not ohlcv:
        ohlcv = fetch_coingecko_price_candle()
    if not ohlcv:
        conn.close()
        return
    current_price = ohlcv[-1]["close"]
    updated = False
    for r in rows:
        trade_id = r[0]
        direction = r[2]
        entry_price = r[3]
        status = check_tp_sl(entry_price, current_price, direction, tp_pct=r[10], sl_pct=r[11])
        if status in ("TP HIT", "SL HIT"):
            exit_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            c.execute(
                "UPDATE trades SET result = ?, exit_price = ?, exit_time = ? WHERE id = ?",
                (status, current_price, exit_time, trade_id),
            )
            updated = True
    if updated:
        conn.commit()
    conn.close()

# --- Reporting ---
def format_trade_row(r):
    _, time_str, direction, entry_price, result, exit_price, exit_time, rsi, wick, liq, score, tp_pct, sl_pct, source = r
    s = f"{time_str} | {direction.upper()} @ {entry_price:.1f} | RSI={rsi} | Wick={wick:.2f}% | Liq=${liq:,} ({source}) | Score={score}"
    if result and result != "open":
        s += f" | {result} @ {exit_price:.1f} ({exit_time})"
    return s

def get_last_trades(limit=30):
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return "No recent trades."
    return "\n".join(format_trade_row(r) for r in rows)

def get_logs(limit=20):
    return get_last_trades(limit)

def get_status():
    default = {"rsi_threshold": 35, "wick_threshold": 0.5, "liq_threshold": 2_000_000}
    if os.path.exists(STRATEGY_FILE):
        try:
            with open(STRATEGY_FILE, "r") as f:
                default = json.load(f)
        except:
            pass
    return (
        f"Thresholds: RSI<{default.get('rsi_threshold')} / >{100 - default.get('rsi_threshold')}, "
        f"Wick>{default.get('wick_threshold')}%, Liq>${default.get('liq_threshold'):,}"
    )

def run_backtest(days=7):
    cutoff = datetime.utcnow() - timedelta(days=days)
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM trades ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    filtered = []
    for r in rows:
        try:
            t = datetime.strptime(r[1], "%Y-%m-%d %H:%M:%S")
        except:
            continue
        if t >= cutoff:
            filtered.append(format_trade_row(r))
    if not filtered:
        return f"No trades in last {days} days."
    return "📉 Backtest:\n" + "\n".join(filtered[:30])

def get_results_summary():
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT result, score FROM trades WHERE result IN ('TP HIT','SL HIT')")
    rows = c.fetchall()
    conn.close()
    if not rows:
        return "No closed trades yet."
    wins = sum(1 for r in rows if r[0] == "TP HIT")
    losses = sum(1 for r in rows if r[0] == "SL HIT")
    total = wins + losses
    win_rate = round((wins / total) * 100, 2) if total else 0
    conn = _get_conn()
    c = conn.cursor()
    c.execute("SELECT score FROM trades")
    all_scores = [r[0] for r in c.fetchall()]
    conn.close()
    avg_score = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0
    return (
        f"Closed trades: {total}\n"
        f"Wins (TP): {wins}\n"
        f"Losses (SL): {losses}\n"
        f"Win rate: {win_rate}%\n"
        f"Avg score: {avg_score}"
    )

# --- News fetch ---
def fetch_news():
    if not NEWS_API_KEY:
        return ["No news API key set."]
    try:
        url = f"https://cryptopanic.com/api/v1/posts/?auth_token={NEWS_API_KEY}&currencies=BTC"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return [f"CryptoPanic HTTP {r.status_code}: {r.text[:200]}"]
        data = r.json()
        items = data.get("results", [])[:5]
        if not items:
            return ["No recent news found."]
        headlines = []
        for it in items:
            title = it.get("title", "No title")
            link = it.get("url", "")
            headlines.append(f"• {title}\n{link}")
        return headlines
    except Exception as e:
        return [f"News fetch error: {e}"]
