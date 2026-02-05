import pandas as pd
import requests

# URLs для разных типов инструментов
URLS = {
    'stock': 'https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities.json',
    'etf': 'https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQTF/securities.json',  # ETF на TQTF
    'bond': 'https://iss.moex.com/iss/engines/stock/markets/bonds/boards/TQCB/securities.json',  # Корпоративные
    'ofz': 'https://iss.moex.com/iss/engines/stock/markets/bonds/boards/TQOB/securities.json',     # ОФЗ
}

def all_instruments_df()->pd.DataFrame:
    """
    Собирает все торгуемые инструменты с MOEX:
    - Акции (TQBR)
    - ETF (TQTF)
    - Корпоративные облигации (TQCB)
    - ОФЗ (TQOB)

    Возвращает единый DataFrame с колонками:
    - type: 'stock', 'etf', 'bond'
    - ticker, isin, name, price, lot_size, currency, cap (для акций/ETF), coupon (для облигаций)
    """
    all_data = []

    for instrument_type, url in URLS.items():
        print(f"Загружаем данные: {instrument_type.upper()}...")

        # Параметры запроса
        params = {
            'iss.only': 'securities,marketdata',
            'iss.meta': 'off',
        }

        # Указываем нужные колонки в зависимости от типа
        if instrument_type in ['stock', 'etf']:
            params['securities.columns'] = 'SECID,SHORTNAME,ISIN,LOTSIZE,CURRENCYID'
            params['marketdata.columns'] = 'SECID,LAST,ISSUECAPITALIZATION'
        elif instrument_type in ['bond', 'ofz']:
            params['securities.columns'] = 'SECID,SHORTNAME,ISIN,LOTSIZE,CURRENCYID,COUPONVALUE'
            params['marketdata.columns'] = 'SECID,LAST'

        # Выполняем запрос
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Проверка, есть ли данные
        if not data['securities']['data']:
            print(f"⚠️ Нет данных для {instrument_type}")
            continue

        # Создаём DataFrames
        sec_df = pd.DataFrame(data['securities']['data'], columns=data['securities']['columns'])
        mkt_df = pd.DataFrame(data['marketdata']['data'], columns=data['marketdata']['columns'])

        # Объединяем
        df = pd.merge(sec_df, mkt_df, on='SECID', how='left')

        # Добавляем тип инструмента
        df['type'] = instrument_type

        all_data.append(df)

    # Объединяем всё
    full_df = pd.concat(all_data, ignore_index=True)

    # Приводим к нужным именам
    column_mapping = {
        'SECID': 'ticker',
        'SHORTNAME': 'name',
        'ISIN': 'isin',
        'LOTSIZE': 'lot_size',
        'CURRENCYID': 'currency',
        'LAST': 'price',
        'ISSUECAPITALIZATION': 'cap',
        'COUPONVALUE': 'coupon',
    }
    full_df = full_df[list(column_mapping.keys()) + ['type']].rename(columns=column_mapping)

    # Приводим числовые поля
    numeric_cols = ['price', 'cap', 'lot_size', 'coupon', 'accrued_interest']
    for col in numeric_cols:
        if col in full_df.columns:
            full_df[col] = pd.to_numeric(full_df[col], errors='coerce')

    # Дополнительно: валюту — как строку
    full_df['currency'] = full_df['currency'].fillna('RUB').str.upper()

    # Сортируем по капитализации (акции/ETF) или по цене (облигации)
    full_df.sort_values(
        by=['type', 'cap', 'price'],
        ascending=[True, False, False],
        inplace=True
    )
    full_df.reset_index(drop=True, inplace=True)

    return full_df


if __name__ == "__main__":
    df = all_instruments_df()
    print("\nВсе инструменты:")
    print(df)
    # print(f"\nВсего инструментов: {len(df)}")
    print(f"Типы: \n{df['type'].value_counts()}")
