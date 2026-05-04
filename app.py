import re, os, time, requests, json, logging
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from calculation import calculate_customs_duty
from dict_for_replace import translate_korean
from datetime import datetime
from service_currency.scheduler import run_scheduler_in_background
from service_currency.storage import load_rate_eur, load_rate_krw, load_rate_usd, load_rate_date
from dotenv import load_dotenv

# Настройки логирования
# logging.basicConfig(
#     filename='encar_bot.log',
#     format='%(asctime)s %(levelname)s %(message)s',
#     level=logging.INFO,
#     encoding='utf-8'
# )

# logging.getLogger("httpx").setLevel(logging.WARNING)
# logging.getLogger("httpcore").setLevel(logging.WARNING)

load_dotenv("stack.env", override=False)
# Твой токен
BOT_TOKEN = os.getenv("BOT_TOKEN")

API_URL_TEMPLATE = "https://api.encar.com/v1/readside/vehicle/{}"

# Регулярка для поиска номера лота (7-8 цифр, в середине или конце строки)
LOT_ID_REGEX = re.compile(r"(\d{7,8})")

# проверка существования JSON файла с курсами валют
def wait_until_json_ready(path: Path, timeout: float = 120.0, poll: float = 0.5) -> bool:
    """Ждём, пока появится файл и он будет валидным JSON (не пустой/не частично записанный)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size > 0:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    json.load(f)  # проверяем валидность
                return True
            except Exception:
                # файл ещё пишется или битый — подождём
                pass
        time.sleep(poll)
    return False

# преобразование 100000 в 100 000
def formatted_cost(value):
    return f"{int(value/1000)*1000:,}".replace(',', ' ')

def extract_lot_id(text: str) -> str | None:
    """Извлекает номер лота из текста/ссылки"""
    match = LOT_ID_REGEX.search(text)
    return match.group(1) if match else None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    user_id = update.message.from_user.id
    lot_id = extract_lot_id(user_input)

    if not lot_id:
        reply = "Пожалуйста, отправьте номер лота или ссылку на лот."
        await update.message.reply_text(reply)
        # logging.info(f"[user_id: {user_id}] Некорректный запрос: {user_input}")
        return

    api_url = API_URL_TEMPLATE.format(lot_id)
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200:
            reply = f"Ошибка запроса к API (код {response.status_code})."
            await update.message.reply_text(reply)
            # logging.error(f"[user_id: {user_id}] API error {response.status_code}: {api_url}")
            return

        data = response.json()
        # logging.info("API JSON for lot_id=%s: %s", lot_id, json.dumps(data, ensure_ascii=False))

        kurs_krw = load_rate_krw()
        kurs_euro = load_rate_eur()
        kurs_usd = load_rate_usd()

        auto_manuf = data.get("category", {}).get("manufacturerName") or "Нет данных"
        auto_model = data.get("category", {}).get("modelGroupName") or "Нет данных"
        fuel_name = data.get("spec", {}).get("fuelName") or "Нет данных"
        auto_displacement = data.get("spec", {}).get("displacement") or "Нет данных"
        auto_year = data.get("category", {}).get("yearMonth") or "Нет данных"
        formatted_auto_year = datetime.strptime(auto_year, "%Y%m").strftime("%m.%Y")
        customs_value_eur = data.get("advertisement", {}).get("price") * 1.1 * 10000 * kurs_krw / kurs_euro or "Нет данных"

        print("user_id:", user_id, auto_displacement, formatted_auto_year, customs_value_eur)

        customs_duty = calculate_customs_duty(auto_displacement, formatted_auto_year, customs_value_eur)
        # print("customs_duty: ",customs_duty)

        value = int(customs_value_eur*kurs_euro/1000)*1000
        formatted_value = f"{value:,}".replace(',', ' ')
        duty_rub = int(customs_duty*kurs_euro/1000)*1000 + 17000
        formatted_duty_rub = f"{duty_rub:,}".replace(',', ' ')
        extra_costs_korea = 127000
        extra_costs_russia = 150000
        agentskie_uslugi = 100000
        #summary = int(customs_value_eur*kurs_euro) + int(customs_duty*kurs_euro) + extra_costs_korea + extra_costs_russia + agentskie_uslugi
        summary = int(customs_value_eur*kurs_euro) + int(customs_duty*kurs_euro) + extra_costs_korea + extra_costs_russia + agentskie_uslugi + 17000

        summary = f"{int(summary/1000)*1000:,}".replace(',', ' ')

        reply = (
            f"🚗 *Расчёт стоимости автомобиля на Encar*\n"
            f"📦 Лот: [{lot_id}](https://fem.encar.com/cars/detail/{lot_id})\n"
            f"      {translate_korean(auto_manuf)} - {translate_korean(auto_model)} - {formatted_auto_year}\n"
            f"      Двигатель: {auto_displacement} cc, {translate_korean(fuel_name)}\n\n"
            f"*💰 Стоимость авто в Корее*\n~ {formatted_value} RUB\n"
            f"*🧾 Таможенная пошлина*\n~ {formatted_duty_rub} RUB\n"
            f"*🧾 Расходы по Корее (доставка в порт, оформление, фрахт и прочее)*\n~ {formatted_cost(extra_costs_korea)} RUB\n"
            f"*🧾 Расходы по России (СБКТС, ЭПТС, брокерские услуги и прочее)*\n~ {formatted_cost(extra_costs_russia)} RUB\n"
            f"*🧾 Агентские услуги*\n~ 100 000 RUB\n\n"
            f"*📍Стоимость авто под ключ во Владивостоке* (доставка 8-14 дней)\n"
            f"➡️ ~ {summary} RUB \n\n"
            f"🚚 Доставка автовозом по России:\n"
            f"📦 до Москвы: +190 000 RUB\n"
            f"📦 до Краснодара: +200 000 RUB\n"
            f"🚗 Доставка в любой город РФ — по запросу\n\n"
            # f"📲 Заказать авто из Кореи — [Car Pride](https://t.me/Car_pride)\n"
            f"📲 ЗАКАЖИ ЭТО АВТО [ЗДЕСЬ](https://t.me/Car_pride) ➡️️ — [Car Pride](https://t.me/Car_pride)\n"
            f"📲 ЗАКАЖИ ЭТО АВТО [ЗДЕСЬ](https://t.me/Car_pride) ➡️️ — [Car Pride](https://t.me/Car_pride)\n"
            f"📲 ЗАКАЖИ ЭТО АВТО [ЗДЕСЬ](https://t.me/Car_pride) ➡️️ — [Car Pride](https://t.me/Car_pride)\n\n"
            f"➡️ EUR: {kurs_euro} USD: {kurs_usd} Обновлено {load_rate_date()}\n"
        )

        await update.message.reply_text(reply, parse_mode="Markdown")
        # logging.info(f"[user_id={user_id}] lot_id={lot_id}: customs_value={customs_value_eur}, customs_duty={customs_duty}")

    except Exception as e:
        reply = "Ошибка при получении информации о лоте. Попробуйте позже."
        await update.message.reply_text(reply)
        # logging.exception(f"[user_id: {user_id}] Exception: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Пришлите номер лота или ссылку, чтобы получить информацию.")

def main():
    run_scheduler_in_background()
    FILE = Path("service_currency/currency_rate.json")
    print(f"Жду появления {FILE.resolve()} ...", flush=True)

    if not wait_until_json_ready(FILE, timeout=180, poll=0.5):
        print("Файл с курсами так и не появился/некорректен. Останавливаюсь.", flush=True)
        return

    print("Файл найден и валиден. Запускаю бота…", flush=True)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Бот запущен. Для остановки используйте Ctrl+C")
    app.run_polling()

if __name__ == "__main__":
    main()
