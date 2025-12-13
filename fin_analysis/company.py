import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import pathlib
import re
from .utils import Plotter
from logger import log


class Company():
    '''

    '''
    def __init__(self, df:pd.DataFrame, ticker, name) -> None:
        self.ticker = ticker
        self.name = name
        self.df = df
        
    @staticmethod    
    def from_csv(path:str):
        file = pathlib.Path(path)
        df = pd.read_csv(path, sep=';', index_col=0, encoding='utf-8')

        def _clean_value(x):
            if pd.isna(x):
                return np.nan
            x_str = str(x).strip()
            if x_str.lower() in ['nan', 'none', '']:
                return np.nan
            x_str = x_str.replace(' ', '').replace(',', '.').replace('%', '')
            try:
                return float(x_str)
            except ValueError:
                return np.nan
        def _is_year_label(label):
            try:
                int(label)
                return True
            except (ValueError, TypeError):
                return False

        def _extract_ticker(name: str) -> str|None:
            match = re.search(r'\(([^)]+)\)', name)
            return match.group(1) if match else None
         
        year_mask = df.columns.map(_is_year_label)
        columns_to_ceep = df.columns[year_mask]
        df = df.map(_clean_value)
        df = df[columns_to_ceep]
        df = df.dropna(how='all')
        ticker = _extract_ticker(file.name)
        return Company(df=df, ticker=ticker, name=file.stem)

    def plot_one_chart(self, title, window=3, axes=None, show:bool=True):
        Plotter.plot_one_chart(self.df, title, window, axes, show)

    def plot_multiple_chart(
            self,
            metric_list:list[str], 
            window:int=3, 
            rows:int=3, 
            cols:int= 2, 
            figsize = (12, 9.5)
            ):
        Plotter.plot_multiple_chart(
            df=self.df,
            title=self.name,
            metric_list = metric_list,
            window=window,
            rows=rows,
            cols=cols,
            figsize=figsize
        )

    def get_metric_list(self):
        return self.df.index
    
    def _processed_data(self, metric:str, n:int) -> pd.Series:
        n = n+1
        last_n:pd.Series = None
        if metric in self.df.index:
            s = self.df.loc[metric]
            s_clean = pd.to_numeric(s, errors='coerce').fillna(0)
            last_n = s_clean.iloc[-n:]
            if len(last_n) < n:
                missing = n - len(last_n)
                padding = pd.Series([0.0] * missing)
                last_n = pd.concat([padding, last_n]).iloc[-n:]
        return last_n
        
    def grow_score(self, metric:str, n:int):
        s = self._processed_data(metric, n)
        if s is None:
            return 0
        l = s.values.tolist()
        l.reverse()
        score = 0
        val = 0
        for i, value in enumerate(l):
            if i >= len(l)-1: break
            if (value > l[i+1]) and (value > 0):
                val += 1
            if (value < 0):
                val -= 1
        score = val/n
        return round(score, 2)

    def count_score(self, metric:str, n:int):
        s = self._processed_data(metric, n)
        if s is None:
            return 0
        l = s.values.tolist()
        l.reverse()
        score = 0
        val = 0
        for i, value in enumerate(l):
            if i >= len(l)-1: break
            if value > 0:
                val += 1
        score = val/n
        return round(score, 2)
    
    def ir_score(self, ir_rating:pd.DataFrame):
        df = ir_rating.set_index('ticker')
        if self.ticker in df.index:
            rating = df.loc[self.ticker]['rating']
            return rating/100
        else: 
            return None

    def cap(self):
        cap = self.df.loc["Капитализация, млрд руб"].dropna().iloc[-1]*1000000000
        return cap
    
    def free_float(self):
        if 'Free Float, %' in self.get_metric_list():
            ff = self.df.loc['Free Float, %'].dropna().iloc[-1]
            if ff is not None:
                return ff
            else: return 100
        else: return 100

    METRIC_LIST = [
        'Выручка, млрд руб',
        'Чистая прибыль, млрд руб',
        'Чистый долг, млрд руб',
        'Долг/EBITDA',
        'Див.выплата, млрд руб',
        'Див доход, ао, %',
    ]

if __name__ == '__main__':
    folder = pathlib.Path(r'.finance_reports')

    tickers = [
        'RTKM',
    ]

    com = Company.from_csv('.finance_reports/X5 (X5).csv')
    com.df
    com.name
    com.ticker
    com.plot_multiple_chart(Company.METRIC_LIST)
    print(com.get_metric_list(), com.df, com.name, com.ticker)
    print(com.count_score('Див.выплата, млрд руб', 7))
    print(com._processed_data('Див.выплата, млрд руб', 7))
    com.plot_one_chart('Див.выплата, млрд руб')
