import pandas as pd
from .broker_parser import BrokerParser

class SberParser(BrokerParser): 
    """
    Парсер отчёта Сбербанка: извлекает и преобразует данные позиций портфеля.

    Ожидается, что:
    - `self.split_tables_dict` уже заполнен (например, через `SberSplitter.split()`),
    - таблица с индексом `2` содержит основную информацию по инструментам.

    Логика обработки:
    1. Берётся третья таблица (`index=2`).
    2. Первая строка — исходные заголовки, вторая — уточнённые.
    3. Выбираются колонки `'Основной рынок'`, `'Плановые показатели'`.
    4. После переименования и очистки остаются только колонки из `COLUMNS_TO_KEEP`.

    .. note::
        Класс зависит от структуры конкретного HTML-отчёта Сбербанка.
        Любое изменение в формате отчёта (порядок таблиц, заголовки) сломает парсер.

    Пример использования (в связке с SberSplitter):
        splitter_sber = SberSplitter()
        splitter_sber.split(r'.reports/sber_14112025.html')
        report_registry = mbtk.ReportRegistry()
        sber_parser = mbtk.SberPareser(
            all_stock_info=all_stock,
            splitter=splitter_sber,
            registry=report_registry
        )
        sber_parser.get_balance_report_df()

    """
    def get_source_df(self)->pd.DataFrame:
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
        df:pd.DataFrame = self.split_tables_dict[2]
        df.columns = df.iloc[0]
        df = df[
                [
                'Основной рынок',
                'Плановые показатели'
                ]
            ]
        df.columns = df.iloc[1]
        df = df.iloc[4:-3].reset_index(drop=True)
        df = df.rename(columns=self.RENAME_DICT_SBER)
        df['Кол-во (шт)'] = df['Плановый исходящий остаток, шт'].str.replace(' ', '').astype(float)
        df = df[self.COLUMNS_TO_KEEP]
        return df

    RENAME_DICT_SBER = {
        'ISIN ценной бумаги': 'ISIN',
        'Количество, шт': 'Кол-во (шт)',
        }