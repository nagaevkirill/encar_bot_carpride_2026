import requests
from datetime import datetime

def fetch_exchange_rate():
    try:
        response = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=30)

        data = response.json()
        rates = {
            "USD": data.get("Valute").get("USD").get("Value"),
            "EUR": data.get("Valute").get("EUR").get("Value"),
            "KRW": data.get("Valute").get("KRW").get("Value")/1000,
            "timestamp": str(datetime.now())
        }
        # предположим, ты получаешь что-то вроде: {"usd": 92.34, "eur": 99.12}
        return  rates # или другой нужный тебе курс
    except Exception as e:
        print(f"Ошибка при получении курса: {e}")
        return None
