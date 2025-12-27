from typing import Optional
import pandas as pd
from .all_stock_info import AllStockInfo
from .table_splitter import TableSplitter
from .report_registry import ReportRegistry 


class BrokerParser:
    """
    Базовый класс парсера брокерского отчёта.

    Агрегирует информацию из:
    - справочника инструментов (`AllStockInfo`),
    - разделённых таблиц (`TableSplitter.df_dict`),

    Подклассы (например, `SberPareser`, `VtbParser`) обязаны реализовать
    метод `get_source_df()`, возвращающий "сырой" DataFrame с ISIN и количеством.

    После обогащения данными (тикер, лот, название) результат сохраняется
    в `self.balance_report` и, при наличии `registry`, регистрируется.

    Атрибуты:
        all_stock_df: DataFrame со справочной информацией по инструментам.
                      Ожидается наличие столбцов: 'ISIN', 'SECID', 'LOTSIZE', 'SHORTNAME'.
        split_tables_dict: Словарь таблиц, полученный от `TableSplitter`.
        balance_report: Итоговый DataFrame с обогащёнными данными портфеля.
        registry: Реестр отчётов для последующего учёта.
    """
    def __init__(
            self, 
            all_stock_info: AllStockInfo,
            splitter: TableSplitter,
            registry: ReportRegistry
            ) -> None:
        """
        Инициализирует парсер с зависимостями.

        :param all_stock_info: Справочник по ценным бумагам.
        :param splitter: Экземпляр TableSplitter с уже вызванным `.split()`.
        :param registry: Реестр для регистрации итогового отчёта.
        """
        self.all_stock_df = all_stock_info.all_stock_df
        self.split_tables_dict: dict[str, pd.DataFrame] = splitter.df_dict
        self.balance_report: pd.DataFrame
        self.registry = registry

    def get_balance_report_df(self) -> pd.DataFrame:
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
        df:pd.DataFrame = self.get_source_df()
        for index, row,  in df.iterrows():
            isin = row['ISIN']
            ticker = self.all_stock_df.loc[
                self.all_stock_df['ISIN'] == isin, 
                'SECID'
                ].iloc[0]
            lot_size = self.all_stock_df.loc[
                self.all_stock_df['ISIN'] == isin, 
                'LOTSIZE'
                ].iloc[0]
            shortname = self.all_stock_df.loc[
                self.all_stock_df['ISIN'] == isin, 
                'SHORTNAME'
                ].iloc[0]
            df.at[index, "ticker"] = ticker
            df.at[index, "Размер лота"] = lot_size
            df.at[index, "name"] = shortname

        # df['Стоимость'] = df['Стоимость'].astype('float')
        df["Размер лота"] = df["Размер лота"].astype('float')
        df['Кол-во (шт)'] = df['Кол-во (шт)'].astype('float')
        self.balance_report = df
                
        if self.registry and self.balance_report is not None:
            self.registry.add(self.balance_report)
        return df
    
    def get_source_df(self) -> pd.DataFrame:
        """
        Возвращает исходный DataFrame с позициями (ISIN, количество и др.).

        Базовая реализация возвращает пустой DataFrame.
        Должна быть переопределена в подклассах (например, `SberPareser`).

        :returns: DataFrame с минимум столбцами из `COLUMNS_TO_KEEP`.
        :rtype: pd.DataFrame
        """
        return pd.DataFrame()
    
    # Список столбцов, которые должны остаться в итоговом DataFrame после `get_source_df()`
    COLUMNS_TO_KEEP = [
        'ISIN',
        'Кол-во (шт)',
        ]
        