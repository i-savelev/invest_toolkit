from .company import Company
from .capitalization_table import Cap
from .free_float_table import Freefloat
import re
import pathlib
import pandas as pd

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
            profit_score = com.grow_score('Чистая прибыль, млрд руб', n)
            div_count_score = com.count_score('Див.выплата, млрд руб', n)
            div_grow_score = com.grow_score('Див.выплата, млрд руб', n)
            _free_float = free_float.by_ticker(com.ticker)
            _cap = cap.by_ticker(com.ticker)
            if _cap is None: _cap = com.cap()
            if ir_score is None:
                score = (profit_score + div_count_score+ div_grow_score)/3
            else:
                score = (ir_score + profit_score + div_count_score+ div_grow_score)/4
            row = {
                'ticker':com.ticker,
                'name': com.name,
                'ir_score':ir_score,
                'profit_score':profit_score,
                'div_count_score':div_count_score,
                'div_grow_score':div_grow_score,
                'score':round(score, 2),
                'cap':round(_cap/1000000000, 2),
                'free_float%': _free_float/100
                }
            if len(tickers) > 0:
                if com.ticker in tickers or com.ticker+'P' in tickers:
                    data.append(row)    
            else:
                data.append(row)
                
        df = pd.DataFrame(data).set_index('ticker')
        df[f'sqrt_free_float({ratio.__round__(2)})'] = ((df['cap']*df['free_float%'])**ratio).round(2)
        df['temp'] = (df['cap']*df['free_float%'])**ratio*df['score']
        df['part'] = (df['temp']/df['temp'].sum()*100).round(2)
        df = df.drop(columns='temp')
        
        return df