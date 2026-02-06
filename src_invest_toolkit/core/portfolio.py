import pandas as pd

COLUMNS_TO_KEEP = [
    'isin',
    'count',
    ]

def source_sber(split_tables_dict: dict[str, pd.DataFrame])->pd.DataFrame:
    """
    Извлекает и преобразует таблицу позиций из отчёта Сбербанка.

    Таблица берётся из `self.split_tables_dict[2]` и проходит следующие этапы:
    - установка первой строки как временных имён столбцов,
    - фильтрация по двум ключевым колонкам,
    - установка второй строки как финальных имён столбцов,
    - обрезка "служебных" строк (первые 4 и последние 3),
    - переименование согласно `RENAME_DICT_SBER`,
    - преобразование колонки `'Кол-во (шт)'` в `float` (удаление пробелов в числах),
    - отбор только нужных колонок (`self.COLUMNS_TO_KEEP`).

    :returns: Обработанный DataFrame с позициями портфеля.
    :rtype: pd.DataFrame

    :raises KeyError: Если в `split_tables_dict` нет ключа `2`,
                      или отсутствуют ожидаемые колонки (`'Основной рынок'`, `'Плановые показатели'`).
    :raises IndexError: Если в таблице недостаточно строк (например, < 5 строк после фильтрации).
    :raises AttributeError: Если `self.COLUMNS_TO_KEEP` не определён в подклассе или экземпляре.
    :raises ValueError: При ошибке приведения `'Плановый исходящий остаток, шт'` к `float`.
    """
    df:pd.DataFrame = split_tables_dict[2]
    df.columns = df.iloc[0]
    df = df[
            [
            'Основной рынок',
            'Плановые показатели'
            ]
        ]
    df.columns = df.iloc[1]
    df = df.iloc[4:-3].reset_index(drop=True)
    df = df.rename(columns={
        'ISIN ценной бумаги': 'isin',
        'Количество, шт': 'count',
    })
    df['count'] = df['Плановый исходящий остаток, шт'].str.replace(' ', '').astype(float)
    df = df[COLUMNS_TO_KEEP]
    return df

def balance_report(df_source:pd.DataFrame, all_stock_df:pd.DataFrame) -> pd.DataFrame:
    """
    Формирует итоговый отчёт о позициях портфеля с обогащёнными данными.

    1. Получает "сырой" DataFrame через `self.get_source_df()`.
    2. Для каждой строки по ISIN находит в `all_stock_df`:
       - тикер (`SECID`),
       - размер лота (`LOTSIZE`),
       - краткое наименование (`SHORTNAME`).
    3. Добавляет столбцы: 'ticker', 'Размер лота', 'name'.
    4. Приводит числовые столбцы к `float`.
    5. Сохраняет результат в `self.balance_report`.
    6. При наличии `self.registry` — регистрирует отчёт.

    :returns: Обогащённый DataFrame с позициями портфеля.
    :rtype: pd.DataFrame

    :raises KeyError: Если в `all_stock_df` отсутствует ISIN из отчёта.
    :raises IndexError: Если по ISIN найдено 0 или >1 записей в `all_stock_df`.
    :raises ValueError: При ошибке приведения к `float`.
    :raises AttributeError: Если `get_source_df()` не переопределён или не возвращает ожидаемые столбцы.
    """
    for index, row,  in df_source.iterrows():
        isin_source = row['isin']
        ticker = all_stock_df.loc[
            all_stock_df['isin'] == isin_source, 
            'ticker'
            ].iloc[0]
        lot_size = all_stock_df.loc[
            all_stock_df['isin'] == isin_source, 
            'lot_size'
            ].iloc[0]
        shortname = all_stock_df.loc[
            all_stock_df['isin'] == isin_source, 
            'name'
            ].iloc[0]
        df_source.at[index, "ticker"] = ticker
        df_source.at[index, "lot_size"] = lot_size
        df_source.at[index, "name"] = shortname

    df_source["lot_size"] = df_source["lot_size"].astype('float')
    df_source['count'] = df_source['count'].astype('float')
    return df_source

if __name__ == '__main__':
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from src_invest_toolkit.io import *
    report_path = r'./.reports/sber_01012026_31012026.HTML'  # Пример пути
    output_excel = r'./.output/sber_tables.xlsx'
    tables = split_sber_report(report_path)
    df = balance_report(source_sber(tables), all_instruments_info())
    print(df)
     