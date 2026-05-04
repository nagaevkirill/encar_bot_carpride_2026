import json
from pathlib import Path
from datetime import datetime
import locale

FILE = Path("service_currency/currency_rate.json")
try:
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
except locale.Error:
    # Для Windows — локаль может быть другой
    try:
        locale.setlocale(locale.LC_TIME, 'Russian_Russia')
    except:
        print("⚠️ Русская локаль не найдена — названия месяцев могут быть на английском.")


def save_rate(rate):
    with open(FILE, "w", encoding="utf-8") as file:
        json.dump(rate, file, ensure_ascii=False, indent=2)

def load_rate_eur():
    if FILE.exists():
        with open(FILE) as f:
            data = json.load(f)
            return round(float(data.get("EUR")), 2)
    return None

def load_rate_krw():
    if FILE.exists():
        with open(FILE) as f:
            data = json.load(f)
            return round(float(data.get("KRW")), 4)
    return None

def load_rate_usd():
    if FILE.exists():
        with open(FILE) as f:
            data = json.load(f)
            return round(float(data.get("USD")), 2)
    return None

def load_rate_date():
    if FILE.exists():
        with open(FILE) as f:
            data = json.load(f)
            dt = datetime.strptime(data.get("timestamp"), "%Y-%m-%d %H:%M:%S.%f")
            formatted = dt.strftime("%H:%M %-d %B") if hasattr(dt,'strftime') else f"{dt.hour}:{dt.minute} {dt.day} {dt.strftime('%B')}"
            return formatted
    return None
