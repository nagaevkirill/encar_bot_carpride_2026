import time
import threading
from service_currency.currency import fetch_exchange_rate
from service_currency.storage import save_rate

def daily_updater():
    rate = fetch_exchange_rate()
    if rate:
        save_rate(rate)
    while True:
        rate = fetch_exchange_rate()
        if rate:
            save_rate(rate)
            print(f"Курс обновлён: {rate}")
        else:
            print("Не удалось обновить курс.")
        time.sleep(3600)  # ждать 1 час

def run_scheduler_in_background():
    thread = threading.Thread(target=daily_updater, daemon=True)
    thread.start()