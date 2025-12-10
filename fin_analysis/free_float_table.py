import pandas as pd
from logger import log

class Freefloat:
    """
    https://www.moex.com/ru/listing/free-float.aspx - free float
    """
    def __init__(self, df:pd.DataFrame, path:str) -> None:
        self.path = path
        self.df = df
        
    @staticmethod
    def from_excel(path:str):
        free_float_df = pd.read_excel(path).set_index('Код')
        return Freefloat(free_float_df, path)
    
    def by_ticker(self, ticker:str):
        if ticker.upper() in self.df.index:
            return self.df.loc[ticker.upper()]['Коэффициент free-float, %']
        else:
            log.info(message=f'тикера [{ticker}] нет в таблице [{self.path}]')
            return 100
            

    