import re, os, time, requests, json, logging
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from calculation import calculate_customs_duty
from calculation_util import calc_recycling_fee
from dict_for_replace import translate_korean
from datetime import datetime
from service_currency.scheduler import run_scheduler_in_background
from service_currency.storage import load_rate_eur, load_rate_krw, load_rate_usd, load_rate_date
from dotenv import load_dotenv

load_dotenv("stack.env", override=False)
BOT_TOKEN = os.getenv("BOT_TOKEN")

API_URL_TEMPLATE = "https://api.encar.com/v1/readside/vehicle/{}"
LOT_ID_REGEX = re.compile(r"(\d{7,8})")

# Маркер в тексте бота — по нему понимаем, что это запрос HP
HP_PROMPT_MARKER = "лот #"


def wait_until_json_ready(path: Path, timeout: float = 120.0, poll: float = 0.5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size > 0:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    json.load(f)
                return True
            except Exception:
                pass
        time.sleep(poll)
    return False


def formatted_cost(value):
    return f"{int(value / 1000) * 1000:,}".replace(',', ' ')


def extract_lot_id(text: str) -> str | None:
    match = LOT_ID_REGEX.search(text)
    return match.group(1) if match else None


def build_reply(lot_id: str, data: dict, car_hp: int,
                kurs_krw: float, kurs_euro: float, kurs_usd: float) -> str:
    auto_manuf = data.get("category", {}).get("manufacturerName") or "Нет данных"
    auto_model = data.get("category", {}).get("modelGroupName") or "Нет данных"
    fuel_name = data.get("spec", {}).get("fuelName") or "Нет данных"
    auto_displacement = data.get("spec", {}).get("displacement") or "Нет данных"
    auto_year = data.get("category", {}).get("yearMonth") or "Нет данных"
    formatted_auto_year = datetime.strptime(auto_year, "%Y%m").strftime("%m.%Y")
    customs_value_eur = (
        data.get("advertisement", {}).get("price") * 1.1 * 10000 * kurs_krw / kurs_euro
    )

    customs_duty = calculate_customs_duty(auto_displacement, formatted_auto_year, customs_value_eur)
    util_sbor = calc_recycling_fee(auto_displacement, formatted_auto_year, car_hp)

    value = int(customs_value_eur * kurs_euro / 1000) * 1000
    formatted_value = f"{value:,}".replace(',', ' ')
    duty_rub = int(customs_duty * kurs_euro / 1000) * 1000 + 17000
    formatted_duty_rub = f"{duty_rub:,}".replace(',', ' ')
    formatted_util_sbor = f"{int(util_sbor):,}".replace(',', ' ')

    extra_costs_korea = 127000
    extra_costs_russia = 150000
    agentskie_uslugi = 100000
    summary = (
        int(customs_value_eur * kurs_euro)
        + int(customs_duty * kurs_euro)
        + extra_costs_korea
        + extra_costs_russia
        + agentskie_uslugi
        + 17000
        + int(util_sbor)
    )
    summary = f"{int(summary / 1000) * 1000:,}".replace(',', ' ')

    return (
        f"🚗 *Расчёт стоимости автомобиля на Encar*\n"
        f"📦 Лот: [{lot_id}](https://fem.encar.com/cars/detail/{lot_id})\n"
        f"      {translate_korean(auto_manuf)} - {translate_korean(auto_model)} - {formatted_auto_year}\n"
        f"      Двигатель: {auto_displacement} cc, {translate_korean(fuel_name)}\n\n"
        f"*💰 Стоимость авто в Корее*\n~ {formatted_value} RUB\n"
        f"*🧾 Таможенная пошлина*\n~ {formatted_duty_rub} RUB\n"
        f"*🧾 Утильсбор*\n~ {formatted_util_sbor} RUB\n"
        f"*🧾 Расходы по Корее (доставка в порт, оформление, фрахт и прочее)*\n~ {formatted_cost(extra_costs_korea)} RUB\n"
        f"*🧾 Расходы по России (СБКТС, ЭПТС, брокерские услуги и прочее)*\n~ {formatted_cost(extra_costs_russia)} RUB\n"
        f"*🧾 Агентские услуги*\n~ 100 000 RUB\n\n"
        f"*📍Стоимость авто под ключ во Владивостоке* (доставка 8-14 дней)\n"
        f"➡️ ~ {summary} RUB \n\n"
        f"🚚 Доставка автовозом по России:\n"
        f"📦 до Москвы: +190 000 RUB\n"
        f"📦 до Краснодара: +200 000 RUB\n"
        f"🚗 Доставка в любой город РФ — по запросу\n\n"
        f"📲 ЗАКАЖИ ЭТО АВТО [ЗДЕСЬ](https://t.me/Car_pride) ➡️️ — [Car Pride](https://t.me/Car_pride)\n"
        f"📲 ЗАКАЖИ ЭТО АВТО [ЗДЕСЬ](https://t.me/Car_pride) ➡️️ — [Car Pride](https://t.me/Car_pride)\n"
        f"📲 ЗАКАЖИ ЭТО АВТО [ЗДЕСЬ](https://t.me/Car_pride) ➡️️ — [Car Pride](https://t.me/Car_pride)\n\n"
        f"➡️ EUR: {kurs_euro} USD: {kurs_usd} Обновлено {load_rate_date()}\n"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()
    user_id = update.message.from_user.id
    replied = update.message.reply_to_message

    # ── Шаг 1: пользователь прислал ссылку / номер лота ──────────────────────
    lot_id = extract_lot_id(user_input)
    if lot_id:
        await update.message.reply_text(
            f"Укажите количество лошадиных сил для {HP_PROMPT_MARKER}{lot_id}\n"
            f"(ответьте на это сообщение цифрой, например: 150)"
        )
        return

    # ── Шаг 2: пользователь ответил на сообщение бота с HP ───────────────────
    if (
        replied is not None
        and replied.from_user.id == context.bot.id
        and HP_PROMPT_MARKER in (replied.text or "")
    ):
        # Извлекаем lot_id из текста нашего предыдущего сообщения
        lot_id = extract_lot_id(replied.text)
        if not lot_id:
            await update.message.reply_text("Не удалось определить лот. Пришлите ссылку заново.")
            return

        # Парсим HP
        hp_match = re.search(r"\d+", user_input)
        if not hp_match:
            await update.message.reply_text(
                "Не понял число. Укажите лошадиные силы цифрой, например: 150"
            )
            return
        car_hp = int(hp_match.group())

        api_url = API_URL_TEMPLATE.format(lot_id)
        try:
            response = requests.get(api_url, timeout=10)
            if response.status_code != 200:
                await update.message.reply_text(
                    f"Ошибка запроса к API (код {response.status_code})."
                )
                return

            data = response.json()
            kurs_krw = load_rate_krw()
            kurs_euro = load_rate_eur()
            kurs_usd = load_rate_usd()

            print("user_id:", user_id, "lot_id:", lot_id, "hp:", car_hp)

            reply = build_reply(lot_id, data, car_hp, kurs_krw, kurs_euro, kurs_usd)
            await update.message.reply_text(reply, parse_mode="Markdown")

        except Exception as e:
            await update.message.reply_text(
                "Ошибка при получении информации о лоте. Попробуйте позже."
            )
        return

    # ── Fallback: непонятное сообщение ───────────────────────────────────────
    await update.message.reply_text(
        "Пришлите ссылку или номер лота с Encar, чтобы начать расчёт."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Пришлите ссылку или номер лота с Encar, чтобы получить расчёт стоимости."
    )


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
