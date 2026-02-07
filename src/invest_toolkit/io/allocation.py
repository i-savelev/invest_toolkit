import pandas as pd
from invest_toolkit.utils import log

def _get_df_dict(file_path:str) -> dict[str, pd.DataFrame]:
    """
    Читает все листы Excel-файла и валидирует процентные суммы.

    - Для листа `'categories'`: проверяет, что сумма в колонке `'%'` = 100.
    - Для остальных листов: проверяет, что сумма `'%'` = 100 и есть колонка `'ticker'`.
    - Удаляет строки с `NaN` в ключевых колонках.

    :returns: Словарь: имя листа → DataFrame.
    :rtype: Dict[str, pd.DataFrame]

    :raises ValueError: 
        - Если сумма `'%'` ≠ 100 на каком-либо листе,
        - Если отсутствует колонка `'%'` или `'ticker'`/`'category'`.
    :raises FileNotFoundError: Если файл не найден.
    :raises KeyError: Если отсутствует лист `'categories'`.
    """
    df_dict = pd.read_excel(
        io=file_path,
        sheet_name=None,
    )
    for key in df_dict:
        if key == 'categories':
            df_dict[key].dropna(subset=['category'], inplace=True)
            percent_error(
                df_dict[key],
                100,
                '%',
                key
            )
        else:
            df_dict[key].dropna(subset=['ticker'], inplace=True)
            percent_error(
                df_dict[key],
                100,
                '%',
                key
            )
    return df_dict
    

def percent_error(df:pd.DataFrame, val: float, column:str, name:str):
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

def allocatin_table(file_path:str):
    """
    Формирует итоговую таблицу распределения портфеля с обогащёнными данными.

    1. Загружает и валидирует листы через `_get_df_dict()`.
    2. Для каждого листа (кроме `'categories'`):
        - находит его долю в `categories`,
        - масштабирует внутренние `%` до абсолютной доли портфеля,
        - добавляет колонку `category`.
    3. Объединяет все таблицы.
    4. Для каждого тикера добавляет:
        - `ISIN`, `Размер лота`, `name` — из `all_stock_df`.

    :returns: Итоговый DataFrame с колонками:
                `ticker`, `%`, `category`, `ISIN`, `Размер лота`, `name`.
    :rtype: pd.DataFrame

    :raises KeyError: 
        - Если лист отсутствует в `categories`,
        - Если `'categories'` не содержит колонку `'%'` или `'category'`.
    :raises IndexError: 
        - Если тикер не найден в `all_stock_df`,
        - Если по категории найдено ≠1 записи в `categories_df`.
    :raises ValueError: При ошибке приведения `'Размер лота'` к `float`.
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
                df_copy['%'] = category_percent/100*df['%'].round(10)
                df_list.append(df_copy)
            else: raise Exception(f'листа {key} нет в категориях')
    distribution_table = pd.concat(df_list).reset_index(drop=True)
    return distribution_table

    
if __name__ == '__main__':
    log.init(f'teat {__file__}')
    at = allocatin_table(r'./support_files/index_fund.xlsx')
    log.raw_dataframe(df=at, caption='Таблица распределения')