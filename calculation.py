from datetime import date, datetime

def calculate_customs_duty(engine_volume: int,
                            manufacture_date: str,
                            customs_value: float):
    """
    Рассчитывает таможенный платёж для автомобиля.

    :param engine_volume: объём двигателя в куб.см
    :param manufacture_date: дата изготовления в формате "MM.YYYY"
    :param customs_value: таможенная стоимость в евро
    :return: сумма таможенного платежа в евро
    """
    # Парсим месяц и год из строки MM.YYYY
    try:
        mfg_month, mfg_year = map(int, manufacture_date.split('.'))
    except ValueError:
        raise ValueError("Неверный формат даты. Ожидается MM.YYYY")

    # Текущая дата
    today = date.today()

    # Вычисляем возраст в месяцах
    age_months = (today.year - mfg_year) * 12 + (today.month - mfg_month)

    # Вычисляем возраст для логики (месяцы)
    # Таблицы по возрастным категориям:
    # <3 лет => <36 мес, 3-5 лет => 36-60 мес, 5-7 лет => 60-84 мес, >=7 лет => >=84 мес

    # 1. Автомобили до 3 лет
    if age_months < 36:
        brackets = [
            (0,      8500,   0.54,  2.5),
            (8500,   16700,  0.48,  3.5),
            (16700,  42300,  0.48,  5.5),
            (42300,  84500,  0.48,  7.5),
            (84500, 169000,  0.48, 15.0),
            (169000, float('inf'), 0.48, 20.0),
        ]
        for min_val, max_val, pct, min_cc in brackets:
            if min_val <= customs_value < max_val:
                percent_fee = customs_value * pct
                min_fee = engine_volume * min_cc
                return max(percent_fee, min_fee)

    # 2. Автомобили от 3 до 5 лет
    if 36 <= age_months < 60:
        rates = [
            (1000, 1.5),
            (1500, 1.7),
            (1800, 2.5),
            (2300, 2.7),
            (3000, 3.0),
            (float('inf'), 3.6),
        ]
        for max_vol, rate in rates:
            if engine_volume <= max_vol:
                return engine_volume * rate

    # 3. Автомобили от 5 до 7 лет
    if 60 <= age_months < 84:
        rates = [
            (1000, 3.0),
            (1500, 3.2),
            (1800, 3.5),
            (2300, 4.8),
            (3000, 5.0),
            (float('inf'), 5.7),
        ]
        for max_vol, rate in rates:
            if engine_volume <= max_vol:
                return engine_volume * rate

    # 4. Автомобили старше 7 лет
    if age_months >= 84:
        rates = [
            (1000, 3.0),
            (1500, 3.2),
            (1800, 3.5),
            (2300, 4.8),
            (3000, 5.0),
            (float('inf'), 5.7),
        ]
        for max_vol, rate in rates:
            if engine_volume <= max_vol:
                return engine_volume * rate

    raise ValueError("Не удалось определить ставку для заданных параметров.")


if __name__ == "__main__":
    # Пример использования
    vol = 2000             # куб.см
    mfg = "03.2021"       # месяц и год изготовления
    value = 12000.0        # таможенная стоимость, евро
    duty = calculate_customs_duty(auto_displacement, formatted_auto_year, customs_value)
    print(f"Таможенный платёж: {duty:.2f} EUR")

