from invest_toolkit.io import *
from invest_toolkit.core import *
from invest_toolkit.utils import *
from invest_toolkit.reports import *

log.init(f'Тест {__file__}')
report_path_sber = r'./.reports/sber_27012026.html'  # Пример пути
report_path_vtb = r'./.reports/vtb20260208.xlsx'  # Пример пути
all_info = all_instruments_info()
sber = read_sber(report_path_sber)

vtb = read_vtb(report_path_vtb)

summary = summary_report([sber, vtb], all_info)

at = allocatin_table(r'./support_files/index_fund.xlsx')

allocation_df = allocation_report(summary, at, 117000)

allocation_grouped_df = group_by_category(df=allocation_df, group_col='ticker', tickers_list=['LQDT', 'SBMM'])

allow_sell_df = allow_sell(allocation_grouped_df, allow_sell=True, tickers_to_sell=['LQDT, SBMM'])

adjust_df = adjust_for_deposit(117000, allow_sell_df)

generate(
    save_path=r'./.output',
    deposit=117000,
    adjust_df=adjust_df,
)
