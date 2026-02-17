from invest_toolkit.io import *
from invest_toolkit.core import *
from invest_toolkit.utils import *
from invest_toolkit.reports import *
import pandas as pd

def portfolio_report(
        report_path_sber:str,
        report_path_vtb:str,
        allocation_path:str,
        deposit: float,
        grouping_tickers:list = [],
        sell:bool = True,
        allow_sell_tickers:list = [],
        report_save_path:str = r'./.output'
):
    log.init(f'Подготовка отчета по брокерским счетам')
    all_info = all_instruments_info()
    sber = read_sber(report_path_sber)
    vtb = read_vtb(report_path_vtb)
    summary = summary_report([sber, vtb], all_info)
    at = allocatin_table(allocation_path)
    allocation_df = allocation_report(summary, at, deposit)
    allocation_grouped_df = group_by_category(df=allocation_df, group_col='ticker', tickers_list=grouping_tickers)
    allow_sell_df = allow_sell(allocation_grouped_df, allow_sell=sell, tickers_to_sell=allow_sell_tickers)
    adjust_df = adjust_for_deposit(deposit, allow_sell_df)
    generate(
        save_path=report_save_path,
        deposit=deposit,
        adjust_df=adjust_df,
    )
    print(f'Отчет сгенерирован в {report_save_path}')
    print(f'лог файл: {log._log_file}')

@log_dataframe
def all_stock_info(
       free_dloat_path:str,
       ir_path:str, 
       sl_stock_folder:str
    ):
    log.init(f'Получение всех данных по акциям...')
    sl_stock_df = merge_csv_files(sl_stock_folder)
    ff_df = free_float(free_dloat_path)
    ir_df = ir_rating(ir_path)
    all_moex_df = all_instruments_info()
    df = get_stock_info(
        moex_api_df=all_moex_df,
        sl_stock_df=sl_stock_df,
        ir_df=ir_df,
        free_float_df=ff_df
    )
    return df

@log_dataframe
def rating_df(df:pd.DataFrame, n:int):
    tickers = df['ticker'].unique()
    data = []
    for ticker in tickers:
        ir_rating = ir_score(ticker, df)
        div_count_res = count_score(ticker, 'Див.выплата, млрд руб', df, n)
        div_grow_res = grow_score(ticker, 'Див.выплата, млрд руб', df, n)
        profit_score_res = grow_score(ticker, 'Чистая прибыль, млрд руб', df, n)
        
        data.append({
            'ticker': ticker,
            'type': 'rating',
            'indicator': 'IR',
            'year': None,
            'value': ir_rating
        })

        data.append({
            'ticker': ticker,
            'type': 'rating',
            'indicator': 'Выплата див-в',
            'year': None,
            'value': div_count_res[0]
        })
        data.append({
            'ticker': ticker,
            'type': 'rating_string',
            'indicator': 'Выплата див-в',
            'year': None,
            'value': div_count_res[1]
        })

        data.append({
            'ticker': ticker,
            'type': 'rating',
            'indicator': 'Рост див-в',
            'year': None,
            'value': div_grow_res[0]
        })
        data.append({
            'ticker': ticker,
            'type': 'rating_string',
            'indicator': 'Рост див-в',
            'year': None,
            'value': div_grow_res[1]
        })
        
        data.append({
            'ticker': ticker,
            'type': 'rating',
            'indicator': 'Рост прибыли',
            'year': None,
            'value': profit_score_res[0]
        })
        data.append({
            'ticker': ticker,
            'type': 'rating_string',
            'indicator': 'Рост прибыли',
            'year': None,
            'value': profit_score_res[1]
        })
            
        score = 0
        score_string = ''
        if ir_rating is not None:   
            score = (ir_rating + div_count_res[0] + div_grow_res[0] + profit_score_res[0])/4
            score_string = f'Рейтинг = ({div_count_res[0]}+{div_grow_res[0]}+{profit_score_res[0]}+{ir_rating})/4={round(score,2)}'
        else:
            score = (div_count_res[0] + div_grow_res[0] + profit_score_res[0])/3
            score_string = f'Рейтинг = ({div_count_res[0]}+{div_grow_res[0]}+{profit_score_res[0]})/3={round(score,2)}'
        data.append({
            'ticker': ticker,
            'type': 'rating',
            'indicator': f'rating',
            'year': None,
            'value': round(score,2)
        })
        data.append({
            'ticker': ticker,
            'type': 'rating_string',
            'indicator': f'rating',
            'year': None,
            'value': score_string
        })
    df = pd.DataFrame(data)
    return df

if __name__=='__main__':
    portfolio_report(
        report_path_sber = r'./.reports/sber_27012026.html' ,
        report_path_vtb = r'./.reports/vtb20260208.xlsx' ,
        allocation_path = r'./support_files/index_fund.xlsx',
        deposit = 117000,
        grouping_tickers=['LQDT', 'SBMM'],
        allow_sell_tickers=['LQDT', 'SBMM'],
        sell=True,
        report_save_path = r'./.output'
    )
    