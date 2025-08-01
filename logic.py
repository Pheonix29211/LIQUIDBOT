import time
import requests
from datetime import datetime
from config import *
from db import log_event
from bot import send_alert

def get_btc_price():
    r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
    return float(r.json()['price'])

def get_liquidations():
    headers = {
        "X-CG-APIKEY": API_KEY_COINGLASS
    }
    url = "https://open-api.coinglass.com/api/pro/v1/futures/liquidation?symbol=BTC"
    r = requests.get(url, headers=headers)
    data = r.json()
    try:
        return float(data['data']['totalVolUsd'])  # Total liquidations in USD
    except:
        return 0.0

def detect_entry(prev_price, curr_price, liquidation_usd):
    drop_pct = (prev_price - curr_price) / prev_price * 100
    if liquidation_usd >= THRESHOLD_LIQUIDATION_USD and drop_pct >= PRICE_DROP_PCT:
        return True, drop_pct
    return False, drop_pct

def monitor_and_trade():
    prev_price = get_btc_price()
    while True:
        time.sleep(60)
        curr_price = get_btc_price()
        liq = get_liquidations()
        is_entry, drop_pct = detect_entry(prev_price, curr_price, liq)

        if is_entry:
            entry_price = curr_price
            send_alert(f"📥 *Entry Detected!*
Price: ${entry_price:.2f}\nDrop: {drop_pct:.2f}%\nLiquidation: ${liq/1e6:.1f}M\nMonitoring rebound...")
            start_time = time.time()

            while time.time() - start_time < TIME_WINDOW_SECONDS:
                time.sleep(30)
                new_price = get_btc_price()
                rebound = (new_price - entry_price) / entry_price * 100

                if rebound >= REBOUND_PCT:
                    send_alert(f"✅ *Rebound Successful!*\nEntry: ${entry_price:.2f}\nExit: ${new_price:.2f}\nRebound: {rebound:.2f}% ✅")
                    log_event({
                        "timestamp": datetime.utcnow().isoformat(),
                        "price": curr_price,
                        "liquidation_usd": liq,
                        "price_drop_pct": drop_pct,
                        "rebound_pct": rebound,
                        "entry_price": entry_price,
                        "exit_price": new_price,
                        "result": "win"
                    })
                    break
            else:
                final_price = get_btc_price()
                rebound = (final_price - entry_price) / entry_price * 100
                send_alert(f"❌ *Rebound Failed*\nEntry: ${entry_price:.2f}\nExit: ${final_price:.2f}\nRebound: {rebound:.2f}% ❌")
                log_event({
                    "timestamp": datetime.utcnow().isoformat(),
                    "price": curr_price,
                    "liquidation_usd": liq,
                    "price_drop_pct": drop_pct,
                    "rebound_pct": rebound,
                    "entry_price": entry_price,
                    "exit_price": final_price,
                    "result": "loss"
                })

        prev_price = curr_price
