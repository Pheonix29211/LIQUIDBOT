import sqlite3

def init_db():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        price REAL,
        liquidation_usd REAL,
        price_drop_pct REAL,
        rebound_pct REAL,
        entry_price REAL,
        exit_price REAL,
        result TEXT
    )''')
    conn.commit()
    conn.close()

def log_event(data):
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute('''INSERT INTO events 
        (timestamp, price, liquidation_usd, price_drop_pct, rebound_pct, entry_price, exit_price, result)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (
        data['timestamp'], data['price'], data['liquidation_usd'],
        data['price_drop_pct'], data['rebound_pct'],
        data['entry_price'], data['exit_price'], data['result']
    ))
    conn.commit()
    conn.close()
