import pandas as pd
from .broker_parser import BrokerParser

class VtbParser(BrokerParser): 
    """
    Парсер отчёта ВТБ: извлекает позиции из таблицы 'Отчёт об останках ценных бумаг'.

    Ожидается, что:
    - `self.split_tables_dict` содержит ключ `'Отчёт об остатках ценных бумаг'`,
    - в этой таблице первая строка — заголовки, последняя — итог/примечание,
    - столбец с инструментами содержит строку вида: `"Название, Рег. №, ISIN"`.

    Логика обработки:
    1. Берётся таблица по фиксированному имени.
    2. Удаляются первая и последняя строки (служебные).
    3. Первая оставшаяся строка → заголовки.
    4. Удаляются "заголовочные" строки уровней (где только первая колонка заполнена).
    5. Фильтрация: только позиции с `Плановый исходящий остаток (шт) > 0`.
    6. Переименование, отбор колонок, извлечение ISIN как третьего элемента после `', '`.

    .. note::
        Класс чувствителен к:
        - точному названию таблицы,
        - формату строки с ISIN,
        - порядку столбцов.

    Пример строки в колонке 'Наименование...':
        `"Газпром ао, 1-02-12500-A, RU000A0JR2K7"`
        → `s.split(', ')[2]` → `'RU000A0JR2K7'`
    """
    def get_source_df(self)->pd.DataFrame:
        """
        Переопределяет метод в BrokerParser. Далее используется в get_balance_report_df() базового класса BrokerParser
        Извлекает и преобразует таблицу позиций из отчёта ВТБ.

        :returns: DataFrame с колонками, указанными в `COLUMNS_TO_KEEP` (обычно `['ISIN', 'Кол-во (шт)']`).
        :rtype: pd.DataFrame

        :raises KeyError: Если таблица `'Отчёт об остатках ценных бумаг'` отсутствует в `split_tables_dict`.
        :raises IndexError: 
            - Если после `iloc[1:-1]` таблица пуста,
            - Если `df.columns[0]` недоступен (пустые колонки),
            - Если `s.split(', ')` возвращает < 3 элементов в ISIN-колонке.
        :raises ValueError: 
            - Если `'Плановый исходящий остаток (шт)'` содержит нечисловые значения,
            - При ошибке приведения к числу после фильтра.
        :raises AttributeError: Если `COLUMNS_TO_KEEP` не определён или `RENAME_DICT_VTB` некорректен.
        """
        source_df = self.split_tables_dict['Отчёт об остатках ценных бумаг']
        df = source_df.iloc[1:-1].reset_index(drop=True)
        df.columns = df.iloc[0]
        df = df[1:]
        df = df.reset_index(drop=True)
        df.columns = df.columns.str.replace('\n', ' ', regex=False)
        df = df[df['Плановый исходящий остаток (шт)']>0]
        first_col = df.columns[0]
        mask = ~(
            df[first_col].notna() &
            df[df.columns[1:]].isna().all(axis=1)
        )
        df = df[mask].copy()
        df = df.rename(columns=self.RENAME_DICT_VTB)
        df = df[self.COLUMNS_TO_KEEP]
        df['ISIN'] = df['ISIN'].apply(lambda s: s.split(', ')[2])
        return df

    RENAME_DICT_VTB = {
        'Наименование ценной бумаги, № гос. регистрации, ISIN': 'ISIN',
        'Плановый исходящий остаток (шт)': 'Кол-во (шт)', 
        }