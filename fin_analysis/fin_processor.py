from .company import Company
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
    def rating_df(folder_path, ir_rating:pd.DataFrame, n:int, tickers:list[str] = [], ratio:float=1):
        data = []
        folder = pathlib.Path(folder_path)
        files = folder.glob('*.csv')
        for file in files:
            score = 0
            com = Company.from_csv(file)
            # if len(tickers)>0:
            if com.ticker in tickers or com.ticker+'P' in tickers:
                ir_score = com.ir_score(ir_rating)
                profit_score = com.grow_score('Чистая прибыль, млрд руб', n)
                div_count_score = com.count_score('Див.выплата, млрд руб', n)
                div_grow_score = com.grow_score('Див.выплата, млрд руб', n)
                free_float_df = pd.read_excel(r'support_files/20251206-free-float.xlsx').set_index('Код')
                if com.ticker in free_float_df.index:
                    free_float = free_float_df.loc[com.ticker]['Коэффициент free-float, %']
                else: free_float = 100
                cap = com.cap()
                
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
                    'cap':cap,
                    'free_float': free_float/100
                    }
                data.append(row)
        df = pd.DataFrame(data).set_index('ticker')
        df['sqrt_cap'] = (df['cap']*df['free_float'])**ratio*df['score']
        df['cap_share'] = df['sqrt_cap']/df['sqrt_cap'].sum()
        df['part'] = ((df['cap_share']*100)).round(1)
        return df