from invest_toolkit.io import *
from invest_toolkit.core import *
from invest_toolkit.utils import *

log.init(f'Тест {__file__}')
report_path_sber = r'./.reports/sber_25122025.HTML'  # Пример пути
report_path_vtb = r'./.reports/vtb20251026_20251125.xlsx'  # Пример пути
all_info = all_instruments_info()
sber = read_sber(report_path_sber)
log.raw_dataframe(caption='Очищенные данные сбера', df=sber)
vtb = read_vtb(report_path_vtb)
log.raw_dataframe(caption='Очищенные данные ВТБ', df=vtb)

summary = summary_report([sber, vtb], all_info)
log.raw_dataframe(caption='Общий отчет', df=summary)

at = allocatin_table(r'./support_files/index_fund.xlsx')
log.raw_dataframe(df=at, caption='Таблица распределения')

allocation_df = allocation_report(summary, at, 40000)
log.raw_dataframe(df=allocation_df, caption='Целевое распределение')

allocation_grouped_df = group_by_category(df=allocation_df, group_col='ticker', tickers_list=['LQDT', 'SBMM'])
log.raw_dataframe(df=allocation_grouped_df, caption='Целевое распределение, группированное по тикеру')

allow_sell_df = allow_sell(allocation_grouped_df, allow_sell=True, tickers_to_sell=['LQDT, SBMM'])
log.raw_dataframe(df=allow_sell_df, caption='Применение политики продаж')

adjust_df = adjust_for_deposit(40000, allow_sell_df)
log.raw_dataframe(df=adjust_df, caption='Корректировка под сумму пополнения')
