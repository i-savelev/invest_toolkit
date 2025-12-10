import pandas as pd
from logger import log

class Cap:
    """
    https://www.moex.com/a9218 - капитализация
    https://www.moex.com/ru/listing/free-float.aspx - free float
    """
    def __init__(self, s:pd.Series, path:str) -> None:
        self.path = path
        self.s = s

    @staticmethod
    def _parse_number(s):
        if pd.isna(s):
            return s
        s = str(s).replace(' ', '').replace(',', '.')
        try:
            return float(s)
        except ValueError:
            return pd.NA
        
    @staticmethod
    def from_html(path:str):
        cap_df = pd.read_html(path, header=0)[0]
        cap_df['Капитализация, руб.'] = cap_df['Капитализация, руб.'].apply(Cap._parse_number)
        cap_df = cap_df.set_index('Торговый код ценной бумаги')
        cap_series = cap_df['Капитализация, руб.']
        return Cap(cap_series, path)
    
    def by_ticker(self, ticker:str):
        if ticker.upper() in self.s.index:
            return self.s[ticker.upper()]
        else:
            log.info(message=f'тикера {ticker} нет в таблице {self.path}')
            

    