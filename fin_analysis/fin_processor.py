from .company import Company
from .capitalization_table import Cap
from .free_float_table import Freefloat
import re
import pathlib
import pandas as pd
from logger import log

class FinProcessor():
    def __init__(self):
        pass
    
    @staticmethod
    def extract_ticker(name: str) -> str:
        match = re.search(r'\(([^)]+)\)', name)
        return match.group(1) if match else None
    
    @staticmethod
    def by_ticker(folder_path:str, ticker:str)->Company|None:    
        company = None
        folder = pathlib.Path(folder_path)
        files = folder.glob('*.csv')
        for file in files: 
            _ticker = FinProcessor.extract_ticker(file.name)
            if ticker.lower() == _ticker.lower():
                company = Company.from_csv(file)
        return company
            
    @staticmethod
    def rating_df(
        folder_path, 
        ir_rating:pd.DataFrame, 
        n:int, 
        cap_source_path:str,
        free_float_source_path:str,
        tickers:list[str] = [], 
        ratio:float=1
        ):
        data = []
        folder = pathlib.Path(folder_path)
        files = folder.glob('*.csv')
        cap = Cap.from_html(cap_source_path)
        free_float = Freefloat.from_excel(free_float_source_path)
        for file in files:
            score = 0
            com = Company.from_csv(file)
            ir_score = com.ir_score(ir_rating)
            profit_score = com.grow_score('Чистая прибыль, млрд руб', n).value()
            if profit_score == None:
                profit_score = 0
                log.debug(message=f'[Чистая прибыль, млрд руб]: [{com.ticker}] нет в таблице')
            div_count_score = com.count_score('Див.выплата, млрд руб', n).value()
            if div_count_score == None:
                div_count_score = 0
                log.debug(message=f'[Див.выплата, млрд руб]: [{com.ticker}] нет в таблице')
            div_grow_score = com.grow_score('Див.выплата, млрд руб', n).value()
            if div_grow_score is None:
                div_grow_score = 0
            _free_float = free_float.by_ticker(com.ticker)
            if _free_float is None:
                _free_float = com.free_float()
                log.debug(message=f'[FREE-FLOAT]: [{com.ticker}] нет в таблице')
            _cap = cap.by_ticker(com.ticker)
            if _cap is None or _cap == 0: 
                _cap = com.cap()
                log.debug(message=f'[CAP]: [{com.ticker}] нет в таблице')
            if ir_score is None:
                log.debug(message=f'[IR]: [{com.ticker}] нет таблице')
                score = (profit_score + div_count_score + div_grow_score)/3
            else:
                score = (ir_score + profit_score + div_count_score+ div_grow_score)/4
            row = {
                'Тикер':com.ticker,
                'Название': com.name,
                'IR':ir_score,
                'Рост прибыли':profit_score,
                'Выплата дивидендов':div_count_score,
                'Рост дивидендов':div_grow_score,
                'Рейтинг':round(score, 2),
                'Капитализация':round(_cap/1000000000, 2),
                'Free-float': _free_float/100
                }
            if len(tickers) > 0:
                if com.ticker in tickers or com.ticker+'P' in tickers:
                    data.append(row)    
            else:
                data.append(row)
                
        df = pd.DataFrame(data).set_index('Тикер')
        df[f'Корень({ratio}) free-float'] = ((df['Капитализация']*df['Free-float'])**(1/ratio)).round(2)
        df['temp'] = (df['Капитализация, млрд. руб.']*df['Free-float'])**(1/ratio)*df['Рейтинг']
        df['Вес, %'] = (df['temp']/df['temp'].sum()*100).round(2)
        df = df.drop(columns='temp')
        
        return df
    
    @staticmethod
    def one_company_rating(
        folder_path:str, 
        ticker:str, 
        ir_rating:pd.DataFrame, 
        n:int, 
        plot:bool=False,
        ):
        com = FinProcessor.by_ticker(folder_path=folder_path, ticker=ticker)
        score = 0
        if com is not None:
            ir_score = com.ir_score(ir_rating)
            profit_score = com.grow_score('Чистая прибыль, млрд руб', n)
            div_count_score = com.count_score('Див.выплата, млрд руб', n)
            div_grow_score = com.grow_score('Див.выплата, млрд руб', n)

            _profit_score = profit_score.value()
            _div_count_score = div_count_score.value()
            _div_grow_score = div_grow_score.value()

            if _profit_score == None:
                _profit_score = 0
                log.debug(message=f'[Чистая прибыль, млрд руб]: [{com.ticker}] нет в таблице')
            if _div_count_score == None:
                _div_count_score = 0
                log.debug(message=f'[Див.выплата, млрд руб]: [{com.ticker}] нет в таблице')
            if _div_grow_score is None:
                _div_grow_score = 0

            row = f'{profit_score.calc()}\n'+\
            f'{div_count_score.calc()}\n'+\
            f'{div_grow_score.calc()}\n'+\
            f'IR = {ir_score}\n'

            if ir_score is not None:
                score = (ir_score + _profit_score + _div_count_score+ _div_grow_score)/4
                row += f'Рейтинг = ({_profit_score}+{_div_count_score}+{_div_grow_score}+{ir_score})/4={round(score,2)}'
            else:
                score = (_profit_score + _div_count_score+ _div_grow_score)/4
                row += f'Рейтинг = ({_profit_score}+{_div_count_score}+{_div_grow_score})/4 = {round(score, 2)}'
            print(row)
            if plot:
                com.plot_multiple_chart(com.METRIC_LIST)
            return row

