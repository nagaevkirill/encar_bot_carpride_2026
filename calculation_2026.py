from datetime import date, datetime

# ---------------------------------------------------------------------------
# Утилизационный сбор 2026 (ПП РФ № 1713 от 01.11.2025, ред. ПП № 1291)
# Новый критерий с 01.12.2025: мощность двигателя.
# Льготные ставки для физлиц сохраняются только при мощности ≤ 160 л.с. и объёме ≤ 3 л.
# ---------------------------------------------------------------------------

_UTIL_BASE = 20_000  # руб., базовая ставка для легковых М1

# Льготные коэффициенты (мощность ≤ 160 л.с., объём ≤ 3 л, личное использование)
_UTIL_ЛЬГОТА_NEW = 0.17  # авто до 3 лет  → 3 400 руб.
_UTIL_ЛЬГОТА_OLD = 0.26  # авто от 3 лет  → 5 200 руб.

# Коммерческие коэффициенты с 01.01.2026.
# Формат строки: (max_power_hp, coeff_до_3лет, coeff_от_3лет)
_UTIL_COMM_UP_TO_1L = [
    (90, 24.6, 37.8),
    (120, 32.1, 49.3),
    (160, 37.8, 58.0),
    (190, 44.9, 68.9),
    (220, 53.4, 82.0),
    (250, 63.6, 97.6),
    (300, 75.6, 116.1),
    (400, 89.9, 138.1),
    (float("inf"), 107.0, 164.3),
]

_UTIL_COMM_1_2L = [
    (160, 0.17, 0.26),
    (190, 45.00, 74.64),
    (220, 47.64, 79.20),
    (250, 50.52, 83.88),
    (280, 57.12, 91.92),
    (310, 64.56, 100.56),
    (340, 72.96, 110.16),
    (370, 83.16, 120.60),
    (400, 94.80, 132.00),
    (430, 108.00, 144.60),
    (460, 123.24, 158.40),
    (500, 140.40, 173.40),
    (float("inf"), 160.08, 189.84),
]

_UTIL_COMM_2_3L = [
    (160, 0.17, 0.26),
    (190, 115.34, 172.80),
    (220, 118.20, 175.08),
    (250, 120.12, 177.60),
    (280, 126.00, 183.00),
    (310, 131.04, 188.52),
    (340, 136.32, 193.68),
    (370, 141.72, 199.08),
    (400, 147.48, 204.72),
    (430, 153.36, 210.48),
    (460, 159.48, 216.36),
    (500, 165.84, 222.36),
    (float("inf"), 172.44, 228.60),
]

# Объём > 3 л — льгота недоступна в любом случае
_UTIL_COMM_OVER_3L = [
    (90, 304.5, 467.7),
    (120, 397.5, 610.3),
    (160, 467.7, 718.3),
    (190, 608.3, 934.0),
    (220, 647.5, 994.5),
    (250, 687.4, 1055.8),
    (300, 789.2, 1212.0),
    (400, 939.2, 1442.6),
    (float("inf"), 1118.0, 1717.0),
]

_UTIL_COMM_TABLES = [
    (1_000, _UTIL_COMM_UP_TO_1L),
    (2_000, _UTIL_COMM_1_2L),
    (3_000, _UTIL_COMM_2_3L),
    (float("inf"), _UTIL_COMM_OVER_3L),
]


def _calc_recycling_fee(engine_volume: int, power_hp: float, age_months: int) -> float:
    """
    Утилизационный сбор по правилам 2026 года (руб.).

    Льгота применяется автоматически при мощности ≤ 160 л.с. и объёме ≤ 3 л.
    В остальных случаях — коммерческий тариф.
    """
    is_new = age_months < 36

    if power_hp <= 160 and engine_volume <= 3_000:
        coeff = _UTIL_ЛЬГОТА_NEW if is_new else _UTIL_ЛЬГОТА_OLD
        return _UTIL_BASE * coeff

    for max_cc, table in _UTIL_COMM_TABLES:
        if engine_volume <= max_cc:
            for max_hp, coeff_new, coeff_old in table:
                if power_hp <= max_hp:
                    return _UTIL_BASE * (coeff_new if is_new else coeff_old)
            break

    raise ValueError("Не удалось определить коэффициент утильсбора.")


def calculate_customs_duty(engine_volume: int,
                           manufacture_date: str,
                           customs_value: float,
                           power_hp: float = 200):
    """
    Рассчитывает таможенный платёж для автомобиля (2026).

    :param engine_volume:    объём двигателя в куб.см
    :param manufacture_date: дата изготовления в формате "MM.YYYY"
    :param customs_value:    таможенная стоимость в евро
    :param power_hp:         мощность двигателя в л.с. (требуется с 01.12.2025)
    :return: (таможенная_пошлина_евро, утилизационный_сбор_руб)
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

    # --- Таможенная пошлина (логика не изменилась) ---

    duty = None

    # 1. Автомобили до 3 лет
    if age_months < 36:
        brackets = [
            (0, 8500, 0.54, 2.5),
            (8500, 16700, 0.48, 3.5),
            (16700, 42300, 0.48, 5.5),
            (42300, 84500, 0.48, 7.5),
            (84500, 169000, 0.48, 15.0),
            (169000, float('inf'), 0.48, 20.0),
        ]
        for min_val, max_val, pct, min_cc in brackets:
            if min_val <= customs_value < max_val:
                duty = max(customs_value * pct, engine_volume * min_cc)
                break

    # 2. Автомобили от 3 до 5 лет
    elif 36 <= age_months < 60:
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
                duty = engine_volume * rate
                break

    # 3. Автомобили старше 5 лет (включая 7+)
    else:
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
                duty = engine_volume * rate
                break

    if duty is None:
        raise ValueError("Не удалось определить ставку таможенной пошлины.")

    # --- Утилизационный сбор (новая логика 2026) ---
    recycling_fee = _calc_recycling_fee(engine_volume, power_hp, age_months)

    print("duty", duty * 89)
    print("recycling_fee", recycling_fee)

    return duty * 89 + recycling_fee


if __name__ == "__main__":
    # Пример использования
    vol = 2200  # куб.см
    mfg = "03.2022"
    value = 12000.0  # евро
    hp = 250  # л.с.

    duty = calculate_customs_duty(vol, mfg, value, hp)
    print(f"Таможенный платёж: {duty:.2f} RUB")

    # recycling_fee = _calc_recycling_fee(2000, 170, 30)
    # print(recycling_fee)