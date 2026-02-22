import pandas as pd
from typing import List
from invest_toolkit.utils import log
from invest_toolkit.utils import log_dataframe

@log_dataframe
def summary_report(df_list: List[pd.DataFrame], all_stock_df:pd.DataFrame) -> pd.DataFrame:
    """
    Формирует итоговый балансовый отчёт по портфелю.

    Объединяет данные о позициях из нескольких брокерских отчётов, обогащает их
    справочной информацией и рассчитывает стоимость позиций.

    :param df_list: Список датафреймов с позициями клиентов (получается через функции 
        `io.brokers.read_sber`, `io.brokers.read_vtb`).
    :param all_stock_df: Справочник всех инструментов MOEX (получается через 
        `io.moex.all_instruments_info`).
    :returns: DataFrame с колонками: isin, ticker, count_pieces, price, value, %.
    """
    log.info("Начато формирование итогового балансового отчёта.")
    df_source = pd.concat(
            df_list, 
            ignore_index=True
            )
    
    balance_report =  df_source.groupby('isin', as_index=False).agg(
            {
            'count_pieces': 'sum',
            }
        )
    balance_report = _data_enrichment(
            balance_report, 
            all_stock_df
            )
    balance_report = _data_calc(balance_report)
    
    log.info("Итоговый балансовый отчёт сформирован.")
    log.info(f"Всего позиций: {len(balance_report)}")
    log.info(f"Всего стоимость: {balance_report['value'].sum()}")
    
    
    return balance_report

def _data_enrichment(df_source: pd.DataFrame, all_stock_df: pd.DataFrame) -> pd.DataFrame:
    """
    Обогащает данные о позициях справочной информацией.

    :param df_source: DataFrame с позициями (ISIN, количество).
    :param all_stock_df: Справочник инструментов (получается через `io.moex.all_instruments_info`).
    :returns: DataFrame с добавленными колонками ticker, lot_size, name, price, cap, type.
    """
    log.debug("Обогащение данных...")
    
    # Выбираем нужные столбцы из all_stock_df
    enrichment_columns = ['isin', 'ticker', 'lot_size', 'name', 'price', 'cap', 'type']
    available_cols = [col for col in enrichment_columns if col in all_stock_df.columns]
    
    # Оставляем только нужные колонки и убираем дубли по isin (на случай дублей)
    enrich_df = all_stock_df[available_cols].drop_duplicates(subset=['isin'])
    
    # Объединяем по isin
    merged = pd.merge(df_source, enrich_df, on='isin', how='left')
    
    # Логируем пропущенные ISIN
    missing = merged[merged['ticker'].isna()]['isin'].unique()
    if len(missing) > 0:
        log.error(f"Для ISIN не найдены данные: {list(missing)}")
    
    # Явно указываем типы
    float_cols = ['lot_size', 'price', 'cap', 'count_pieces']
    for col in float_cols:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors='coerce')
    
    log.info(f"Обработано {len(merged)} позиций.")
    return merged

def _data_calc(report_df:pd.DataFrame)->pd.DataFrame:
    """
    Рассчитывает стоимость позиций и их вес в портфеле.

    :param report_df: DataFrame с позициями и ценами.
    :returns: DataFrame с добавленными колонками value (стоимость) и % (доля).
    """
    log.info('Расчет стоимости и весов акций...')
    try:
        df = report_df.copy()
        df['value'] = (
                df['price']*df['count_pieces']
                ).round(2)
        df['%'] = (
            df['value']/df['value'].sum()*100
            ).round(2)
        return df
    except Exception as e:
        log.error(f'Ошибка{e}')
        raise



if __name__ == '__main__':

    from invest_toolkit.io import *
    log.init(f'Тест {__file__}')
    report_path_sber = r'./.reports/sber_09102025.HTML'  # Пример пути
    report_path_vtb = r'./.reports/vtb_20250917_20251012.xlsx'  # Пример пути
    all_info = all_instruments_info()
    sber = read_sber(report_path_sber)
    log.raw_dataframe(caption='Очищенные данные сбера', df=sber)
    vtb = read_vtb(report_path_vtb)
    log.raw_dataframe(caption='Очищенные данные ВТБ', df=vtb)
    summary = summary_report([sber, vtb], all_info)
    log.separator()
    log.raw_dataframe(caption='Общий отчет', df=summary)
    