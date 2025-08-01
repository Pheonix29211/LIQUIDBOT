from db import init_db
from logic import monitor_and_trade

if __name__ == "__main__":
    init_db()
    monitor_and_trade()
