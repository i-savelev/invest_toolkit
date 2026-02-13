import pandas as pd
from invest_toolkit.utils import log, log_dataframe

@log_dataframe
def free_float(path:str):
    """
    Источник данных для free-float:
    https://www.moex.com/ru/listing/free-float.aspx

    В таблцу вручную добавляется SIBN = 0.045

    :param path: Описание
    :type path: str
    """
    log.info(f'Получение free-float из {path}...')
    df = pd.read_excel(path)
    df.rename(columns={
        'Код':'ticker',
        'Коэффициент free-float, %':'free_float',
    }, inplace=True)
    df.drop(columns=[
        'Полное наименование организации',
        'ИНН организации',
        'Тип инструмента',
        'Регистрационный номер выпуска / ISIN',
        'Уровень листинга',
    ], inplace=True)
    df['free_float'] = df['free_float']/100
    df.set_index('ticker', inplace=True)
    return df


if __name__ == '__main__':
    df = free_float(r'./support_files/20251206-free-float.xlsx')
    print(df)