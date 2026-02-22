import pandas as pd
from invest_toolkit.utils import log
from invest_toolkit.utils import log_dataframe

def _get_df_dict(file_path:str) -> dict[str, pd.DataFrame]:
    """
    Читает все листы Excel-файла и валидирует процентные суммы.

    - Для листа `'categories'`: проверяет, что сумма в колонке `'%'` = 100.
    - Для остальных листов: проверяет, что сумма `'%'` = 100 и есть колонка `'ticker'`.
    - Удаляет строки с `NaN` в ключевых колонках.

    :param file_path: Путь к Excel-файлу с настройками распределения.
    :returns: Словарь {имя_листа: DataFrame}.
    :raises ValueError: Если сумма процентов не равна 100.
    """
    df_dict = pd.read_excel(
        io=file_path,
        sheet_name=None,
    )
    for key in df_dict:
        if key == 'categories':
            df_dict[key].dropna(subset=['category'], inplace=True)
            _percent_error(
                df_dict[key],
                100,
                '%',
                key
            )
        else:
            df_dict[key].dropna(subset=['ticker'], inplace=True)
            _percent_error(
                df_dict[key],
                100,
                '%',
                key
            )
    return df_dict
    

def _percent_error(df:pd.DataFrame, val: float, column:str, name:str):
    """Проверяет, что сумма значений в столбце равна ожидаемому значению.

    :param df: DataFrame для проверки.
    :param val: Ожидаемая сумма (обычно `100.0`).
    :param column: Имя столбца с процентами.
    :param name: Название листа/группы (для сообщения об ошибке).

    :raises ValueError: Если `df[column].sum()` ≠ `val` (с точностью до float).
    :raises KeyError: Если столбец `column` отсутствует.
    """
    sum = df[column].sum().round(10)
    if sum != val:
        raise ValueError(f'сумма процентов {name} равна {sum}, а не равно 100%')

@log_dataframe
def allocatin_table(file_path:str):
    """
    Формирует итоговую таблицу целевого распределения портфеля.

    :param file_path: Путь к Excel-файлу с настройками (support_files/index_fund.xlsx).
    :returns: DataFrame с колонками: ticker, %, category, ISIN, Размер лота, name.
    """
    log.info(f"Начало обработки таблицы распределения: {file_path}...")
    df_dict = _get_df_dict(file_path=file_path)
    log.debug(f"получен словарь из excel")
    categories_df = df_dict['categories']
    log.raw_dataframe(df=categories_df, caption=f'Каотегории')
    categories_list = categories_df['category'].tolist()
    log.data(categories_list, label='Список категорий')
    df_list:list[pd.DataFrame] = []
    for key in df_dict:
        
        if key != 'categories':
            log.debug(f"обработка {key}...")
            if key in categories_list:
                df:pd.DataFrame = df_dict[key]
                log.raw_dataframe(df=df, caption=f'{key}')
                category_percent = categories_df.loc[
                    categories_df['category'] == key, 
                    '%'
                    ].iloc[0]
                df_copy = df.copy()[['ticker', '%']]
                df_copy['%'] = (category_percent/100*df['%']).round(2)
                df_list.append(df_copy)
            else: raise Exception(f'листа {key} нет в категориях')
    distribution_table = pd.concat(df_list).reset_index(drop=True)
    return distribution_table

    
if __name__ == '__main__':
    log.init(f'teat {__file__}')
    at = allocatin_table(r'./support_files/index_fund.xlsx')
    log.raw_dataframe(df=at, caption='Таблица распределения')