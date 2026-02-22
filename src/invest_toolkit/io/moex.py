import pandas as pd
import requests
from typing import Dict
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from invest_toolkit.utils.logger import Logger

# URLs для разных типов инструментов
URLS = {
    'stock': 'https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities.json',
    'etf': 'https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQTF/securities.json',  # ETF на TQTF
    'bond': 'https://iss.moex.com/iss/engines/stock/markets/bonds/boards/TQCB/securities.json',  # Корпоративные
    'ofz': 'https://iss.moex.com/iss/engines/stock/markets/bonds/boards/TQOB/securities.json',     # ОФЗ
}

def all_instruments_info() -> pd.DataFrame:
    """
    Собирает справочную информацию по всем торгуемым инструментам на MOEX.

    Загружает данные для акций, ETF, корпоративных облигаций и ОФЗ через API MOEX.
    :returns: DataFrame с информацией (ticker, isin, name, lot_size, price, cap, type).
    """
    Logger.info("Начат сбор справочной информации по инструментам MOEX")
    all_data = []

    for instrument_type, url in URLS.items():
        Logger.info(f"Загрузка данных: {instrument_type.upper()}...")

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

        try:
            # Выполняем запрос
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            Logger.debug(f"Запрос к {url} выполнен успешно. Статус: {response.status_code}")

            # Проверка, есть ли данные
            if not data.get('securities', {}).get('data'):
                Logger.warning(f"Нет данных для {instrument_type}")
                continue

            # Создаём DataFrames
            sec_df = pd.DataFrame(data['securities']['data'], columns=data['securities']['columns'])
            mkt_df = pd.DataFrame(data['marketdata']['data'], columns=data['marketdata']['columns'])

            # Объединяем
            df = pd.merge(sec_df, mkt_df, on='SECID', how='left')

            # Добавляем тип инструмента
            df['type'] = instrument_type

            all_data.append(df)
            Logger.debug(f"Данные для {instrument_type} успешно загружены и объединены.")

        except requests.RequestException as e:
            Logger.error(f"Ошибка при загрузке данных {instrument_type}: {e}")
            raise
        except (KeyError, IndexError) as e:
            Logger.error(f"Ошибка при обработке данных {instrument_type}: структура ответа API изменилась. {e}")
            raise

    # Объединяем всё
    if not all_data:
        Logger.warning("Не удалось загрузить данные ни по одному типу инструментов.")
        return pd.DataFrame()
        
    full_df = pd.concat(all_data, ignore_index=True)
    Logger.info(f"Сбор данных завершен. Загружено {len(full_df)} записей.")

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
    numeric_cols = ['price', 'cap', 'lot_size', 'coupon']
    for col in numeric_cols:
        if col in full_df.columns:
            full_df[col] = pd.to_numeric(full_df[col], errors='coerce')

    # Дополнительно: валюту — как строку
    full_df['currency'] = full_df['currency'].fillna('RUB').str.upper()

    # Сортируем
    full_df.sort_values(
        by=['type', 'cap', 'price'],
        ascending=[True, False, False],
        inplace=True
    )
    full_df['price'] = full_df['price'].round(2)
    full_df.reset_index(drop=True, inplace=True)

    return full_df

    
if __name__ == "__main__":
    Logger.init('# Пример использования moex.py')
    df = all_instruments_info()
    print("\nВсе инструменты:")
    print(df)
    # print(f"\nВсего инструментов: {len(df)}")
    print(f"Типы: \n{df['type'].value_counts()}")
    df.to_excel(r'.output/moex_instruments.xlsx', index=False)
