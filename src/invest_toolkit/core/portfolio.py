import pandas as pd
from typing import Dict, Any


def balance_report(df_source:pd.DataFrame, all_stock_df:pd.DataFrame) -> pd.DataFrame:
    """
    Формирует итоговый отчёт о позициях портфеля с обогащёнными данными.

    1. Получает "сырой" DataFrame через `self.get_source_df()`.
    2. Для каждой строки по ISIN находит в `all_stock_df`:
       - тикер (`SECID`),
       - размер лота (`LOTSIZE`),
       - краткое наименование (`SHORTNAME`).
    3. Добавляет столбцы: 'ticker', 'Размер лота', 'name'.
    4. Приводит числовые столбцы к `float`.
    5. Сохраняет результат в `self.balance_report`.
    6. При наличии `self.registry` — регистрирует отчёт.

    :returns: Обогащённый DataFrame с позициями портфеля.
    :rtype: pd.DataFrame

    :raises KeyError: Если в `all_stock_df` отсутствует ISIN из отчёта.
    :raises IndexError: Если по ISIN найдено 0 или >1 записей в `all_stock_df`.
    :raises ValueError: При ошибке приведения к `float`.
    :raises AttributeError: Если `get_source_df()` не переопределён или не возвращает ожидаемые столбцы.
    """
    log.info("Начато формирование итогового балансового отчёта.")
    log.debug(f"Начата итерация по {len(df_source)} позициям портфеля.")
    
    for index, row,  in df_source.iterrows():
        isin_source = row['isin']
        log.debug(f"Обработка позиции {index}: ISIN = {isin_source}")
        
        try:
            ticker = all_stock_df.loc[
                all_stock_df['isin'] == isin_source, 
                'ticker'
                ].iloc[0]
            lot_size = all_stock_df.loc[
                all_stock_df['isin'] == isin_source, 
                'lot_size'
                ].iloc[0]
            shortname = all_stock_df.loc[
                all_stock_df['isin'] == isin_source, 
                'name'
                ].iloc[0]
            
            df_source.at[index, "ticker"] = ticker
            df_source.at[index, "lot_size"] = lot_size
            df_source.at[index, "name"] = shortname
            
            log.debug(f"Позиция {index} обогащена: ticker={ticker}, lot_size={lot_size}, name={shortname}")
        
        except IndexError:
            log.error(f"Для ISIN {isin_source} не найдено данных в all_stock_df")
            raise
        
    log.debug("Все позиции обработаны. Начата конвертация типов данных.")
    
    df_source["lot_size"] = df_source["lot_size"].astype('float')
    df_source['count'] = df_source['count'].astype('float')
    
    log.debug("Конвертация типов данных завершена.")
    log.info(f"Формирование балансового отчёта завершено. Обработано {len(df_source)} позиций.")
    return df_source

if __name__ == '__main__':

    from invest_toolkit.io import *
    from invest_toolkit.utils import log
    log.init(f'Тест {__file__}')


    report_path_sber = r'./.reports/sber_09102025.HTML'  # Пример пути
    output_excel_sber = r'./.output/sber_tables.xlsx'
    report_path_vtb = r'./.reports/vtb_20250917_20251012.xlsx'  # Пример пути
    output_excel_vtb = r'./.output/vtb_tables.xlsx'

    all_info = all_instruments_info()

    log.separator()
    
    tables_sber = split_sber_report(report_path_sber)
    log.separator()

    tables_vtb = split_vtb_report(report_path_vtb)
    log.separator()
    
    df_sber = balance_report(source_sber(tables_sber), all_info)
    print(df_sber)
    print('=======================================')
    df_vtb = balance_report(source_vtb(tables_vtb), all_info)
    print(df_vtb)
